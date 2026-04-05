"""
calcul_tools/pipeline.py
Chaîne les outils de calcul disponibles depuis le Founder Chat Flow.
Retourne un dict avec tous les résultats, chaque étape étant indépendante des erreurs.
"""

from __future__ import annotations
import logging
from typing import Any, Optional

from models.data_models import BenchmarkResult, FinancialContext

logger = logging.getLogger(__name__)


def run_analysis_pipeline(
    context:    FinancialContext,
    benchmarks: Optional[BenchmarkResult] = None,
) -> dict:
    """
    Exécute le pipeline complet d'analyse financière à partir d'un FinancialContext.

    Étapes :
        1. validate_inputs     → ValidationResult
        2. calculate_kpis      → KPIResult          (si burn_rate + cash_balance présents)
        3. route_by_phase      → Phase + active_models
        4. scenario_projection → ScenarioProjectionResult
        5. monte_carlo         → MonteCarloResult
        6. seasonality_trend   → SeasonalityResult  (data-driven gating)
        7. scenario_comparator → ScenarioComparatorResult (si benchmarks fournis)
        8. confidence + A2A    → ConfidenceResult + A2AMessage

    Paramètres :
        context    : FinancialContext extrait par le parser
        benchmarks : BenchmarkResult optionnel (depuis fetch_benchmarks) — active step 7

    Retourne un dict avec les clés :
        validation, kpis, monte_carlo, phase, active_models, scenarios,
        seasonality, comparator, confidence, a2a_message
    """

    result: dict[str, Any] = {
        "validation":    None,
        "kpis":          None,
        "monte_carlo":   None,
        "phase":         None,
        "active_models": None,
        "scenarios":     None,
        "seasonality":   None,
        "comparator":    None,
        "confidence":    None,
        "a2a_message":   None,
    }

    # ── 1. Validation ──────────────────────────────────────────────────────────
    try:
        from calcul_tools.validate_inputs import validate_inputs
        result["validation"] = validate_inputs(context)
    except Exception as e:
        logger.warning("pipeline step 1 (validate_inputs) failed: %s", e)

    # Les étapes suivantes nécessitent burn_rate et cash_balance
    has_minimum = (
        getattr(context, "burn_rate", None) is not None
        and getattr(context, "cash_balance", None) is not None
    )

    if not has_minimum:
        return result

    # ── 2. KPIs ────────────────────────────────────────────────────────────────
    try:
        from calcul_tools.calculate_kpis import calculate_kpis
        result["kpis"] = calculate_kpis(context)
    except Exception as e:
        logger.warning("pipeline step 2 (calculate_kpis) failed: %s", e)

    if result["kpis"] is None:
        return result

    # ── 3. Phase ───────────────────────────────────────────────────────────────
    try:
        from calcul_tools.route_by_phase import route_by_phase, get_active_models
        phase = route_by_phase(context)
        result["phase"] = phase
        result["active_models"] = get_active_models(phase)
    except Exception as e:
        logger.warning("pipeline step 3 (route_by_phase) failed: %s", e)

    # ── 4. Scénarios (avant MC pour extraire le taux de croissance réaliste) ───
    if result["phase"] is not None:
        try:
            from calcul_tools.scenario_projection import scenario_projection
            result["scenarios"] = scenario_projection(
                context,
                result["kpis"],
                result["phase"],
            )
        except Exception as e:
            logger.warning("pipeline step 4 (scenario_projection) failed: %s", e)

    # ── 5. Monte Carlo ────────────────────────────────────────────────────────
    try:
        from calcul_tools.monte_carlo import run_monte_carlo
        realistic_growth = None
        if result["scenarios"] is not None:
            realistic_growth = getattr(result["scenarios"].realiste, "growth_rate", None)
        result["monte_carlo"] = run_monte_carlo(
            context, result["kpis"], growth_mean=realistic_growth
        )
    except Exception as e:
        logger.warning("pipeline step 5 (monte_carlo) failed: %s", e)

    # ── 6. Seasonality (data-driven gating — always runs if revenue present) ──
    has_revenue = (
        getattr(context, "monthly_revenue", None) is not None
        or bool(getattr(context, "revenue_history", []))
    )
    if has_revenue:
        try:
            from calcul_tools.seasonality_trend import seasonality_trend
            result["seasonality"] = seasonality_trend(
                context,
                revenue_history=getattr(context, "revenue_history", []) or [],
                phase=result.get("phase"),
            )
        except Exception as e:
            logger.warning("pipeline step 6 (seasonality_trend) failed: %s", e)

    # ── 7. Scenario Comparator (requires benchmarks) ───────────────────────────
    if benchmarks is not None and result["kpis"] and result["scenarios"]:
        try:
            from calcul_tools.scenario_comparator import scenario_comparator
            result["comparator"] = scenario_comparator(
                context,
                result["kpis"],
                result["scenarios"],
                benchmarks,
            )
        except Exception as e:
            logger.warning("pipeline step 7 (scenario_comparator) failed: %s", e)

    # ── 8. Confidence score + A2A message ─────────────────────────────────────
    try:
        from agent.tools.confidence_a2a import compute_confidence_score, build_a2a_message
        result["confidence"] = compute_confidence_score(
            result["validation"],
            result["monte_carlo"],
            result["kpis"],
        )
        result["a2a_message"] = build_a2a_message(
            context,
            result["phase"],
            result["kpis"],
            result["monte_carlo"],
            benchmarks,
            result["confidence"],
        )
    except Exception as e:
        logger.warning("pipeline step 8 (confidence/a2a) failed: %s", e)

    return result
