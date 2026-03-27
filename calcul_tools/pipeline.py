"""
calcul_tools/pipeline.py
Chaîne les 5 outils de calcul disponibles depuis le Founder Chat Flow.
Retourne un dict avec tous les résultats, chaque étape étant indépendante des erreurs.
"""

from __future__ import annotations
from typing import Any

from models.data_models import FinancialContext


def run_analysis_pipeline(context: FinancialContext) -> dict:
    """
    Exécute le pipeline complet d'analyse financière à partir d'un FinancialContext.

    Étapes :
        1. validate_inputs   → ValidationResult
        2. calculate_kpis    → KPIResult          (si burn_rate + cash_balance présents)
        3. run_monte_carlo   → MonteCarloResult   (si kpis disponibles)
        4. route_by_phase    → Phase + active_models
        5. scenario_projection → ScenarioProjectionResult (si kpis + mc disponibles)

    Retourne un dict avec les clés :
        validation, kpis, monte_carlo, phase, active_models, scenarios
    """

    result: dict[str, Any] = {
        "validation":    None,
        "kpis":          None,
        "monte_carlo":   None,
        "phase":         None,
        "active_models": None,
        "scenarios":     None,
    }

    # ── 1. Validation ──────────────────────────────────────────────────────────
    try:
        from calcul_tools.validate_inputs import validate_inputs
        result["validation"] = validate_inputs(context)
    except Exception:
        pass

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
    except Exception:
        pass

    if result["kpis"] is None:
        return result

    # ── 3. Phase ───────────────────────────────────────────────────────────────
    try:
        from calcul_tools.route_by_phase import route_by_phase, get_active_models
        phase = route_by_phase(context)
        result["phase"] = phase
        result["active_models"] = get_active_models(phase)
    except Exception:
        pass

    # ── 4. Scénarios (avant MC pour extraire le taux de croissance réaliste) ───
    if result["phase"] is not None:
        try:
            from calcul_tools.scenario_projection import scenario_projection
            result["scenarios"] = scenario_projection(
                context,
                result["kpis"],
                result["phase"],
            )
        except Exception:
            pass

    # ── 5. Monte Carlo (utilise le taux réaliste des scénarios) ────────────────
    try:
        from calcul_tools.monte_carlo import run_monte_carlo
        realistic_growth = None
        if result["scenarios"] is not None:
            realistic_growth = getattr(result["scenarios"].realiste, "growth_rate", None)
        result["monte_carlo"] = run_monte_carlo(
            context, result["kpis"], growth_mean=realistic_growth
        )
    except Exception:
        pass

    return result
