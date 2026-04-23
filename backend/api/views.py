"""
api/views.py
============
Django REST views — expose all StartWise logic as JSON endpoints.
All business logic (agents, pipeline, LLM) is unchanged; only
session management and rendering are adapted for HTTP REST.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.session_utils import (
    delete_state,
    get_a2a_classes,
    get_comm_agent,
    get_finance_agent,
    get_state,
    save_state,
)

logger = logging.getLogger(__name__)

# ── Import existing modules (unchanged) ──────────────────────────────────────
try:
    from agents.finance.tools.parser import parse_founder_input
    from agents.finance.tools.validator import validate_financial_context
    from agents.finance.tools.fetch_benchmarks import fetch_benchmarks
    from agents.finance.calcul_tools.pipeline import run_analysis_pipeline
    MODULES_OK = True
except Exception as _e:
    logger.error("Core modules unavailable: %s", _e)
    MODULES_OK = False


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
    import math
    if obj is None:
        return None
    if isinstance(obj, float):
        # NaN and Infinity are not valid JSON — browsers reject them
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(i) for i in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


def _safe_json(data: dict) -> JsonResponse:
    """Sanitise every float in `data` before serialisation — prevents NaN/Inf breaking JSON."""
    return JsonResponse(_to_dict(data))


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def _has_financial_data(ctx: Any) -> bool:
    if ctx is None:
        return False
    for f in ("burn_rate", "cash_balance", "monthly_revenue", "n_clients",
              "prix_client", "churn_rate", "marketing_budget"):
        if getattr(ctx, f, None) is not None:
            return True
    return False


def _merge_contexts(existing: Any, new: Any) -> Any:
    if existing is None:
        return new
    if new is None:
        return existing
    try:
        from models.data_models import FinancialContext, DataQuality
        e = asdict(existing)
        n = asdict(new)
        merged = dict(e)
        for k, v in n.items():
            if k == "revenue_history":
                old_h = e.get("revenue_history") or []
                new_h = v or []
                seen = {tuple(x.items()) if isinstance(x, dict) else x for x in old_h}
                combined = list(old_h)
                for item in new_h:
                    key = tuple(item.items()) if isinstance(item, dict) else item
                    if key not in seen:
                        combined.append(item)
                        seen.add(key)
                merged["revenue_history"] = combined
            elif v is not None:
                merged[k] = v
        for qf in ("burn_quality", "cash_quality", "revenue_quality"):
            val = merged.get(qf)
            if isinstance(val, str):
                try:
                    merged[qf] = DataQuality[val]
                except KeyError:
                    pass
            elif isinstance(val, dict) and "value" in val:
                try:
                    merged[qf] = DataQuality(val["value"])
                except (ValueError, KeyError):
                    pass
        return FinancialContext(**{k: v for k, v in merged.items()
                                   if k in FinancialContext.__dataclass_fields__})
    except Exception as exc:
        logger.warning("_merge_contexts failed: %s", exc)
        return new


def _format_extracted(ctx: Any, validation: Any, analysis: dict) -> str:
    if ctx is None:
        return ""
    lines = ["### 📊 Données extraites\n"]
    for label, field in [
        ("Burn rate", "burn_rate"), ("Trésorerie", "cash_balance"),
        ("Revenu mensuel", "monthly_revenue"), ("Clients", "n_clients"),
        ("Prix/client", "prix_client"), ("Secteur", "secteur"), ("Pays", "pays"),
    ]:
        val = getattr(ctx, field, None)
        if val is not None:
            if field == "churn_rate" and isinstance(val, float):
                lines.append(f"- **{label}** : {val:.1%}")
            else:
                lines.append(f"- **{label}** : {_fmt(val)}")

    kpis = analysis.get("kpis") if analysis else None
    if kpis:
        lines.append("\n### 📈 KPIs\n")
        rw = getattr(kpis, "runway_months", None)
        ltv = getattr(kpis, "ltv", None)
        cac = getattr(kpis, "cac", None)
        gm = getattr(kpis, "gross_margin", None)
        if rw is not None:
            lines.append(f"- **Runway** : {rw:.1f} mois")
        if ltv and cac and cac > 0:
            lines.append(f"- **LTV/CAC** : {ltv/cac:.1f}x")
        if gm is not None:
            lines.append(f"- **Gross Margin** : {gm:.1%}")

    mc = analysis.get("monte_carlo") if analysis else None
    if mc:
        p50 = getattr(mc, "p50", None)
        proba = getattr(mc, "proba_survie_12m", None)
        if p50:
            lines.append(f"- **Runway P50** : {p50:.1f} mois")
        if proba:
            lines.append(f"- **Survie 12m** : {proba:.0%}")

    phase = analysis.get("phase") if analysis else None
    if phase:
        lines.append(f"\n**Phase** : {phase.name if hasattr(phase, 'name') else phase}")

    if validation:
        dqs = getattr(validation, "data_quality_score", None)
        if dqs is not None:
            lines.append(f"\n**Qualité données** : {dqs:.0%}")

    return "\n".join(lines)


def _parse_docs_extra(docs: list) -> dict:
    import re
    values: dict = {"ltv_cac_ratio": [], "cac_payback_months": [], "nrr": [], "growth_yoy": []}
    patterns = {
        "ltv_cac_ratio": r"ltv[/_\s]*cac[:\s]+([0-9.]+)",
        "cac_payback_months": r"cac\s*payback[:\s]+([0-9.]+)",
        "nrr": r"nrr[:\s]+([0-9.]+)",
        "growth_yoy": r"(?:growth|croissance)[:\s]+([0-9.]+)",
    }
    for doc in (docs or []):
        text = str(doc).lower()
        for key, pat in patterns.items():
            m = re.search(pat, text)
            if m:
                try:
                    values[key].append(float(m.group(1)))
                except ValueError:
                    pass
    return {k: sorted(v)[len(v) // 2] for k, v in values.items() if v}


def _format_benchmark_result(bench: Any, ctx: Any, analysis: dict = None) -> str:
    """
    Comparaison sectorielle RAG — analyse détaillée avec descriptions et plan d'action.
    Portée depuis app.py pour conserver tout le contenu de l'analyse originale.
    """
    if bench is None:
        return ""

    source = getattr(bench, "source", "unknown")
    sim    = getattr(bench, "similarity_score", 0.0)
    docs   = list(getattr(bench, "documents_raw", []) or [])

    ctx_dict = _to_dict(ctx)
    sector   = ctx_dict.get("secteur") or "SaaS"
    extra    = _parse_docs_extra(docs)

    analysis = analysis or {}
    kpis = analysis.get("kpis")

    # Valeurs founder depuis KPIResult
    churn           = ctx_dict.get("churn_rate")
    rev             = ctx_dict.get("monthly_revenue")
    founder_gm_pct  = getattr(kpis, "gross_margin_pct", None)  if kpis else None
    founder_gm      = founder_gm_pct / 100 if founder_gm_pct is not None else None
    founder_ltv_cac = getattr(kpis, "ltv_cac_ratio", None)     if kpis else None
    founder_cac     = getattr(kpis, "cac", None)               if kpis else None
    founder_arr     = getattr(kpis, "arr", None)               if kpis else (rev * 12 if rev else None)
    ltv_cac_status  = getattr(kpis, "ltv_cac_status", "")      if kpis else ""
    gm_status       = getattr(kpis, "gross_margin_status", "")  if kpis else ""

    # Benchmarks sectoriels
    churn_med = getattr(bench, "churn_median", None)
    gm_med    = getattr(bench, "gross_margin_median", None)
    ev_mult   = getattr(bench, "valorisation_multiple", None)
    ltv_cac_b = extra.get("ltv_cac_ratio")
    payback_b = extra.get("cac_payback_months")
    nrr_b     = extra.get("nrr")
    growth_b  = extra.get("growth_yoy")

    if "Tavily" in source or "tavily" in source:
        badge = "🟠 **Tavily live**"
    else:
        badge = "🟢 **ChromaDB cache**"

    lines = []
    lines.append(
        f"---\n### 🏆 Positionnement sectoriel — {sector}\n"
        f"Similarité RAG : **{sim:.0%}** &nbsp;·&nbsp; {badge} &nbsp;·&nbsp; {len(docs)} doc(s)"
    )

    def _gap(f, b):     return (f - b) / (abs(b) + 1e-9)
    def _x_label(v):    return f"{v:.1f}x" if v is not None else "—"

    metric_blocks = []

    # ── Gross Margin ──────────────────────────────────────────────────────────
    if gm_med is not None:
        fv = founder_gm_pct
        fv_str = f"{fv:.1f}%" if fv is not None else "—"
        bv_str = f"{gm_med:.1%}"
        if fv is not None:
            gap = _gap(founder_gm, gm_med)
            if abs(gap) < 0.05:
                status = "Aligné"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) est alignée avec la médiane sectorielle ({gm_med:.1%}). "
                    "Une marge brute saine reflète une structure de coûts variables maîtrisée. "
                    "Cible SaaS B2B : > 70% pour préserver le levier opérationnel au scale."
                )
            elif gap > 0:
                status = "Au-dessus ✓"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) dépasse la médiane sectorielle ({gm_med:.1%}) de {gap:.0%}. "
                    "Cela traduit une pricing power solide ou des coûts de livraison faibles. "
                    "Avantage compétitif lors d'une levée : les VCs valorisent une GM > 70% comme signal de scalabilité."
                )
            else:
                status = "En dessous ✗"
                desc = (
                    f"Votre gross margin ({fv:.1f}%) est inférieure à la médiane ({gm_med:.1%}) de {abs(gap):.0%}. "
                    "Un GM < 60% signale soit des coûts variables élevés (COGS, infrastructure, support), "
                    "soit un sous-pricing. Levier prioritaire : revoir la structure tarifaire ou réduire le coût de livraison."
                )
            icon = {"SAIN": "✓", "FAIBLE": "⚡", "CRITIQUE": "✗"}.get(gm_status, "→")
            metric_blocks.append((f"{icon} Gross Margin", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("Gross Margin", "—", bv_str, "—",
                                   f"Médiane sectorielle : {bv_str}. Fournissez vos COGS pour comparer."))

    # ── Churn ─────────────────────────────────────────────────────────────────
    if churn_med is not None and churn is not None:
        gap = _gap(churn, churn_med)
        bv_str = f"{churn_med:.1%}"
        fv_str = f"{churn:.1%}"
        life_months = round(1 / churn, 1) if churn > 0 else None
        if abs(gap) < 0.10:
            status = "Aligné"
            desc = (
                f"Votre churn mensuel ({churn:.1%}) est proche de la médiane ({bv_str}). "
                f"Durée de vie client estimée : {life_months} mois. "
                "Objectif SaaS B2B : < 1%/mois (Net Revenue Retention > 100%)."
            )
        elif gap > 0:
            status = "Au-dessus du marché ✗"
            desc = (
                f"Votre churn ({churn:.1%}) dépasse la médiane sectorielle ({bv_str}) de {gap:.0%}. "
                f"Cela réduit la durée de vie client à {life_months} mois et alourdit mécaniquement le CAC effectif. "
                "Priorités : renforcer l'onboarding, mettre en place des health scores, "
                "et investiguer les churns via exit interviews."
            )
        else:
            status = "En dessous du marché ✓"
            desc = (
                f"Votre churn ({churn:.1%}) est inférieur à la médiane ({bv_str}) — signal fort de rétention. "
                f"Durée de vie client : {life_months} mois. "
                "Une attrition faible amplifie la croissance organique via l'expansion ARR et réduit la pression sur l'acquisition."
            )
        metric_blocks.append(("↩ Churn mensuel", fv_str, bv_str, status, desc))

    # ── LTV / CAC ─────────────────────────────────────────────────────────────
    if ltv_cac_b is not None:
        fv_str = _x_label(founder_ltv_cac)
        bv_str = _x_label(ltv_cac_b)
        if founder_ltv_cac is not None:
            gap = _gap(founder_ltv_cac, ltv_cac_b)
            if abs(gap) < 0.10:
                status = "Aligné"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — dans la norme sectorielle ({ltv_cac_b:.1f}x). "
                    "Un ratio > 3x est le standard VC pour valider l'unit economics. "
                    "Cherchez à atteindre 5x+ pour démontrer une efficacité d'acquisition supérieure."
                )
            elif gap > 0:
                status = "Au-dessus ✓"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — supérieur à la médiane ({ltv_cac_b:.1f}x). "
                    f"Vous générez {founder_ltv_cac:.1f} DT de valeur pour chaque DT investi en acquisition. "
                    "Position favorable : les VCs utilisent ce ratio comme proxy de la scalabilité du go-to-market."
                )
            else:
                status = "En dessous ✗"
                desc = (
                    f"Ratio LTV/CAC de {founder_ltv_cac:.1f}x — inférieur à la médiane ({ltv_cac_b:.1f}x). "
                    "Chaque DT investi en acquisition génère moins de valeur que vos pairs. "
                    "Leviers : réduire le CAC (canaux organiques, referral), allonger la durée de vie client, "
                    "ou augmenter le prix moyen via upsell."
                )
            icon = {"SAIN": "✓", "LIMITE": "⚡", "DANGEREUX": "✗"}.get(ltv_cac_status, "→")
            metric_blocks.append((f"{icon} LTV / CAC", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("LTV / CAC", "—", bv_str, "—",
                                   f"Médiane sectorielle : {bv_str}. Fournissez marketing_budget et new_clients_month."))

    # ── EV / ARR Multiple ─────────────────────────────────────────────────────
    if ev_mult is not None and founder_arr is not None:
        valuation_ref = founder_arr * ev_mult
        desc = (
            f"Le multiple EV/ARR médian pour ce segment est **{ev_mult:.1f}x**. "
            f"Sur la base de votre ARR actuel ({_fmt(founder_arr)} DT), "
            f"la valorisation de référence est **~{_fmt(valuation_ref)} DT**. "
            "Ce multiple reflète les attentes du marché en matière de croissance et de rétention. "
            "Il diminue avec l'augmentation des taux ou la compression des multiples SaaS (post-2022)."
        )
        metric_blocks.append(("◈ Valorisation EV/ARR",
                               f"ARR {_fmt(founder_arr)} DT",
                               f"{ev_mult:.1f}x",
                               f"→ ~{_fmt(valuation_ref)} DT",
                               desc))

    # ── CAC Payback ───────────────────────────────────────────────────────────
    if payback_b is not None:
        desc = (
            f"Le CAC payback médian du secteur est **{payback_b:.0f} mois** "
            "(délai pour récupérer le coût d'acquisition via les revenus). "
        )
        if founder_cac and churn and churn > 0:
            desc += f"Votre CAC ({_fmt(founder_cac)} DT) implique un payback estimé selon votre pricing. "
        desc += "SaaS B2B sain : < 12 mois. > 18 mois signale un risque de capital intensif."
        metric_blocks.append(("⏱ CAC Payback",
                               f"{_fmt(founder_cac)} DT CAC" if founder_cac else "—",
                               f"{payback_b:.0f} mois",
                               "Référence", desc))

    # ── NRR ───────────────────────────────────────────────────────────────────
    if nrr_b is not None:
        desc = (
            f"Le Net Revenue Retention médian du secteur est **{nrr_b:.1f}%**. "
            "Un NRR > 100% signifie que les revenus existants croissent d'eux-mêmes (expansion, upsell). "
            "C'est l'indicateur le plus valorisé par les investisseurs SaaS growth-stage : "
            "il prouve que la croissance peut s'auto-financer sans acquisition nette."
        )
        metric_blocks.append(("◎ NRR (Net Revenue Retention)", "—", f"{nrr_b:.1f}%", "Référence", desc))

    # ── Croissance YoY ────────────────────────────────────────────────────────
    if growth_b is not None:
        desc = (
            f"La croissance ARR YoY médiane du secteur est **{growth_b:.0f}%**. "
            "Règle empirique : 'Triple, Triple, Double, Double, Double' (T2D3) "
            "pour les SaaS B2B visant une levée Series A/B. "
            "En dessous de la médiane, la croissance organique seule peut ne pas suffire à justifier une valorisation premium."
        )
        metric_blocks.append(("↗ Croissance ARR YoY", "—", f"{growth_b:.0f}%", "Référence", desc))

    if not metric_blocks:
        lines.append("\n_Benchmarks sectoriels insuffisants pour une comparaison complète._")
    else:
        # Tableau synthèse
        lines.append("\n**Comparaison vs médiane sectorielle**\n")
        lines.append("| Métrique | Votre valeur | Médiane secteur | Positionnement |")
        lines.append("|----------|-------------|-----------------|---------------|")
        for name, fv, bv, status, _ in metric_blocks:
            lines.append(f"| {name} | {fv} | {bv} | {status} |")

        # Descriptions détaillées
        lines.append("")
        for name, fv, bv, status, desc in metric_blocks:
            clean_name = name.lstrip("✓✗⚡→↩◈⏱◎↗ ")
            lines.append(f"\n**{clean_name}** — {desc}")

    # ── Recommandations actionnables ──────────────────────────────────────────
    lines.append("\n\n**Plan d'action prioritaire**\n")
    recs = []

    if gm_status == "CRITIQUE" or (founder_gm is not None and gm_med and founder_gm < gm_med * 0.80):
        recs.append(
            "**[Pricing/COGS]** Gross margin insuffisante — auditez vos coûts variables (hosting, support, ops) "
            "et envisagez une révision tarifaire ou le passage à un modèle d'abonnement annuel "
            "(réduit le churn et améliore le cashflow)."
        )
    if churn is not None and churn_med is not None and churn > churn_med * 1.3:
        recs.append(
            f"**[Rétention]** Churn {churn:.1%} vs médiane {churn_med:.1%} — mettez en place un Customer Success "
            "proactif (health scores, QBR), un onboarding structuré sur 30/60/90 jours, "
            "et des alertes de désengagement avant résiliation."
        )
    if ltv_cac_status == "DANGEREUX":
        recs.append(
            f"**[Unit Economics]** LTV/CAC {founder_ltv_cac:.1f}x — en dessous de 1x, le modèle d'acquisition est déficitaire. "
            "Action immédiate : couper les canaux d'acquisition les moins efficients, "
            "augmenter le prix moyen, ou cibler un segment client avec LTV plus élevée."
        )
    elif ltv_cac_status == "LIMITE":
        recs.append(
            f"**[Scalabilité]** LTV/CAC {founder_ltv_cac:.1f}x (cible > 3x) — optimisez les canaux organiques "
            "(SEO, referral, partenariats) pour réduire le CAC sans augmenter le budget marketing."
        )
    if ev_mult and founder_arr:
        valuation_ref = founder_arr * ev_mult
        recs.append(
            f"**[Valorisation]** À {ev_mult:.1f}x ARR, votre valorisation indicative est ~{_fmt(valuation_ref)} DT. "
            "Pour dépasser ce multiple, démontrez une croissance > médiane secteur et un NRR > 110%."
        )

    if not recs:
        recs.append(
            "Vos métriques sont globalement dans la norme sectorielle. "
            "Focus : augmenter la croissance ARR pour accéder à des multiples de valorisation supérieurs."
        )
    for r in recs:
        lines.append(f"- {r}")

    return "\n".join(lines)


def _call_llm(messages: list, max_tokens: int = 800) -> str:
    import httpx
    key = os.getenv("ESPRIT_API_KEY", "")
    if not key:
        return ""
    try:
        r = httpx.post(
            "https://tokenfactory.esprit.tn/api/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct")),
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=30.0,
            verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return ""


def _answer_general(prompt: str, ctx: Any) -> str:
    ctx_str = ""
    if ctx is not None:
        try:
            d = asdict(ctx)
            relevant = {k: v for k, v in d.items()
                        if v is not None and k in ("burn_rate", "cash_balance",
                        "monthly_revenue", "n_clients", "churn_rate", "secteur", "pays")}
            if relevant:
                ctx_str = "Contexte: " + ", ".join(f"{k}={v}" for k, v in relevant.items())
        except Exception:
            pass

    reply = _call_llm([
        {"role": "system", "content": (
            "Tu es un assistant CFO expert pour les startups en Tunisie. "
            "Réponds en français, de manière concise et professionnelle. " + ctx_str
        )},
        {"role": "user", "content": prompt},
    ])
    return reply or "Je n'ai pas pu traiter votre requête pour le moment."


def _run_whatif(prompt: str, ctx: Any) -> str:
    if ctx is None:
        return "Veuillez d'abord fournir vos données financières."

    try:
        ctx_dict = asdict(ctx)
    except Exception:
        return _answer_general(prompt, ctx)

    nums = {k: v for k, v in ctx_dict.items()
            if isinstance(v, (int, float)) and k in (
                "burn_rate", "cash_balance", "monthly_revenue", "n_clients",
                "prix_client", "churn_rate", "marketing_budget", "cogs", "new_clients_month"
            )}

    raw = _call_llm([
        {"role": "system", "content": (
            "Détecte si la requête est une simulation hypothétique. "
            'Si oui: {"is_whatif":true,"modifications":{"field":{"op":"multiply|add|set","factor":N,"value":N}}} '
            'Sinon: {"is_whatif":false,"modifications":{}}. JSON uniquement.'
        )},
        {"role": "user", "content": f"Données: {json.dumps(nums)}\nRequête: {prompt}"},
    ], max_tokens=300)

    try:
        start = raw.find("{"); end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        if not parsed.get("is_whatif"):
            return _answer_general(prompt, ctx)
        mods = parsed.get("modifications", {})
    except Exception:
        return _answer_general(prompt, ctx)

    new_vals: dict = {}
    for field, op_dict in mods.items():
        current = getattr(ctx, field, None)
        if current is None:
            continue
        op = op_dict.get("op", "multiply")
        try:
            if op == "multiply":
                new_vals[field] = current * float(op_dict.get("factor", 1))
            elif op == "add":
                new_vals[field] = current + float(op_dict.get("value", 0))
            elif op == "set":
                new_vals[field] = float(op_dict.get("value", current))
        except (TypeError, ValueError):
            pass

    if not new_vals:
        return _answer_general(prompt, ctx)

    try:
        old_res = run_analysis_pipeline(ctx)
        new_res = run_analysis_pipeline(replace(ctx, **new_vals))
        lines = ["### ⚡ Simulation What-If\n", "**Modifications :**"]
        for field, val in new_vals.items():
            old_val = getattr(ctx, field, "?")
            lines.append(f"- {field}: {_fmt(old_val)} → {_fmt(val)}")

        lines.append("\n**Impact KPIs :**")
        ok = old_res.get("kpis")
        nk = new_res.get("kpis")
        if ok and nk:
            old_rw = getattr(ok, "runway_months", None)
            new_rw = getattr(nk, "runway_months", None)
            if old_rw and new_rw:
                d = new_rw - old_rw
                lines.append(f"- **Runway** : {old_rw:.1f}m → **{new_rw:.1f}m** ({'↑' if d>0 else '↓'} {d:+.1f}m)")
            old_gm = getattr(ok, "gross_margin", None)
            new_gm = getattr(nk, "gross_margin", None)
            if old_gm and new_gm:
                lines.append(f"- **Gross Margin** : {old_gm:.1%} → **{new_gm:.1%}**")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("whatif pipeline failed: %s", exc)
        return _answer_general(prompt, ctx)


def _process_ctx(state: dict, new_ctx: Any, raw_text: str) -> tuple:
    """Core orchestrator — replicates app.py _process_financial_context logic."""
    FA = get_finance_agent()
    CA = get_comm_agent()
    cls = get_a2a_classes()

    merged = _merge_contexts(state.get("financial_context"), new_ctx)

    if CA is not None:
        try:
            CA.store_financial_context(merged)
        except Exception:
            pass

    bench = None

    # ── Path A: Full agent loop ───────────────────────────────────────────
    if FA is not None and cls and raw_text.strip():
        Task = cls["Task"]; TaskStatus = cls["TaskStatus"]
        Message = cls["Message"]; TextPart = cls["TextPart"]

        new_msg = Message(role="user", parts=[TextPart(text=raw_text)])
        existing_task = state.get("agent_task")
        fresh = state.get("_agent_fresh", False)

        if (existing_task and
                getattr(getattr(existing_task, "status", None), "state", "") == "input-required"
                and not fresh):
            existing_task.add_message(new_msg)
            result_task = FA.continue_task(existing_task)
        else:
            state.pop("a2a_publish_time", None)
            task_id = str(uuid.uuid4())
            state["_agent_task_id"] = task_id
            task = Task(id=task_id, status=TaskStatus(state="submitted"), messages=[new_msg])
            result_task = FA.process_task(task)

        state["agent_task"] = result_task
        state["_agent_fresh"] = False

        ctx = result_task.metadata.get("_context", merged)
        validation = result_task.metadata.get("_validation")
        analysis = result_task.metadata.get("_analysis") or {}
        benchmarks = result_task.metadata.get("_benchmarks")

        if validation is None:
            try:
                validation = validate_financial_context(ctx)
            except Exception:
                validation = None

        questions = []
        if getattr(getattr(result_task, "status", None), "state", "") == "input-required":
            for msg in reversed(result_task.messages):
                if msg.role == "agent":
                    for part in msg.parts:
                        if hasattr(part, "text") and part.text:
                            questions = [l.lstrip("•").strip()
                                         for l in part.text.splitlines() if l.strip()]
                            break
                    break

        state["financial_context"] = ctx
        state["validation_result"] = validation
        state["analysis"] = analysis

        if benchmarks is None and getattr(validation, "is_valid", False):
            try:
                benchmarks = fetch_benchmarks(ctx)
            except Exception:
                benchmarks = None

        if benchmarks is not None:
            bench = benchmarks
            state["last_bench"] = bench
            state["last_bench_extra"] = _parse_docs_extra(
                list(getattr(bench, "documents_raw", []) or [])
            )

        if CA and os.getenv("A2A_BUS_URL"):
            state["a2a_publish_time"] = time.time()
            state["awaiting_clarification"] = False

        data_text = _format_extracted(ctx, validation, analysis)
        bench_text = _format_benchmark_result(bench, ctx, analysis) if bench is not None else ""
        state["last_bench_text"] = bench_text
        return data_text, questions, bench

    # ── Path B: Direct pipeline fallback ─────────────────────────────────
    state.pop("a2a_publish_time", None)
    analysis: dict = {}
    try:
        analysis = run_analysis_pipeline(merged)
    except Exception as exc:
        logger.warning("Pipeline failed: %s", exc)

    state["analysis"] = analysis

    validation = None
    try:
        validation = validate_financial_context(merged)
    except Exception:
        pass
    state["validation_result"] = validation

    if getattr(validation, "is_valid", False):
        try:
            bench = fetch_benchmarks(merged)
        except Exception:
            bench = None

    if bench is not None:
        state["last_bench"] = bench
        state["last_bench_extra"] = _parse_docs_extra(
            list(getattr(bench, "documents_raw", []) or [])
        )

    state["financial_context"] = merged

    questions: list = []
    if validation:
        qs = getattr(validation, "questions_to_ask", []) or []
        missing = getattr(validation, "missing_critical", []) or []
        questions = list(qs[:3]) or [f"Pouvez-vous préciser votre {m} ?" for m in missing[:2]]

    data_text = _format_extracted(merged, validation, analysis)
    bench_text = _format_benchmark_result(bench, merged, analysis) if bench is not None else ""
    state["last_bench_text"] = bench_text

    if CA and os.getenv("A2A_BUS_URL"):
        state["a2a_publish_time"] = time.time()

    return data_text, questions, bench


# ── Serialisers ───────────────────────────────────────────────────────────────

def _ser_analysis(analysis: dict) -> dict:
    if not analysis:
        return {}
    out: dict = {}
    for key in ("kpis", "monte_carlo", "scenarios", "seasonality", "comparator"):
        val = analysis.get(key)
        if val is not None:
            out[key] = _to_dict(val)
    phase = analysis.get("phase")
    if phase:
        out["phase"] = phase.name if hasattr(phase, "name") else str(phase)
    confidence = analysis.get("confidence")
    if confidence is not None:
        out["confidence"] = _to_dict(confidence)
    return out


def _ser_validation(v: Any) -> dict | None:
    if v is None:
        return None
    return {
        "is_valid": getattr(v, "is_valid", False),
        "data_quality_score": getattr(v, "data_quality_score", 0),
        "missing_critical": list(getattr(v, "missing_critical", []) or []),
        "incoherences": list(getattr(v, "incoherences", []) or []),
        "questions_to_ask": list(getattr(v, "questions_to_ask", []) or []),
    }


def _ser_ctx(ctx: Any) -> dict | None:
    if ctx is None:
        return None
    try:
        d = asdict(ctx)
        for k, v in d.items():
            if hasattr(v, "name"):
                d[k] = v.name
            elif hasattr(v, "value"):
                d[k] = v.value
        return d
    except Exception:
        return None


def _ser_bench(bench: Any) -> dict | None:
    if bench is None:
        return None
    return {
        "source": getattr(bench, "source", ""),
        "similarity_score": getattr(bench, "similarity_score", 0),
        "churn_median": getattr(bench, "churn_median", None),
        "gross_margin_median": getattr(bench, "gross_margin_median", None),
        "valorisation_multiple": getattr(bench, "valorisation_multiple", None),
    }


def _ser_task(task: Any) -> dict | None:
    if task is None:
        return None
    try:
        return task.to_dict() if hasattr(task, "to_dict") else None
    except Exception:
        return None


# ── Session ID ────────────────────────────────────────────────────────────────

def _sid(request) -> str:
    # Prefer the custom header (sent by frontend via localStorage)
    # This avoids all CORS credential/cookie issues entirely
    sid = request.headers.get("X-Session-ID", "").strip()
    if sid:
        return sid
    # Fallback: Django session cookie
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


# ── Views ─────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST"])
def chat_view(request):
    if not MODULES_OK:
        return JsonResponse({"error": "Modules non chargés"}, status=500)

    session_id = _sid(request)
    body = json.loads(request.body)
    prompt = body.get("message", "").strip()
    if not prompt:
        return JsonResponse({"error": "Message vide"}, status=400)

    state = get_state(session_id)
    messages = state.get("messages", [])
    messages.append({"role": "user", "content": prompt})

    # Parse input
    new_ctx = None
    try:
        new_ctx = parse_founder_input(prompt)
    except Exception as exc:
        logger.warning("parse_founder_input: %s", exc)

    # What-if mode
    if state.get("whatif_mode") and state.get("financial_context") is not None:
        reply = _run_whatif(prompt, state.get("financial_context"))
        state["whatif_mode"] = False
        messages.append({"role": "assistant", "content": reply})
        state["messages"] = messages
        save_state(session_id, state)
        return JsonResponse({"type": "whatif", "reply": reply, "messages": messages})

    # Financial data detected
    if _has_financial_data(new_ctx):
        data_text, questions, bench = _process_ctx(state, new_ctx, raw_text=prompt)
        bench_text = state.get("last_bench_text", "")
        # Build the full reply: extracted data + benchmark analysis + clarification questions
        reply = data_text
        if bench_text:
            reply += "\n\n" + bench_text
        if questions:
            reply += "\n\n---\n**Questions pour compléter l'analyse :**\n" + "\n".join(f"- {q}" for q in questions)
        messages.append({"role": "assistant", "content": reply})
        state["messages"] = messages
        save_state(session_id, state)
        return _safe_json({
            "type": "analysis",
            "reply": reply,
            "data_text": data_text,
            "bench_text": bench_text,
            "questions": questions,
            "analysis": _ser_analysis(state.get("analysis", {})),
            "financial_context": _ser_ctx(state.get("financial_context")),
            "validation": _ser_validation(state.get("validation_result")),
            "bench": _ser_bench(bench),
            "bench_extra": state.get("last_bench_extra", {}),
            "agent_task": _ser_task(state.get("agent_task")),
            "a2a_publish_time": state.get("a2a_publish_time"),
            "messages": messages,
        })

    # General question
    reply = _answer_general(prompt, state.get("financial_context"))
    messages.append({"role": "assistant", "content": reply})
    state["messages"] = messages
    save_state(session_id, state)
    return JsonResponse({"type": "general", "reply": reply, "messages": messages})


@csrf_exempt
@require_http_methods(["GET"])
def state_view(request):
    session_id = _sid(request)
    state = get_state(session_id)
    task = state.get("agent_task")
    task_state = getattr(getattr(task, "status", None), "state", "")
    return _safe_json({
        "messages": state.get("messages", []),
        "financial_context": _ser_ctx(state.get("financial_context")),
        "validation": _ser_validation(state.get("validation_result")),
        "analysis": _ser_analysis(state.get("analysis", {})),
        "bench": _ser_bench(state.get("last_bench")),
        "bench_extra": state.get("last_bench_extra", {}),
        "bench_text": state.get("last_bench_text", ""),
        "shown_sections": list(state.get("shown_sections", set())),
        "whatif_mode": state.get("whatif_mode", False),
        "awaiting_clarification": state.get("awaiting_clarification", False),
        "a2a_publish_time": state.get("a2a_publish_time"),
        "agent_task_state": task_state,
        "agent_task": _ser_task(task),
        "conversations": [{"id": c["id"], "title": c["title"]}
                          for c in state.get("conversations", [])],
    })


@csrf_exempt
@require_http_methods(["GET"])
def a2a_state_view(request):
    comm = get_comm_agent()
    if comm is None or not os.getenv("A2A_BUS_URL"):
        return JsonResponse({"available": False})
    try:
        return _safe_json({"available": True, **comm.get_state()})
    except Exception as exc:
        return JsonResponse({"available": False, "error": str(exc)})


@csrf_exempt
@require_http_methods(["POST"])
def a2a_clarification_view(request):
    session_id = _sid(request)
    comm = get_comm_agent()
    if comm is None:
        return JsonResponse({"error": "CommAgent non disponible"}, status=503)
    body = json.loads(request.body)
    answer = body.get("answer", "")
    comm.answer_clarification(answer)
    state = get_state(session_id)
    state["awaiting_clarification"] = False
    state["a2a_publish_time"] = time.time()
    msgs = state.get("messages", [])
    msgs.append({"role": "user", "content": answer})
    msgs.append({"role": "assistant",
                 "content": "Réponse transmise à l'investment_agent. Analyse en cours..."})
    state["messages"] = msgs
    save_state(session_id, state)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def toggle_section_view(request):
    session_id = _sid(request)
    body = json.loads(request.body)
    section = body.get("section", "")
    state = get_state(session_id)
    sections = state.get("shown_sections", set())
    if isinstance(sections, list):
        sections = set(sections)
    if section in sections:
        sections.discard(section)
    else:
        sections.add(section)
    state["shown_sections"] = sections
    save_state(session_id, state)
    return JsonResponse({"shown_sections": list(sections)})


@csrf_exempt
@require_http_methods(["POST"])
def toggle_whatif_view(request):
    session_id = _sid(request)
    state = get_state(session_id)
    state["whatif_mode"] = not state.get("whatif_mode", False)
    save_state(session_id, state)
    return JsonResponse({"whatif_mode": state["whatif_mode"]})


@csrf_exempt
@require_http_methods(["POST"])
def whatif_view(request):
    session_id = _sid(request)
    body = json.loads(request.body)
    prompt = body.get("prompt", "")
    state = get_state(session_id)
    reply = _run_whatif(prompt, state.get("financial_context"))
    msgs = state.get("messages", [])
    msgs.append({"role": "user", "content": prompt})
    msgs.append({"role": "assistant", "content": reply})
    state["messages"] = msgs
    state["whatif_mode"] = False
    save_state(session_id, state)
    return JsonResponse({"reply": reply, "messages": msgs})


@csrf_exempt
@require_http_methods(["POST"])
def pdf_view(request):
    session_id = _sid(request)
    state = get_state(session_id)
    ctx = state.get("financial_context")
    if ctx is None:
        return JsonResponse({"error": "Aucune donnée disponible"}, status=400)
    try:
        from agents.finance.tools.pdf_report import generate_pdf_report
        from datetime import datetime
        pdf_bytes = generate_pdf_report(
            ctx,
            state.get("validation_result"),
            state.get("analysis", {}),
            state.get("last_bench"),
            state.get("last_bench_extra", {}),
        )
        # Ensure we have raw bytes (fpdf2 output() returns bytes)
        if not isinstance(pdf_bytes, (bytes, bytearray)):
            pdf_bytes = bytes(pdf_bytes)
        date_str = datetime.now().strftime("%Y%m%d")
        response = HttpResponse(bytes(pdf_bytes), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="startwise_rapport_{date_str}.pdf"'
        )
        response["Content-Length"] = len(pdf_bytes)
        response["Cache-Control"] = "no-cache"
        return response
    except Exception as exc:
        import traceback
        logger.error("PDF generation failed:\n%s", traceback.format_exc())
        return JsonResponse({"error": str(exc), "detail": traceback.format_exc()}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_view(request):
    if not MODULES_OK:
        return JsonResponse({"error": "Modules non chargés"}, status=500)
    session_id = _sid(request)
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "Aucun fichier reçu"}, status=400)

    suffix = Path(uploaded.name).suffix
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        new_ctx = parse_founder_input(tmp_path)
        os.unlink(tmp_path)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)

    state = get_state(session_id)
    if _has_financial_data(new_ctx):
        data_text, questions, bench = _process_ctx(state, new_ctx, raw_text="")
        save_state(session_id, state)
        return JsonResponse({
            "type": "analysis",
            "data_text": data_text,
            "questions": questions,
            "analysis": _ser_analysis(state.get("analysis", {})),
            "financial_context": _ser_ctx(state.get("financial_context")),
            "validation": _ser_validation(state.get("validation_result")),
            "bench": _ser_bench(bench),
        })
    return JsonResponse({"type": "no_data",
                         "message": "Aucune donnée financière détectée dans le fichier"})


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def reset_view(request):
    session_id = _sid(request)
    delete_state(session_id)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def new_conversation_view(request):
    session_id = _sid(request)
    state = get_state(session_id)
    msgs = state.get("messages", [])
    if msgs and any(m["role"] == "user" for m in msgs):
        first = next((m["content"] for m in msgs if m["role"] == "user"), "Conv")
        title = first[:40] + ("..." if len(first) > 40 else "")
        conv = {
            "id": str(uuid.uuid4()),
            "title": title,
            "messages": msgs,
        }
        convs = state.get("conversations", [])
        convs.insert(0, conv)
        state["conversations"] = convs[:20]

    from api.session_utils import _default_state
    new_state = _default_state()
    new_state["conversations"] = state.get("conversations", [])
    save_state(session_id, new_state)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["GET"])
def conversations_view(request):
    session_id = _sid(request)
    state = get_state(session_id)
    return JsonResponse({
        "conversations": [{"id": c["id"], "title": c["title"]}
                          for c in state.get("conversations", [])]
    })


@csrf_exempt
@require_http_methods(["POST"])
def restore_conversation_view(request):
    session_id = _sid(request)
    body = json.loads(request.body)
    conv_id = body.get("conversation_id", "")
    state = get_state(session_id)
    conv = next((c for c in state.get("conversations", []) if c["id"] == conv_id), None)
    if conv is None:
        return JsonResponse({"error": "Conversation non trouvée"}, status=404)
    state["messages"] = conv.get("messages", [])
    save_state(session_id, state)
    return JsonResponse({"ok": True, "messages": conv.get("messages", [])})


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_conversation_view(request, conv_id: str):
    session_id = _sid(request)
    state = get_state(session_id)
    state["conversations"] = [c for c in state.get("conversations", []) if c["id"] != conv_id]
    save_state(session_id, state)
    return JsonResponse({"ok": True})
