"""
api/formatters.py
=================
Text formatting helpers — convert raw pipeline results into human-readable
Markdown strings displayed in the chat and exported to PDF.
"""
from __future__ import annotations
import re
from typing import Any


# ── Utility ───────────────────────────────────────────────────────────────────

def fmt(v: Any) -> str:
    """Format a number with thousands separator, returns '—' for None."""
    if v is None:
        return "—"
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(v)


def parse_docs_extra(docs: list) -> dict:
    """Extract numeric metrics from RAG documents via regex."""
    values: dict = {
        "ltv_cac_ratio": [], "cac_payback_months": [], "nrr": [], "growth_yoy": []
    }
    patterns = {
        "ltv_cac_ratio":      r"ltv[/_\s]*cac[:\s]+([0-9.]+)",
        "cac_payback_months": r"cac\s*payback[:\s]+([0-9.]+)",
        "nrr":                r"nrr[:\s]+([0-9.]+)",
        "growth_yoy":         r"(?:growth|croissance)[:\s]+([0-9.]+)",
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


# ── Extracted data summary ────────────────────────────────────────────────────

def format_extracted(ctx: Any, validation: Any, analysis: dict) -> str:
    """Build a Markdown summary of extracted financial data + KPIs."""
    if ctx is None:
        return ""
    lines = ["### Données extraites\n"]
    for label, field in [
        ("Burn rate", "burn_rate"), ("Trésorerie", "cash_balance"),
        ("Revenu mensuel", "monthly_revenue"), ("Clients", "n_clients"),
        ("Prix/client", "prix_client"), ("Secteur", "secteur"), ("Pays", "pays"),
    ]:
        val = getattr(ctx, field, None)
        if val is not None:
            lines.append(f"- **{label}** : {val:.1%}" if field == "churn_rate" and isinstance(val, float)
                         else f"- **{label}** : {fmt(val)}")

    kpis = analysis.get("kpis") if analysis else None
    if kpis:
        lines.append("\n### KPIs\n")
        rw  = getattr(kpis, "runway_months", None)
        ltv = getattr(kpis, "ltv", None)
        cac = getattr(kpis, "cac", None)
        gm  = getattr(kpis, "gross_margin", None)
        if rw  is not None:          lines.append(f"- **Runway** : {rw:.1f} mois")
        if ltv and cac and cac > 0:  lines.append(f"- **LTV/CAC** : {ltv/cac:.1f}x")
        if gm  is not None:          lines.append(f"- **Gross Margin** : {gm:.1%}")

    mc = analysis.get("monte_carlo") if analysis else None
    if mc:
        p50   = getattr(mc, "p50", None)
        proba = getattr(mc, "proba_survie_12m", None)
        if p50:   lines.append(f"- **Runway P50** : {p50:.1f} mois")
        if proba: lines.append(f"- **Survie 12m** : {proba:.0%}")

    phase = analysis.get("phase") if analysis else None
    if phase:
        lines.append(f"\n**Phase** : {phase.name if hasattr(phase, 'name') else phase}")

    if validation:
        dqs = getattr(validation, "data_quality_score", None)
        if dqs is not None:
            lines.append(f"\n**Qualité données** : {dqs:.0%}")

    return "\n".join(lines)


# ── Benchmark comparison ──────────────────────────────────────────────────────

def format_benchmark_result(bench: Any, ctx: Any, analysis: dict = None) -> str:
    """Build a detailed Markdown sector comparison (RAG results vs founder KPIs)."""
    if bench is None:
        return ""
    # Don't display misleading "0 doc(s)" when benchmarks are unavailable
    if getattr(bench, "source", "") == "unavailable":
        return ""
    docs_check = list(getattr(bench, "documents_raw", []) or [])
    if not docs_check and getattr(bench, "similarity_score", 0.0) == 0.0:
        return ""

    from cfo.serializers import to_dict
    source   = getattr(bench, "source", "unknown")
    sim      = getattr(bench, "similarity_score", 0.0)
    docs     = list(getattr(bench, "documents_raw", []) or [])
    ctx_dict = to_dict(ctx)
    sector   = ctx_dict.get("secteur") or "SaaS"
    extra    = parse_docs_extra(docs)
    analysis = analysis or {}
    kpis     = analysis.get("kpis")

    churn          = ctx_dict.get("churn_rate")
    rev            = ctx_dict.get("monthly_revenue")
    founder_gm_pct = getattr(kpis, "gross_margin_pct", None)  if kpis else None
    founder_gm     = founder_gm_pct / 100 if founder_gm_pct is not None else None
    founder_ltvcac = getattr(kpis, "ltv_cac_ratio", None)     if kpis else None
    founder_cac    = getattr(kpis, "cac", None)               if kpis else None
    founder_arr    = getattr(kpis, "arr", None)               if kpis else (rev * 12 if rev else None)
    ltvcac_status  = getattr(kpis, "ltv_cac_status", "")      if kpis else ""
    gm_status      = getattr(kpis, "gross_margin_status", "")  if kpis else ""

    churn_med = getattr(bench, "churn_median", None)
    gm_med    = getattr(bench, "gross_margin_median", None)
    ev_mult   = getattr(bench, "valorisation_multiple", None)
    ltvcac_b  = extra.get("ltv_cac_ratio")
    payback_b = extra.get("cac_payback_months")
    nrr_b     = extra.get("nrr")
    growth_b  = extra.get("growth_yoy")

    badge = "Tavily live" if ("tavily" in source.lower()) else "ChromaDB cache"
    lines = [f"---\n### Positionnement sectoriel — {sector}\n"
             f"Similarité RAG : **{sim:.0%}** · {badge} · {len(docs)} doc(s)"]

    def _gap(f, b): return (f - b) / (abs(b) + 1e-9)
    def _x(v):      return f"{v:.1f}x" if v is not None else "—"

    metric_blocks = []

    # Gross Margin
    if gm_med is not None:
        fv_str = f"{founder_gm_pct:.1f}%" if founder_gm_pct is not None else "—"
        bv_str = f"{gm_med:.1%}"
        if founder_gm is not None:
            gap = _gap(founder_gm, gm_med)
            if abs(gap) < 0.05:
                status, desc = "Aligné", f"GM ({founder_gm_pct:.1f}%) alignée avec la médiane ({gm_med:.1%}). Cible SaaS B2B : > 70%."
            elif gap > 0:
                status, desc = "Au-dessus", f"GM ({founder_gm_pct:.1f}%) > médiane ({gm_med:.1%}) de {gap:.0%}. Signal de pricing power."
            else:
                status, desc = "En dessous", f"GM ({founder_gm_pct:.1f}%) < médiane ({gm_med:.1%}) de {abs(gap):.0%}. Revoir le COGS ou la tarification."
            icon = {"SAIN": "✓", "FAIBLE": "⚡", "CRITIQUE": "✗"}.get(gm_status, "→")
            metric_blocks.append((f"{icon} Gross Margin", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("Gross Margin", "—", bv_str, "—", f"Médiane sectorielle : {bv_str}."))

    # Churn
    if churn_med is not None and churn is not None:
        bv_str = f"{churn_med:.1%}"
        fv_str = f"{churn:.1%}"
        life   = round(1 / churn, 1) if churn > 0 else None
        gap    = _gap(churn, churn_med)
        if abs(gap) < 0.10:
            status, desc = "Aligné", f"Churn ({churn:.1%}) proche de la médiane ({bv_str}). Durée vie client : {life} mois."
        elif gap > 0:
            status, desc = "Au-dessus", f"Churn ({churn:.1%}) > médiane ({bv_str}). Priorité : onboarding 30/60/90j, health scores."
        else:
            status, desc = "En dessous", f"Churn ({churn:.1%}) < médiane — forte rétention. Durée vie client : {life} mois."
        metric_blocks.append(("Churn mensuel", fv_str, bv_str, status, desc))

    # LTV/CAC
    if ltvcac_b is not None:
        fv_str = _x(founder_ltvcac)
        bv_str = _x(ltvcac_b)
        if founder_ltvcac is not None:
            gap = _gap(founder_ltvcac, ltvcac_b)
            if abs(gap) < 0.10:
                status, desc = "Aligné", f"LTV/CAC {founder_ltvcac:.1f}x dans la norme ({ltvcac_b:.1f}x). Cible VC : > 3x."
            elif gap > 0:
                status, desc = "Au-dessus", f"LTV/CAC {founder_ltvcac:.1f}x > médiane ({ltvcac_b:.1f}x). Position favorable pour une levée."
            else:
                status, desc = "En dessous", f"LTV/CAC {founder_ltvcac:.1f}x < médiane ({ltvcac_b:.1f}x). Leviers : canaux organiques, upsell, réduction CAC."
            icon = {"SAIN": "✓", "LIMITE": "⚡", "DANGEREUX": "✗"}.get(ltvcac_status, "→")
            metric_blocks.append((f"{icon} LTV / CAC", fv_str, bv_str, status, desc))
        else:
            metric_blocks.append(("LTV / CAC", "—", bv_str, "—", f"Médiane : {bv_str}."))

    # EV/ARR Multiple
    if ev_mult is not None and founder_arr is not None:
        val_ref = founder_arr * ev_mult
        desc = f"Multiple EV/ARR médian : **{ev_mult:.1f}x**. Sur votre ARR ({fmt(founder_arr)} DT) → ~{fmt(val_ref)} DT indicatif."
        metric_blocks.append(("Valorisation EV/ARR", f"ARR {fmt(founder_arr)} DT", f"{ev_mult:.1f}x", f"~{fmt(val_ref)} DT", desc))

    # CAC Payback
    if payback_b is not None:
        desc = f"CAC payback médian : **{payback_b:.0f} mois**. SaaS B2B sain : < 12 mois."
        metric_blocks.append(("CAC Payback",
                               f"{fmt(founder_cac)} DT" if founder_cac else "—",
                               f"{payback_b:.0f} mois", "Référence", desc))

    # NRR
    if nrr_b is not None:
        metric_blocks.append(("NRR", "—", f"{nrr_b:.1f}%", "Référence",
                               f"NRR médian : **{nrr_b:.1f}%**. NRR > 100% = croissance auto-financée."))

    # Croissance YoY
    if growth_b is not None:
        metric_blocks.append(("Croissance ARR YoY", "—", f"{growth_b:.0f}%", "Référence",
                               f"Croissance ARR YoY médiane : **{growth_b:.0f}%**. Règle T2D3 pour Series A/B."))

    if not metric_blocks:
        lines.append("\n_Benchmarks insuffisants pour une comparaison complète._")
    else:
        lines += ["\n**Comparaison vs médiane sectorielle**\n",
                  "| Métrique | Votre valeur | Médiane | Positionnement |",
                  "|----------|-------------|---------|----------------|"]
        for name, fv, bv, status, _ in metric_blocks:
            lines.append(f"| {name} | {fv} | {bv} | {status} |")
        lines.append("")
        for name, _, _, _, desc in metric_blocks:
            lines.append(f"\n**{name.lstrip('✓✗⚡→ ')}** — {desc}")

    # Plan d'action
    lines.append("\n\n**Plan d'action prioritaire**\n")
    recs = []
    if gm_status == "CRITIQUE" or (founder_gm is not None and gm_med and founder_gm < gm_med * 0.80):
        recs.append("**[Pricing/COGS]** Gross margin insuffisante — auditez vos coûts variables et envisagez un abonnement annuel.")
    if churn is not None and churn_med is not None and churn > churn_med * 1.3:
        recs.append(f"**[Rétention]** Churn {churn:.1%} > médiane — onboarding 30/60/90j, health scores, exit interviews.")
    if ltvcac_status == "DANGEREUX":
        recs.append("**[Unit Economics]** LTV/CAC < 1x — couper les canaux inefficients, augmenter le prix moyen.")
    elif ltvcac_status == "LIMITE":
        recs.append("**[Scalabilité]** LTV/CAC < 3x — optimisez les canaux organiques (SEO, referral).")
    if ev_mult and founder_arr:
        recs.append(f"**[Valorisation]** ~{fmt(founder_arr * ev_mult)} DT indicatif. Cible : NRR > 110% + croissance > médiane.")
    if not recs:
        recs.append("Métriques dans la norme. Focus : accélérer la croissance ARR pour des multiples supérieurs.")
    for r in recs:
        lines.append(f"- {r}")

    return "\n".join(lines)
