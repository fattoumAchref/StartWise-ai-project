# tools/scenario_comparator.py— Comparaison scénarios vs benchmarks Chroma
# Dépend de : scenario_projection + benchmarks Chroma

from dataclasses import dataclass
from typing import Optional
from finagents.models.data_models import (
    FinancialContext, KPIResult, BenchmarkResult,
)
from finagents.finance.pipeline.scenario_projection import ScenarioProjectionResult

# TND/USD approximate exchange rate — used to convert USD benchmark defaults to local currency.
# Update annually. Source: Banque Centrale de Tunisie (BCT) average.
_TND_PER_USD: float = 3.10

# ─────────────────────────────────────────
# MODÈLE DE SORTIE
# ─────────────────────────────────────────

@dataclass
class KPIComparison:
    """Comparaison d'un KPI entre la startup et le benchmark."""
    kpi_name:       str
    valeur_startup: Optional[float]
    valeur_bench:   Optional[float]
    statut:         str     # "AU_DESSUS" | "EN_DESSOUS" | "DANS_LA_NORME" | "N/A"
    ecart_pct:      Optional[float]  # % d'écart par rapport au benchmark
    message:        str


@dataclass
class ScenarioComparatorResult:
    comparaisons:       list            # liste de KPIComparison
    score_vs_benchmark: float           # [0-1] — 1 = meilleur que le benchmark
    scenario_recommande: str            # "pessimiste" | "réaliste" | "optimiste"
    resume:             str             # résumé en une phrase
    points_forts:       list            # ce qui est au-dessus du benchmark
    points_faibles:     list            # ce qui est en-dessous
    benchmark_source:   str             # source des benchmarks utilisés


# ─────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────

def scenario_comparator(
    context: FinancialContext,
    kpis: KPIResult,
    scenarios: ScenarioProjectionResult,
    benchmarks: Optional[BenchmarkResult] = None,
) -> ScenarioComparatorResult:
    """
    Compare les KPIs de la startup avec les benchmarks sectoriels.
    Si benchmarks=None → utilise des benchmarks par défaut selon le secteur.

    Exemple :
        result = scenario_comparator(ctx, kpis, scenarios, benchmarks)
        result.score_vs_benchmark  → 0.65
        result.points_forts        → ["LTV/CAC au-dessus de la norme"]
        result.scenario_recommande → "réaliste"
    """

    # ── Benchmarks par défaut si Chroma n'a rien retourné ───
    bench = benchmarks or _default_benchmarks(context.secteur)

    # ── Comparer chaque KPI ──────────────────────────────────
    comparaisons = []

    comparaisons.append(_compare_kpi(
        "CAC",
        kpis.cac, bench.cac_median,
        lower_is_better=True,
        unité="DT",
    ))

    comparaisons.append(_compare_kpi(
        "LTV",
        kpis.ltv, bench.ltv_median,
        lower_is_better=False,
        unité="DT",
    ))

    comparaisons.append(_compare_kpi(
        "Churn mensuel",
        context.churn_rate * 100 if context.churn_rate else None,
        bench.churn_median * 100 if bench.churn_median else None,
        lower_is_better=True,
        unité="%",
    ))

    comparaisons.append(_compare_kpi(
        "Gross margin",
        kpis.gross_margin_pct,
        bench.gross_margin_median,
        lower_is_better=False,
        unité="%",
    ))

    # LTV/CAC — benchmark universel : >= 3
    ltv_cac_comp = _compare_ltv_cac(kpis.ltv_cac_ratio)
    comparaisons.append(ltv_cac_comp)

    # ── Score global ─────────────────────────────────────────
    scores_valides = [c for c in comparaisons if c.statut != "N/A"]
    if scores_valides:
        n_positifs = sum(
            1 for c in scores_valides
            if c.statut in ("AU_DESSUS", "DANS_LA_NORME")
        )
        score = round(n_positifs / len(scores_valides), 2)
    else:
        score = 0.5

    # ── Points forts et faibles ──────────────────────────────
    points_forts   = [c.message for c in comparaisons if c.statut == "AU_DESSUS"]
    points_faibles = [c.message for c in comparaisons if c.statut == "EN_DESSOUS"]

    # ── Scénario recommandé ──────────────────────────────────
    scenario_rec = _recommend_scenario(scenarios, score)

    # ── Résumé ───────────────────────────────────────────────
    resume = _build_resume(score, points_forts, points_faibles, scenario_rec)

    return ScenarioComparatorResult(
        comparaisons        = comparaisons,
        score_vs_benchmark  = score,
        scenario_recommande = scenario_rec,
        resume              = resume,
        points_forts        = points_forts,
        points_faibles      = points_faibles,
        benchmark_source    = bench.source,
    )


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _compare_kpi(
    nom: str,
    valeur: Optional[float],
    benchmark: Optional[float],
    lower_is_better: bool,
    unité: str = "",
) -> KPIComparison:
    """Compare un KPI avec son benchmark."""

    if valeur is None or benchmark is None or benchmark == 0:
        return KPIComparison(
            kpi_name        = nom,
            valeur_startup  = valeur,
            valeur_bench    = benchmark,
            statut          = "N/A",
            ecart_pct       = None,
            message         = f"{nom} : données insuffisantes pour comparer",
        )

    ecart_pct = round((valeur - benchmark) / benchmark * 100, 1)

    # Tolérance de ±15% pour "dans la norme"
    tolerance = 15.0

    if abs(ecart_pct) <= tolerance:
        statut = "DANS_LA_NORME"
    elif lower_is_better:
        statut = "AU_DESSUS" if ecart_pct < 0 else "EN_DESSOUS"
    else:
        statut = "AU_DESSUS" if ecart_pct > 0 else "EN_DESSOUS"

    direction = "mieux" if statut == "AU_DESSUS" else \
                "moins bien" if statut == "EN_DESSOUS" else "dans la norme"

    message = (
        f"{nom} : {round(valeur, 1)}{unité} vs benchmark {round(benchmark, 1)}{unité} "
        f"({direction}, écart {ecart_pct:+.1f}%)"
    )

    return KPIComparison(
        kpi_name        = nom,
        valeur_startup  = valeur,
        valeur_bench    = benchmark,
        statut          = statut,
        ecart_pct       = ecart_pct,
        message         = message,
    )


