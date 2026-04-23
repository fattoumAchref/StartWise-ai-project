"""
agent/tools/confidence_a2a.py
Unified confidence scoring + A2A message builder.

compute_confidence_score() → ConfidenceResult
build_a2a_message()        → A2AMessage  (to field populated by AgentRegistry at send time)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from models.data_models import (
    A2AMessage,
    BenchmarkResult,
    ConfidenceResult,
    FinancialContext,
    KPIResult,
    MonteCarloResult,
    Phase,
    ValidationResult,
)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIDENCE SCORE
# ─────────────────────────────────────────────────────────────────────────────

def compute_confidence_score(
    validation:  Optional[ValidationResult],
    monte_carlo: Optional[MonteCarloResult],
    kpis:        Optional[KPIResult],
) -> ConfidenceResult:
    """
    Compute a [0-1] confidence score from three components:

      data_quality   (×0.40) — reliability of raw inputs
      mc_tightness   (×0.35) — tightness of Monte Carlo P10/P90 spread
      llm_consistency(×0.25) — absence of logical incoherences

    Returns a ConfidenceResult with human-readable interpretation.
    """

    # ── Component 1 : Data Quality ────────────────────────────────────────────
    dq = getattr(validation, "data_quality_score", None)
    data_quality = float(dq) if dq is not None else 0.30

    # ── Component 2 : Monte Carlo Tightness ──────────────────────────────────
    mc_tight = getattr(monte_carlo, "mc_tightness", None)
    mc_tightness = float(mc_tight) if mc_tight is not None else 0.30

    # ── Component 3 : LLM / Logical Consistency ───────────────────────────────
    incoherences = getattr(validation, "incoherences", []) or []
    n = len(incoherences)
    if n == 0:
        llm_consistency = 1.00
    elif n == 1:
        llm_consistency = 0.65
    elif n == 2:
        llm_consistency = 0.35
    else:
        llm_consistency = 0.10

    # ── Weighted composite ────────────────────────────────────────────────────
    score = round(
        0.40 * data_quality +
        0.35 * mc_tightness +
        0.25 * llm_consistency,
        3,
    )

    # ── Interpretation ────────────────────────────────────────────────────────
    if score >= 0.70:
        niveau = "ÉLEVÉ"
        interpretation = (
            f"Confiance élevée ({score:.0%}) — projections financières fiables. "
            "Données de qualité, faible dispersion Monte Carlo."
        )
    elif score >= 0.45:
        niveau = "MOYEN"
        interpretation = (
            f"Confiance moyenne ({score:.0%}) — projections indicatives. "
            "Complétez les données manquantes pour améliorer la précision."
        )
    else:
        niveau = "FAIBLE"
        interpretation = (
            f"Confiance faible ({score:.0%}) — données incomplètes ou incohérentes. "
            "Interprétez les projections avec précaution."
        )

    return ConfidenceResult(
        score            = score,
        data_quality     = round(data_quality, 3),
        mc_tightness     = round(mc_tightness, 3),
        llm_consistency  = round(llm_consistency, 3),
        niveau           = niveau,
        interpretation   = interpretation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# A2A MESSAGE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_a2a_message(
    context:     FinancialContext,
    phase:       Optional[Phase],
    kpis:        Optional[KPIResult],
    monte_carlo: Optional[MonteCarloResult],
    benchmarks:  Optional[BenchmarkResult],
    confidence:  Optional[ConfidenceResult],
    project_id:  str = "",
    session_id:  str = "",
) -> A2AMessage:
    """
    Assemble the A2A message the financial agent sends downstream.
    The `to` field defaults to ["investment_agent"]; AgentRegistry updates it at send time.

    Usage:
        conf = compute_confidence_score(validation, mc, kpis)
        msg  = build_a2a_message(ctx, phase, kpis, mc, bench, conf)
        # → serialize msg and publish to the A2A bus
    """
    # ── Alertes ───────────────────────────────────────────────────────────────
    alertes: list[str] = list(getattr(kpis, "alertes", []) or [])

    cash_alert = getattr(kpis, "cash_out_alert", None)
    if cash_alert == "CRITIQUE":
        runway = getattr(kpis, "runway_months", "?")
        alertes.insert(0, f"🔴 RUNWAY CRITIQUE : {runway} mois — action immédiate requise")
    elif cash_alert == "ATTENTION":
        runway = getattr(kpis, "runway_months", "?")
        alertes.insert(0, f"🟠 RUNWAY ATTENTION : {runway} mois — préparer la levée")

    if confidence and confidence.niveau == "FAIBLE":
        alertes.insert(0, f"⚠ CONFIANCE FAIBLE : {confidence.interpretation}")

    # ── Priority from runway alert ────────────────────────────────────────────
    priority = "high" if cash_alert == "CRITIQUE" else \
               "medium" if cash_alert == "ATTENTION" else "low"

    # ── Confidence score (float) ──────────────────────────────────────────────
    confidence_score = round(confidence.score, 3) if confidence else 0.0

    # ── Payload : all financial data nested under payload.data ────────────────
    payload_data: dict = {
        "phase":   phase.value if isinstance(phase, Phase) else str(phase or "unknown"),
        "secteur": str(getattr(context, "secteur", "unknown") or "unknown"),
        "pays":    str(getattr(context, "pays", "TN") or "TN"),
        "alertes": alertes,
    }

    if kpis:
        payload_data["kpis"] = {
            "burn_net":           kpis.burn_net,
            "runway_months":      kpis.runway_months,
            "cash_out_alert":     kpis.cash_out_alert,
            "cac":                kpis.cac,
            "ltv":                kpis.ltv,
            "ltv_cac_ratio":      kpis.ltv_cac_ratio,
            "ltv_cac_status":     kpis.ltv_cac_status,
            "gross_margin_pct":   kpis.gross_margin_pct,
            "gross_margin_status": kpis.gross_margin_status,
            "mrr":                kpis.mrr,
            "arr":                kpis.arr,
            "breakeven_months":   kpis.breakeven_months,
            "breakeven_reachable": kpis.breakeven_reachable,
        }

    if monte_carlo:
        payload_data["monte_carlo"] = {
            "p10":              monte_carlo.p10,
            "p50":              monte_carlo.p50,
            "p90":              monte_carlo.p90,
            "proba_survie_12m": monte_carlo.proba_survie_12m,
            "proba_breakeven":  monte_carlo.proba_breakeven,
            "mc_tightness":     monte_carlo.mc_tightness,
        }

    if benchmarks:
        payload_data["benchmarks"] = {
            "cac_median":            benchmarks.cac_median,
            "ltv_median":            benchmarks.ltv_median,
            "churn_median":          benchmarks.churn_median,
            "gross_margin_median":   benchmarks.gross_margin_median,
            "valorisation_multiple": benchmarks.valorisation_multiple,
            "source":                benchmarks.source,
            "similarity_score":      benchmarks.similarity_score,
        }

    if confidence:
        payload_data["confidence_detail"] = {
            "score":           confidence.score,
            "data_quality":    confidence.data_quality,
            "mc_tightness":    confidence.mc_tightness,
            "llm_consistency": confidence.llm_consistency,
            "niveau":          confidence.niveau,
            "interpretation":  confidence.interpretation,
        }

    return A2AMessage(
        message_id = str(uuid.uuid4()),
        type       = "financial_analysis",
        from_agent = "finance_agent",
        to         = ["investment_agent"],   # populated dynamically by AgentRegistry at send time
        timestamp  = datetime.now(timezone.utc).isoformat(),
        context    = {
            "project_id": project_id or str(uuid.uuid4()),
            "session_id": session_id or str(uuid.uuid4()),
        },
        payload    = {"data": payload_data},
        confidence = confidence_score,
        metadata   = {
            "priority":           priority,
            "requires_response":  False,
            "tags":               [
                payload_data["phase"],
                payload_data["secteur"],
                payload_data["pays"],
            ],
        },
    )
