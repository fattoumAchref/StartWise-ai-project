"""
api/cfo_engine.py
=================
CFO Agent business logic — orchestrates LLM calls, pipeline runs,
context merging, ideation detection, and what-if simulations.

This is the brain of the FinAgent CFO module.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, replace
from typing import Any

logger = logging.getLogger(__name__)

# ── External module imports (finagents) ───────────────────────────────────────

try:
    from finagents.finance.tools.parser import parse_founder_input
    from finagents.finance.tools.validator import validate_financial_context
    from finagents.finance.tools.benchmark_fetcher import fetch_benchmarks
    from finagents.finance.pipeline.orchestrator import run_analysis_pipeline
    MODULES_OK = True
except Exception as _e:
    logger.error("FinAgent modules unavailable: %s", _e)
    MODULES_OK = False


# ── Detection helpers ─────────────────────────────────────────────────────────

def has_financial_data(ctx: Any) -> bool:
    """Return True if ctx contains at least one real financial field."""
    if ctx is None:
        return False
    for f in ("burn_rate", "cash_balance", "monthly_revenue", "n_clients",
              "prix_client", "churn_rate", "marketing_budget"):
        if getattr(ctx, f, None) is not None:
            return True
    return False


def is_ideation_message(prompt: str) -> bool:
    """Detect messages that come from the ideation tunnel (no real data yet)."""
    triggers = [
        "viabilite financiere", "idee de startup", "tunnel d'ideation",
        "business ideation", "## business idea",
        "benchmarks sectoriels pour les hypotheses", "key insights",
        "contexte issu de l'idéation", "contexte issu de l'ideation",
        "mon projet de startup", "startwise_summary", "business title",
    ]
    lower = prompt.lower()
    return any(t in lower for t in triggers)


# Field → keyword mapping used by both _filter_agent_questions and process_ctx.
# Extracted at module level so process_ctx can derive field names from question texts
# when populating already_asked for a new task.
FIELD_COVERAGE: dict[str, list[str]] = {
    "burn_rate": [
        "burn", "dépens", "depens", "charges mensuelles", "coûts mensuel",
        "couts mensuel", "dépenses totales", "depenses totales",
    ],
    "cash_balance": [
        "cash", "trésorerie", "tresorerie", "solde", "banque disponible",
        "liquidité", "liquidite",
    ],
    "monthly_revenue": [
        "revenu mensuel", "chiffre d'affaires", "chiffre d affaires",
        "c.a.", " ca ", "rentrée", "rentree", "revenus mensuels",
    ],
    "n_clients": [
        "combien de clients", "nombre de clients", "abonnés", "abonnes",
        "utilisateurs actifs", "clients actifs", "clients payants",
    ],
    "prix_client": [
        "prix ", "tarif", "ticket moyen", "abonnement mensuel", "prix moyen",
    ],
    "churn_rate": [
        "churn", "attrition", "perdez des clients", "résiliation", "resiliation",
        "taux de rétention", "taux de retention",
    ],
    "secteur": [
        "secteur d'activit", "secteur d activit", "domaine d'activit",
        "type d'activit", "secteur d'activite", "secteur d activite",
    ],
    "pays": [
        "pays cibl", "pays cible", "marché géograph", "marche geograph",
        "marché cible", "localisation", "région géograph",
    ],
}


def _filter_agent_questions(questions: list, ctx: Any, state: dict) -> list:
    """Remove already-asked and known-field questions from FinanceAgent clarification list.

    Prevents:
    - Repeating questions across turns (dedup via state["asked_questions"])
    - Asking about fields already set in the financial context (field-level coverage,
      not text-exact — catches same concept rephrased differently)
    """
    asked = state.get("asked_questions", set())
    if isinstance(asked, list):
        asked = set(asked)

    # Build a set of keyword groups to suppress based on what ctx already has
    suppressed_keywords: list[list[str]] = []
    for field, keywords in FIELD_COVERAGE.items():
        if getattr(ctx, field, None) is not None:
            suppressed_keywords.append(keywords)

    filtered = []
    for q in questions:
        if not q or q in asked:
            continue
        q_lower = q.lower()
        skip = False
        # Field-level suppression: already answered, any phrasing
        for kw_group in suppressed_keywords:
            if any(kw in q_lower for kw in kw_group):
                skip = True
                break
        if not skip:
            filtered.append(q)

    # Limit to 3 new questions per turn and register them as asked
    result = filtered[:3]
    asked.update(result)
    state["asked_questions"] = list(asked)
    return result


def extract_ideation_sector(prompt: str) -> str:
    """Use the parser LLM to detect the sector from an ideation summary."""
    if not MODULES_OK:
        return ""
    try:
        ctx = parse_founder_input(prompt)
        return ctx.secteur or ""
    except Exception:
        return ""

def build_ideation_preanalysis(prompt: str) -> str:
    """Generate a contextual CFO pre-analysis from ideation context only."""
    sector = extract_ideation_sector(prompt)
    sector_hint = f"Secteur détecté: {sector}. " if sector else ""
    rag_hint = ""
    if MODULES_OK:
        try:
            ctx = parse_founder_input(prompt)
            bench = fetch_benchmarks(ctx)
            if bench is not None:
                churn_med = getattr(bench, "churn_median", None)
                gm_med = getattr(bench, "gross_margin_median", None)
                ev_mult = getattr(bench, "valorisation_multiple", None)
                docs = list(getattr(bench, "documents_raw", []) or [])
                snippets = []
                for d in docs[:2]:
                    s = str(d).strip().replace("\n", " ")
                    if s:
                        snippets.append(s[:220])
                rag_bits = []
                if churn_med is not None:
                    rag_bits.append(f"churn median ~ {churn_med:.1%}")
                if gm_med is not None:
                    rag_bits.append(f"gross margin median ~ {gm_med:.1%}")
                if ev_mult is not None:
                    rag_bits.append(f"EV/ARR ~ {ev_mult:.1f}x")
                if snippets:
                    rag_bits.append("signals docs: " + " | ".join(snippets))
                if rag_bits:
                    rag_hint = "Benchmark/RAG disponible: " + "; ".join(rag_bits) + ". "
        except Exception as exc:
            logger.debug("Ideation preanalysis benchmark hint unavailable: %s", exc)

    system_prompt = (
        "Tu es FinAgent, CFO stratégique de StartWise. "
        "On te donne un contexte d'idéation sans chiffres comptables réels. "
        "Tu dois produire une pré-analyse utile, contextuelle et actionnable (pas de message générique). "
        "Format obligatoire en français avec sections markdown:\n"
        "## Lecture du projet\n"
        "## Viabilité initiale (hypothèses explicites)\n"
        "## Go-to-market & traction attendue\n"
        "## Risques majeurs + actions immédiates\n"
        "## Données minimales à fournir pour lancer la simulation complète\n"
        "Règles:\n"
        "- Utiliser les éléments du contexte fourni.\n"
        "- Si des signaux Benchmark/RAG sont fournis, les exploiter explicitement dans l'analyse.\n"
        "- Donner des hypothèses chiffrées plausibles (fourchettes) et indiquer clairement qu'elles sont des hypothèses.\n"
        "- Pas de phrase 'idée reçue'.\n"
        "- Être précis, utile, orienté décision.\n"
        f"{sector_hint}{rag_hint}"
    )
    reply = call_llm(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=900,
    )
    return reply or (
        "## Lecture du projet\n"
        "Le contexte d'ideation est bien recu.\n\n"
        "## Viabilite initiale (hypotheses explicites)\n"
        "Hypothese provisoire: structure de couts legere en phase d'amorcage et monetisation progressive.\n\n"
        "## Go-to-market & traction attendue\n"
        "Prioriser une niche testable, acquisition organique + partenariats locaux.\n\n"
        "## Risques majeurs + actions immediates\n"
        "Risque principal: absence de preuve de traction; action: definir ICP, proposition de valeur et premiers KPI.\n\n"
        "## Donnees minimales a fournir pour lancer la simulation complete\n"
        "- Revenus mensuels estimes\n- Burn rate mensuel\n- Tresorerie disponible\n- Nombre de clients et prix moyen"
    )


# ── Context merging ───────────────────────────────────────────────────────────

def merge_contexts(existing: Any, new: Any) -> Any:
    """Merge two FinancialContext objects, keeping non-None fields from both."""
    if existing is None:
        return new
    if new is None:
        return existing
    try:
        from finagents.models.data_models import FinancialContext, DataQuality
        e = asdict(existing)
        n = asdict(new)
        merged = dict(e)
        for k, v in n.items():
            if k == "revenue_history":
                old_h = e.get("revenue_history") or []
                new_h = v or []
                seen  = {tuple(x.items()) if isinstance(x, dict) else x for x in old_h}
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
                try:   merged[qf] = DataQuality[val]
                except KeyError: pass
            elif isinstance(val, dict) and "value" in val:
                try:   merged[qf] = DataQuality(val["value"])
                except (ValueError, KeyError): pass
        return FinancialContext(**{k: v for k, v in merged.items()
                                   if k in FinancialContext.__dataclass_fields__})
    except Exception as exc:
        logger.warning("merge_contexts failed: %s", exc)
        return new


# ── LLM call ─────────────────────────────────────────────────────────────────

def call_llm(messages: list, max_tokens: int = 800) -> str:
    """Low-level LLM call via the Esprit Token Factory API."""
    import httpx
    key = os.getenv("ESPRIT_API_KEY", "")
    if not key:
        return ""
    try:
        r = httpx.post(
            "https://tokenfactory.esprit.tn/api/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("ESPRIT_MODEL",
                                   os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct")),
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=45.0,
            verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return ""


# ── CFO general answer ────────────────────────────────────────────────────────

def answer_general(prompt: str, ctx: Any) -> str:
    """Answer a general question using the CFO LLM persona.

    The system prompt enforces structured ## sections so the frontend
    can render bento-grid tiles instead of a wall of text.
    """
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

    system_prompt = (
        "Tu es FinAgent, le CFO IA de la plateforme StartWise pour startups tunisiennes. "
        "RÈGLE D'OR : structure TOUJOURS ta réponse en 2 à 4 sections courtes avec des titres ## markdown. "
        "Format obligatoire :\n"
        "## [Titre]\n[contenu concis, listes à puces]\n## [Titre]\n[contenu]\n"
        "Utilise **gras** pour les chiffres clés. Jamais de bloc de texte non structuré. "
        "Réponds en français."
        + (f"\n{ctx_str}" if ctx_str else "")
    )

    reply = call_llm([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": prompt},
    ])
    return reply or "Je n'ai pas pu traiter votre requête pour le moment."


# ── What-if simulation ────────────────────────────────────────────────────────

def run_whatif(prompt: str, ctx: Any) -> str:
    """Simulate a hypothetical scenario by modifying ctx fields and re-running pipeline."""
    if ctx is None:
        return "Veuillez d'abord fournir vos données financières."
    if not MODULES_OK:
        return answer_general(prompt, ctx)

    try:
        ctx_dict = asdict(ctx)
    except Exception:
        return answer_general(prompt, ctx)

    nums = {k: v for k, v in ctx_dict.items()
            if isinstance(v, (int, float)) and k in (
                "burn_rate", "cash_balance", "monthly_revenue", "n_clients",
                "prix_client", "churn_rate", "marketing_budget", "cogs", "new_clients_month"
            )}

    raw = call_llm([
        {"role": "system", "content": (
            "Détecte si la requête est une simulation hypothétique. "
            'Si oui: {"is_whatif":true,"modifications":{"field":{"op":"multiply|add|set","factor":N,"value":N}}} '
            'Sinon: {"is_whatif":false,"modifications":{}}. JSON uniquement.'
        )},
        {"role": "user", "content": f"Données: {json.dumps(nums)}\nRequête: {prompt}"},
    ], max_tokens=300)

    try:
        start  = raw.find("{"); end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])
        if not parsed.get("is_whatif"):
            return answer_general(prompt, ctx)
        mods = parsed.get("modifications", {})
    except Exception:
        return answer_general(prompt, ctx)

    new_vals: dict = {}
    for field, op_dict in mods.items():
        current = getattr(ctx, field, None)
        if current is None:
            continue
        op = op_dict.get("op", "multiply")
        try:
            if op == "multiply": new_vals[field] = current * float(op_dict.get("factor", 1))
            elif op == "add":    new_vals[field] = current + float(op_dict.get("value", 0))
            elif op == "set":    new_vals[field] = float(op_dict.get("value", current))
        except (TypeError, ValueError):
            pass

    if not new_vals:
        return answer_general(prompt, ctx)

    from cfo.formatters import fmt
    try:
        old_res = run_analysis_pipeline(ctx)
        new_res = run_analysis_pipeline(replace(ctx, **new_vals))
        lines   = ["## Simulation What-If\n", "**Modifications :**"]
        for field, val in new_vals.items():
            lines.append(f"- {field}: {fmt(getattr(ctx, field, '?'))} → {fmt(val)}")

        lines.append("\n## Impact KPIs")
        ok = old_res.get("kpis")
        nk = new_res.get("kpis")
        if ok and nk:
            old_rw = getattr(ok, "runway_months", None)
            new_rw = getattr(nk, "runway_months", None)
            if old_rw and new_rw:
                d = new_rw - old_rw
                lines.append(f"- **Runway** : {old_rw:.1f}m → **{new_rw:.1f}m** ({'↑' if d > 0 else '↓'} {d:+.1f}m)")
            old_gm = getattr(ok, "gross_margin", None)
            new_gm = getattr(nk, "gross_margin", None)
            if old_gm and new_gm:
                lines.append(f"- **Gross Margin** : {old_gm:.1%} → **{new_gm:.1%}**")
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("what-if pipeline failed: %s", exc)
        return answer_general(prompt, ctx)


# ── Main pipeline orchestrator ────────────────────────────────────────────────

def process_ctx(state: dict, new_ctx: Any, raw_text: str) -> tuple:
    """Merge context, run pipeline (or full agent), fetch benchmarks.

    Returns (data_text, questions, bench).
    Side-effects: mutates `state` with analysis results.
    """
    from cfo.session_manager import get_finance_agent, get_comm_agent, get_a2a_classes
    from cfo.formatters import format_extracted, format_benchmark_result, parse_docs_extra

    FA  = get_finance_agent()
    CA  = get_comm_agent()
    cls = get_a2a_classes()

    merged = merge_contexts(state.get("financial_context"), new_ctx)

    if CA is not None:
        try:
            CA.store_financial_context(merged)
        except Exception:
            pass

    bench = None

    # ── Path A : Full FinanceAgent loop ───────────────────────────────────
    if FA is not None and cls and raw_text.strip():
        Task = cls["Task"]; TaskStatus = cls["TaskStatus"]
        Message = cls["Message"]; TextPart = cls["TextPart"]

        new_msg      = Message(role="user", parts=[TextPart(text=raw_text)])
        existing_task = state.get("agent_task")
        fresh         = state.get("_agent_fresh", False)

        if (existing_task and
                getattr(getattr(existing_task, "status", None), "state", "") == "input-required"
                and not fresh):
            # Give the agent the accumulated context so it doesn't re-ask about
            # fields already confirmed in earlier turns (agent re-parses from text
            # on each continue_task call and can miss previously confirmed values).
            existing_task.metadata["_parent_context"] = merged
            existing_task.add_message(new_msg)
            result_task = FA.continue_task(existing_task)
        else:
            state.pop("a2a_publish_time", None)
            task_id = str(uuid.uuid4())
            state["_agent_task_id"] = task_id
            task = Task(id=task_id, status=TaskStatus(state="submitted"), messages=[new_msg])
            # Carry session-level asked_questions into the new task.
            # IMPORTANT: also derive field NAMES from question texts so
            # _reason_about_missing_data (which checks field names, not question texts)
            # correctly skips fields that were asked in a previous task.
            session_asked = state.get("asked_questions", [])
            if session_asked or merged is not None:
                field_names_from_questions: set = set()
                for q in session_asked:
                    ql = q.lower()
                    for field, keywords in FIELD_COVERAGE.items():
                        if any(kw in ql for kw in keywords):
                            field_names_from_questions.add(field)
                # Fields already confirmed in the accumulated context are also "asked"
                for field in FIELD_COVERAGE:
                    if merged is not None and getattr(merged, field, None) is not None:
                        field_names_from_questions.add(field)
                task.metadata["already_asked"] = list(
                    set(session_asked)
                    | set(task.metadata.get("already_asked", []))
                    | field_names_from_questions
                )
            # Pass accumulated context so agent can fill in fields parser misses
            task.metadata["_parent_context"] = merged
            result_task = FA.process_task(task)

        state["agent_task"]  = result_task
        state["_agent_fresh"] = False

        agent_ctx  = result_task.metadata.get("_context", merged)
        # Re-merge with the accumulated state context: the agent re-parses from text
        # on every turn and can miss fields confirmed in previous turns (especially on
        # short block answers). merged has the union of all confirmed fields.
        ctx = merge_contexts(merged, agent_ctx)
        # Write the enriched context back so the agent sees it on the next continue
        result_task.metadata["_context"] = ctx

        validation = result_task.metadata.get("_validation")
        analysis   = result_task.metadata.get("_analysis") or {}
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
                            raw_qs = [l.lstrip("•-* ").strip()
                                      for l in part.text.splitlines()
                                      if l.strip() and len(l.strip()) > 8]
                            # Pass the enriched ctx so field-level suppression works
                            # even when the agent's fresh parse missed a field
                            questions = _filter_agent_questions(raw_qs, ctx, state)
                            break
                    break

        state["financial_context"] = ctx
        state["validation_result"] = validation
        state["analysis"]          = analysis

        if benchmarks is None and getattr(validation, "is_valid", False):
            try:
                benchmarks = fetch_benchmarks(ctx)
            except Exception:
                benchmarks = None

        if benchmarks is not None and getattr(benchmarks, "source", "unavailable") != "unavailable":
            bench = benchmarks
            state["last_bench"]       = bench
            state["last_bench_extra"] = parse_docs_extra(
                list(getattr(bench, "documents_raw", []) or [])
            )

        # Only signal the frontend to poll for investment agent results when the
        # finance agent actually COMPLETED the pipeline (not when it's still
        # collecting data in input-required state). Broadcasting on every partial
        # answer would spam the investment agent and show a polling spinner for
        # every single block answer the user provides.
        task_completed = getattr(getattr(result_task, "status", None), "state", "") == "completed"
        if CA and os.getenv("A2A_BUS_URL") and task_completed:
            state["a2a_publish_time"]    = time.time()
            state["awaiting_clarification"] = False

        data_text  = format_extracted(ctx, validation, analysis)
        bench_text = format_benchmark_result(bench, ctx, analysis) if bench is not None else ""
        state["last_bench_text"] = bench_text
        return data_text, questions, bench

    # ── Path B : Direct pipeline fallback ─────────────────────────────────
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

    if bench is not None and getattr(bench, "source", "unavailable") != "unavailable":
        state["last_bench"]       = bench
        state["last_bench_extra"] = parse_docs_extra(
            list(getattr(bench, "documents_raw", []) or [])
        )

    state["financial_context"] = merged

    questions: list = []
    if validation:
        qs      = getattr(validation, "questions_to_ask", []) or []
        missing = getattr(validation, "missing_critical", []) or []
        # Filter out already-asked questions — agent remembers across turns
        asked = state.get("asked_questions", set())
        if isinstance(asked, list):
            asked = set(asked)
        fresh_qs = [q for q in qs if q not in asked]
        if fresh_qs:
            asked.update(fresh_qs[:3])
            state["asked_questions"] = list(asked)
            questions = fresh_qs[:3]
        else:
            # All dynamic questions already asked — fall back to missing field hints
            missing_hints = [f"Pouvez-vous préciser votre {m} ?" for m in missing[:2]
                             if f"Pouvez-vous préciser votre {m} ?" not in asked]
            asked.update(missing_hints)
            state["asked_questions"] = list(asked)
            questions = missing_hints

    data_text  = format_extracted(merged, validation, analysis)
    bench_text = format_benchmark_result(bench, merged, analysis) if bench is not None else ""
    state["last_bench_text"] = bench_text

    if CA and os.getenv("A2A_BUS_URL"):
        state["a2a_publish_time"] = time.time()

    return data_text, questions, bench
