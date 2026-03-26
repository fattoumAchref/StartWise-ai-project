# tools/monte_carlo.py  — Simulation probabiliste
# Aucun LLM ici — numpy + maths

import numpy as np
from models.data_models import FinancialContext, KPIResult, MonteCarloResult


def run_monte_carlo(
    context: FinancialContext,
    kpis: KPIResult,
    n_simulations: int = 1000,
    n_months: int = 24,
    growth_mean: float = None,
    growth_std: float = 0.15,
    burn_volatility: float = 0.12,
) -> MonteCarloResult:
    """
    Simule n_simulations futurs possibles pour la startup.
    Retourne P10/P50/P90 du runway et probabilités clés.

    growth_std=0.15 → incertitude réaliste pour early-stage
    burn_volatility=0.12 → burn peut varier de ±12%/mois

    Exemple :
        mc = run_monte_carlo(ctx, kpis)
        mc.p10 → runway pessimiste (10% des futurs pire que ça)
        mc.p50 → runway médian
        mc.p90 → runway optimiste (10% des futurs mieux que ça)
    """

    cash     = context.cash_balance or 0.0
    burn     = context.burn_rate    or 0.0
    revenue  = context.monthly_revenue or 0.0
    burn_net = max(kpis.burn_net, 0.0)

    # ── Cas trivial : déjà profitable ───────────────────────
    if burn_net == 0:
        return MonteCarloResult(
            p10=n_months, p50=n_months, p90=n_months,
            proba_survie_12m=1.0, proba_breakeven=1.0,
            mc_tightness=1.0, n_simulations=n_simulations,
        )

    # ── Cas trivial : plus de cash ───────────────────────────
    if cash <= 0:
        return MonteCarloResult(
            p10=0, p50=0, p90=0,
            proba_survie_12m=0.0, proba_breakeven=0.0,
            mc_tightness=1.0, n_simulations=n_simulations,
        )

    # ── Taux de croissance — doit être fourni par le pipeline (scénario réaliste)
    # Fallback conservateur si non fourni
    if growth_mean is None:
        growth_mean = 0.05

    # ── Matrices aléatoires (vectorisé) ─────────────────────
    np.random.seed(None)

    growth_matrix = np.random.normal(
        loc=growth_mean, scale=growth_std,
        size=(n_simulations, n_months)
    )
    burn_shocks = np.clip(
        np.random.normal(1.0, burn_volatility, (n_simulations, n_months)),
        0.5, 2.0
    )

    # ── Simulation ──────────────────────────────────────────
    runways         = []
    breakeven_flags = []

    for sim in range(n_simulations):
        cash_sim   = cash
        rev_sim    = revenue
        runway_sim = n_months
        reached_be = False

        for month in range(n_months):
            rev_sim  = max(rev_sim * (1 + growth_matrix[sim, month]), 0.0)
            burn_sim = burn * burn_shocks[sim, month]

            if rev_sim >= burn_sim and not reached_be:
                reached_be = True

            cash_sim += rev_sim - burn_sim

            if cash_sim <= 0:
                runway_sim = month + 1
                break

        runways.append(runway_sim)
        breakeven_flags.append(reached_be)

    # ── Percentiles ─────────────────────────────────────────
    ra  = np.array(runways)
    p10 = int(np.percentile(ra, 10))
    p50 = int(np.percentile(ra, 50))
    p90 = int(np.percentile(ra, 90))

    proba_survie_12m = round(float(np.mean(ra >= 12)), 3)
    proba_breakeven  = round(float(np.mean(breakeven_flags)), 3)

    # ── Tightness : 1 = très serré (fiable), 0 = très large ─
    interval     = p90 - p10
    mc_tightness = round(1.0 - min(interval / n_months, 1.0), 3)

    return MonteCarloResult(
        p10=p10, p50=p50, p90=p90,
        proba_survie_12m=proba_survie_12m,
        proba_breakeven=proba_breakeven,
        mc_tightness=mc_tightness,
        n_simulations=n_simulations,
        growth_mean_used=growth_mean,
    )