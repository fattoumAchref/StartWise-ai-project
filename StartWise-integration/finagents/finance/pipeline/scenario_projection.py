# tools/scenario_projection.py— Génération des 3 scénarios comparés
# Dépend de : calculate_kpis + run_monte_carlo

from dataclasses import dataclass, field
from typing import Optional
from finagents.models.data_models import (
    FinancialContext, KPIResult, MonteCarloResult, Phase
)


# ─────────────────────────────────────────
# MODÈLE DE SORTIE
# ─────────────────────────────────────────

@dataclass
class Scenario:
    nom:              str            # "pessimiste" | "réaliste" | "optimiste"
    growth_rate:      float          # taux croissance mensuel utilisé
    runway_months:    float          # runway estimé
    breakeven_months: Optional[float]# mois pour atteindre breakeven
    revenue_12m:      float          # revenus projetés dans 12 mois
    cash_12m:         float          # cash restant dans 12 mois
    survie_12m:       bool           # survit aux 12 prochains mois ?
    alerte:           str            # message principal


@dataclass
class ScenarioProjectionResult:
    pessimiste:  Scenario
    realiste:    Scenario
    optimiste:   Scenario
    recommandation: str              # conseil principal pour l'entrepreneur
    phase:       str                 # phase détectée
    horizon_mois: int                # horizon de projection


# ─────────────────────────────────────────
# TAUX DE CROISSANCE PAR SCÉNARIO
# ─────────────────────────────────────────

# Pessimiste : croissance nulle ou négative
# Réaliste   : benchmark sectoriel conservateur
# Optimiste  : hypothèse de l'entrepreneur (divisée par 2 pour réalisme)

GROWTH_RATES = {
    "food_delivery":  {"pessimiste": 0.00, "realiste": 0.08, "optimiste": 0.18},
    "saas":           {"pessimiste": 0.00, "realiste": 0.06, "optimiste": 0.15},
    "marketplace":    {"pessimiste": 0.00, "realiste": 0.10, "optimiste": 0.20},
    "ecommerce":      {"pessimiste": 0.00, "realiste": 0.07, "optimiste": 0.16},
    "default":        {"pessimiste": 0.00, "realiste": 0.08, "optimiste": 0.15},
}


def scenario_projection(
    context: FinancialContext,
    kpis: KPIResult,
    phase: Phase,
    mc: MonteCarloResult = None,
    horizon_mois: int = 24,
) -> ScenarioProjectionResult:
    """
    Génère 3 scénarios financiers comparés.

    pessimiste : croissance = 0% — que se passe-t-il si rien ne décolle ?
    réaliste   : croissance = benchmark sectoriel
    optimiste  : croissance = hypothèse entrepreneur ÷ 2

    Exemple :
        sp = scenario_projection(ctx, kpis, mc, Phase.SEED)
        sp.realiste.runway_months  → 8.5
        sp.pessimiste.survie_12m   → False
        sp.recommandation          → "Levez des fonds avant le mois 5"
    """

    cash    = context.cash_balance or 0.0
    burn    = context.burn_rate    or 0.0
    revenue = context.monthly_revenue or 0.0
    secteur = context.secteur.lower() if context.secteur else "default"

    # ── Taux de croissance ───────────────────────────────────
    rates = GROWTH_RATES.get(secteur, GROWTH_RATES["default"])

    # Pour l'optimiste : si l'entrepreneur a une hypothèse, on la prend
    # divisée par 2 pour rester réaliste, cap à 30%/mois (sinon les projections deviennent absurdes)
    hypothese_growth = _extract_growth_from_hypotheses(context.hypotheses)
    if hypothese_growth is not None:
        rates["optimiste"] = min(hypothese_growth / 2, 0.30)  # cap à 30%/mois

    # ── Générer les 3 scénarios ──────────────────────────────
    pessimiste = _simulate_scenario(
        "pessimiste", cash, burn, revenue,
        rates["pessimiste"], horizon_mois
    )
    realiste = _simulate_scenario(
        "réaliste", cash, burn, revenue,
        rates["realiste"], horizon_mois
    )
    optimiste = _simulate_scenario(
        "optimiste", cash, burn, revenue,
        rates["optimiste"], horizon_mois
    )

    # ── Recommandation principale ────────────────────────────
    recommandation = _build_recommandation(
        pessimiste, realiste, optimiste, phase, kpis
    )

    return ScenarioProjectionResult(
        pessimiste      = pessimiste,
        realiste        = realiste,
        optimiste       = optimiste,
        recommandation  = recommandation,
        phase           = phase.value,
        horizon_mois    = horizon_mois,
    )


# ─────────────────────────────────────────
# SIMULATION D'UN SCÉNARIO
# ─────────────────────────────────────────