def _compare_ltv_cac(ltv_cac_ratio: Optional[float]) -> KPIComparison:
    """LTV/CAC — benchmark universel >= 3."""
    if ltv_cac_ratio is None:
        return KPIComparison(
            kpi_name="LTV/CAC", valeur_startup=None,
            valeur_bench=3.0, statut="N/A", ecart_pct=None,
            message="LTV/CAC : non calculable"
        )

    if ltv_cac_ratio >= 3.0:
        statut = "AU_DESSUS"
        msg = f"LTV/CAC : {ltv_cac_ratio} ≥ 3.0 — modèle économique sain"
    elif ltv_cac_ratio >= 1.0:
        statut = "DANS_LA_NORME"
        msg = f"LTV/CAC : {ltv_cac_ratio} — correct mais visez > 3"
    else:
        statut = "EN_DESSOUS"
        msg = f"LTV/CAC : {ltv_cac_ratio} < 1 — vous perdez de l'argent sur chaque client"

    return KPIComparison(
        kpi_name        = "LTV/CAC",
        valeur_startup  = ltv_cac_ratio,
        valeur_bench    = 3.0,
        statut          = statut,
        ecart_pct       = round((ltv_cac_ratio - 3.0) / 3.0 * 100, 1),
        message         = msg,
    )


def _recommend_scenario(
    scenarios: ScenarioProjectionResult,
    score: float,
) -> str:
    """Choisit le scénario à présenter à l'investisseur."""
    # Score élevé → on peut présenter l'optimiste
    if score >= 0.7 and scenarios.optimiste.survie_12m:
        return "optimiste"
    # Score moyen → réaliste
    if scenarios.realiste.survie_12m:
        return "réaliste"
    # Score bas → on présente quand même le réaliste avec des notes
    return "réaliste"


def _build_resume(
    score: float,
    points_forts: list,
    points_faibles: list,
    scenario_rec: str,
) -> str:
    if score >= 0.7:
        return (
            f"Startup au-dessus des benchmarks sectoriels ({int(score*100)}%). "
            f"Présentez le scénario {scenario_rec}. "
            f"Points forts : {', '.join(points_forts[:2]) if points_forts else 'solides'}."
        )
    if score >= 0.4:
        return (
            f"Startup dans la moyenne sectorielle ({int(score*100)}%). "
            f"Travaillez sur : {', '.join(points_faibles[:2]) if points_faibles else 'les KPIs'}."
        )
    return (
        f"Startup en-dessous des benchmarks ({int(score*100)}%). "
        f"Priorités : {', '.join(points_faibles[:2]) if points_faibles else 'améliorer les KPIs'}."
    )


def _default_benchmarks(secteur: str) -> BenchmarkResult:
    """Benchmarks par défaut selon le secteur — valeurs converties en TND (×3.10)."""
    secteur = (secteur or "default").lower()
    r = _TND_PER_USD

    benchmarks = {
        "saas": BenchmarkResult(
            cac_median=round(300 * r), ltv_median=round(1200 * r), churn_median=0.05,
            gross_margin_median=70.0, valorisation_multiple=6.0,
            source="SaaStr benchmarks 2024 (converti en TND)"
        ),
        "food_delivery": BenchmarkResult(
            cac_median=round(150 * r), ltv_median=round(450 * r), churn_median=0.08,
            gross_margin_median=25.0, valorisation_multiple=2.5,
            source="Food delivery MENA benchmarks 2024 (converti en TND)"
        ),
        "marketplace": BenchmarkResult(
            cac_median=round(200 * r), ltv_median=round(800 * r), churn_median=0.06,
            gross_margin_median=40.0, valorisation_multiple=4.0,
            source="Marketplace benchmarks 2024 (converti en TND)"
        ),
        "ecommerce": BenchmarkResult(
            cac_median=round(180 * r), ltv_median=round(540 * r), churn_median=0.07,
            gross_margin_median=35.0, valorisation_multiple=2.0,
            source="E-commerce benchmarks 2024 (converti en TND)"
        ),
        "fintech": BenchmarkResult(
            cac_median=round(350 * r), ltv_median=round(1750 * r), churn_median=0.04,
            gross_margin_median=55.0, valorisation_multiple=7.0,
            source="Fintech benchmarks 2024 (converti en TND)"
        ),
        "edtech": BenchmarkResult(
            cac_median=round(120 * r), ltv_median=round(480 * r), churn_median=0.06,
            gross_margin_median=60.0, valorisation_multiple=4.5,
            source="EdTech benchmarks 2024 (converti en TND)"
        ),
        "hrtech": BenchmarkResult(
            cac_median=round(280 * r), ltv_median=round(1120 * r), churn_median=0.05,
            gross_margin_median=55.0, valorisation_multiple=5.0,
            source="HRTech benchmarks 2024 (converti en TND)"
        ),
    }

    default = BenchmarkResult(
        cac_median=round(250 * r), ltv_median=round(750 * r), churn_median=0.06,
        gross_margin_median=45.0, valorisation_multiple=3.0,
        source="Benchmarks généraux startups early-stage 2024 (converti en TND)"
    )

    return benchmarks.get(secteur, default)