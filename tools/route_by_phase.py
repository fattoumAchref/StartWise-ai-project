# tools/route_by_phase.py
# Aucun LLM — Aucun mot-clé — Logique pure sur champs numériques
# La détection d'intention est faite EN AMONT par extract_financials (LLM)

from models.data_models import FinancialContext, Phase


def route_by_phase(context: FinancialContext) -> Phase:
    """
    Détecte la phase depuis les champs numériques + flag booléen.
    Ne fait aucune analyse textuelle.

    Priorité :
    1. intent_fundraising=True + traction  → FUNDRAISING
    2. intent_fundraising=True + pas traction → SEED_RAISING
    3. revenue > 0 ET months_data >= 6    → TRACTION
    4. sinon                              → SEED
    """
    intent      = context.intent_fundraising or False
    revenue     = context.monthly_revenue or 0.0
    months      = context.months_data or 0
    has_revenue = revenue > 0
    has_history = months >= 6

    if intent:
        if has_revenue and has_history:
            return Phase.FUNDRAISING
        return Phase.SEED_RAISING

    if has_revenue and has_history:
        return Phase.TRACTION

    return Phase.SEED


def get_active_models(phase: Phase) -> dict:
    """Retourne les modèles à activer selon la phase."""
    return {
        Phase.SEED: {
            "use_monte_carlo": True,
            "use_parametric":  True,
            "use_prophet":     False,
            "use_dcf":         False,
            "use_cap_table":   False,
        },
        Phase.TRACTION: {
            "use_monte_carlo": True,
            "use_parametric":  False,
            "use_prophet":     True,
            "use_dcf":         False,
            "use_cap_table":   False,
        },
        Phase.FUNDRAISING: {
            "use_monte_carlo": True,
            "use_parametric":  False,
            "use_prophet":     True,
            "use_dcf":         True,
            "use_cap_table":   True,
        },
        Phase.SEED_RAISING: {
            "use_monte_carlo": True,
            "use_parametric":  True,
            "use_prophet":     False,
            "use_dcf":         True,
            "use_cap_table":   True,
        },
    }[phase]