def _simulate_scenario(
    nom: str,
    cash: float,
    burn: float,
    revenue: float,
    growth_rate: float,
    horizon_mois: int,
) -> Scenario:
    """Simule un seul scénario déterministe (pas de stochastique)."""

    cash_sim    = cash
    rev_sim     = revenue
    runway      = horizon_mois
    breakeven   = None

    for month in range(1, horizon_mois + 1):
        rev_sim  = rev_sim * (1 + growth_rate)
        net_flow = rev_sim - burn
        cash_sim = cash_sim + net_flow

        # Breakeven atteint ?
        if rev_sim >= burn and breakeven is None:
            breakeven = month

        # Cash épuisé ?
        if cash_sim <= 0:
            runway = month
            break

    cash_12m    = _simulate_cash_at_month(cash, burn, revenue, growth_rate, 12)
    revenue_12m = revenue * ((1 + growth_rate) ** 12)
    survie_12m  = runway >= 12

    if runway < horizon_mois:
        # La startup a manqué de cash pendant la simulation
        runway_final = runway
    else:
        # La startup a survécu tout l'horizon — runway basé sur l'état FINAL de la simulation
        # rev_sim et cash_sim reflètent la situation après horizon_mois mois de croissance
        burn_net_final = burn - rev_sim  # peut être négatif (startup rentable à la fin)
        if burn_net_final <= 0:
            runway_final = None  # cash-flow positif en fin de période — runway non applicable
        elif cash_sim > 0:
            runway_final = horizon_mois + round(cash_sim / burn_net_final, 1)
        else:
            runway_final = horizon_mois

    alerte = _build_alerte(nom, runway_final, breakeven, survie_12m)

    return Scenario(
        nom              = nom,
        growth_rate      = growth_rate,
        runway_months    = runway_final,
        breakeven_months = breakeven,
        revenue_12m      = round(revenue_12m, 0),
        cash_12m         = round(max(cash_12m, 0), 0),
        survie_12m       = survie_12m,
        alerte           = alerte,
    )


def _simulate_cash_at_month(
    cash: float, burn: float, revenue: float,
    growth: float, target_month: int
) -> float:
    """Calcule le cash restant à un mois précis."""
    c = cash
    r = revenue
    for _ in range(target_month):
        r = r * (1 + growth)
        c = c + (r - burn)
        if c <= 0:
            return 0.0
    return c


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _extract_growth_from_hypotheses(hypotheses: list) -> Optional[float]:
    """
    Cherche un taux de croissance dans les hypothèses textuelles.
    Ex: "je pense doubler mes clients" → 1.0 (100%)
        "croissance x2/mois"          → 1.0
    """
    for h in hypotheses:
        h_lower = h.lower()
        if "doubl" in h_lower or "x2" in h_lower or "×2" in h_lower:
            return 1.0
        if "tripl" in h_lower or "x3" in h_lower or "×3" in h_lower:
            return 2.0
        if "50%" in h_lower:
            return 0.50
        if "30%" in h_lower:
            return 0.30
        if "20%" in h_lower:
            return 0.20
    return None


def _build_alerte(
    nom: str, runway: float,
    breakeven: Optional[float], survie: bool
) -> str:
    if not survie:
        return (
            f"Scénario {nom} : cash épuisé dans {runway} mois. "
            "Financement nécessaire."
        )
    if breakeven is not None:
        return (
            f"Scénario {nom} : breakeven atteint au mois {breakeven}. "
            f"Runway de {runway} mois."
        )
    return (
        f"Scénario {nom} : survie sur {runway} mois "
        "mais breakeven non atteint."
    )


def _build_recommandation(
    pessimiste: Scenario,
    realiste: Scenario,
    optimiste: Scenario,
    phase: Phase,
    kpis: KPIResult,
) -> str:
    """Génère le conseil principal pour l'entrepreneur."""

    # Si même le réaliste ne survit pas 12 mois → urgence
    if not realiste.survie_12m:
        return (
            f"Urgence : dans le scénario réaliste vous manquez de cash "
            f"dans {realiste.runway_months} mois. "
            "Commencez à lever des fonds ou réduire le burn immédiatement."
        )

    # Si seul l'optimiste survit
    if not pessimiste.survie_12m and realiste.survie_12m:
        return (
            f"Situation fragile : vous survivez dans le scénario réaliste "
            f"({realiste.runway_months} mois) mais pas dans le pessimiste "
            f"({pessimiste.runway_months} mois). "
            "Sécurisez un financement ou réduisez les coûts variables."
        )

    # Si phase levée → recommandation valorisation
    if phase in (Phase.FUNDRAISING, Phase.SEED_RAISING):
        return (
            "Votre runway vous donne le temps de lever. "
            "Préparez votre dossier investisseur avec le scénario réaliste "
            "comme base et l'optimiste comme upside."
        )

    # Situation saine
    import math as _math
    run_str = (
        "cash-flow positif"
        if realiste.runway_months is None
        else f"{realiste.runway_months} mois"
    )
    return (
        f"Situation saine : runway réaliste de {run_str}. "
        "Concentrez-vous sur la croissance et la réduction du churn."
    )