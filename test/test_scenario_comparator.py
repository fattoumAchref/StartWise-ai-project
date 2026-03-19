# tests/test_scenario_comparator.py
# Lance avec : python test\test_scenario_comparator.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, Phase, DataQuality, BenchmarkResult
from tools.calculate_kpis import calculate_kpis
from tools.monte_carlo import run_monte_carlo
from tools.route_by_phase import route_by_phase
from tools.scenario_projection import scenario_projection
from tools.scenario_comparator import scenario_comparator


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


def _pipeline(ctx):
    """Lance tout le pipeline jusqu'aux scénarios."""
    kpis  = calculate_kpis(ctx)
    mc    = run_monte_carlo(ctx, kpis)
    phase = route_by_phase(ctx)
    sp    = scenario_projection(ctx, kpis, mc, phase)
    return kpis, mc, phase, sp


# ─────────────────────────────────────────
# TEST 1 — Score dans [0,1]
# ─────────────────────────────────────────
def test_score_bornes():
    print("\n── TEST 1 : Score dans [0,1] ─────────────────")

    ctx = FinancialContext(
        burn_rate=12000, cash_balance=80000, monthly_revenue=750,
        n_clients=15, prix_client=50, churn_rate=0.05,
        marketing_budget=2000, new_clients_month=8,
        secteur="food_delivery",
    )
    kpis, mc, phase, sp = _pipeline(ctx)
    result = scenario_comparator(ctx, kpis, sp)

    check("score dans [0,1]",
          0.0 <= result.score_vs_benchmark <= 1.0,
          result.score_vs_benchmark)

    check("scenario_recommande valide",
          result.scenario_recommande in ("pessimiste", "réaliste", "optimiste"),
          result.scenario_recommande)

    check("resume non vide",
          len(result.resume) > 0, result.resume)

    print(f"  → score={result.score_vs_benchmark}  "
          f"scénario={result.scenario_recommande}")


# ─────────────────────────────────────────
# TEST 2 — Startup saine vs benchmark
# LTV/CAC = 4.0 → AU_DESSUS du benchmark (3.0)
# ─────────────────────────────────────────
def test_startup_saine():
    print("\n── TEST 2 : Startup saine → LTV/CAC au-dessus ─")

    ctx = FinancialContext(
        burn_rate=12000, cash_balance=80000, monthly_revenue=750,
        n_clients=15, prix_client=50, churn_rate=0.05,
        marketing_budget=2000, new_clients_month=8,
        secteur="food_delivery",
    )
    kpis, mc, phase, sp = _pipeline(ctx)
    result = scenario_comparator(ctx, kpis, sp)

    ltv_cac_comp = next(
        (c for c in result.comparaisons if c.kpi_name == "LTV/CAC"), None
    )
    check("LTV/CAC = 4.0 → AU_DESSUS",
          ltv_cac_comp and ltv_cac_comp.statut == "AU_DESSUS",
          ltv_cac_comp.statut if ltv_cac_comp else None, "AU_DESSUS")

    print(f"  → LTV/CAC : {ltv_cac_comp.message if ltv_cac_comp else 'N/A'}")


# ─────────────────────────────────────────
# TEST 3 — Benchmarks fournis par Chroma
# ─────────────────────────────────────────
def test_avec_benchmarks_chroma():
    print("\n── TEST 3 : Avec benchmarks Chroma fournis ───")

    ctx = FinancialContext(
        burn_rate=12000, cash_balance=80000, monthly_revenue=750,
        n_clients=15, prix_client=50, churn_rate=0.05,
        marketing_budget=2000, new_clients_month=8,
        secteur="food_delivery",
    )

    # Benchmarks Chroma simulés
    bench = BenchmarkResult(
        cac_median=200, ltv_median=600, churn_median=0.07,
        gross_margin_median=30.0, source="Chroma — food delivery MENA 2024",
        similarity_score=0.87,
    )

    kpis, mc, phase, sp = _pipeline(ctx)
    result = scenario_comparator(ctx, kpis, sp, benchmarks=bench)

    check("source = Chroma",
          "Chroma" in result.benchmark_source,
          result.benchmark_source)

    check("5 comparaisons produites",
          len(result.comparaisons) == 5,
          len(result.comparaisons), 5)

    print(f"  → source : {result.benchmark_source}")
    print(f"  → {len(result.comparaisons)} comparaisons")


# ─────────────────────────────────────────
# TEST 4 — Startup mauvais KPIs → score bas
# ─────────────────────────────────────────
def test_startup_mauvaise():
    print("\n── TEST 4 : Mauvais KPIs → score bas ─────────")

    ctx = FinancialContext(
        burn_rate=15000, cash_balance=20000, monthly_revenue=500,
        n_clients=5, prix_client=100, churn_rate=0.30,  # churn très élevé
        marketing_budget=5000, new_clients_month=1,     # CAC très élevé
        secteur="food_delivery",
    )
    kpis, mc, phase, sp = _pipeline(ctx)
    result = scenario_comparator(ctx, kpis, sp)

    check("score < 0.5 si mauvais KPIs",
          result.score_vs_benchmark < 0.5,
          result.score_vs_benchmark, "< 0.5")

    check("des points faibles identifiés",
          len(result.points_faibles) > 0,
          result.points_faibles)

    print(f"  → score={result.score_vs_benchmark}")
    print(f"  → points faibles : {result.points_faibles}")


# ─────────────────────────────────────────
# TEST 5 — Pipeline complet (5 outils)
# ─────────────────────────────────────────
def test_pipeline_complet():
    print("\n── TEST 5 : Pipeline complet (5 outils) ──────")

    ctx = FinancialContext(
        burn_rate         = 12000,
        cash_balance      = 80000,
        monthly_revenue   = 750,
        n_clients         = 15,
        prix_client       = 50,
        churn_rate        = 0.05,
        marketing_budget  = 2000,
        new_clients_month = 8,
        secteur           = "food_delivery",
        burn_quality      = DataQuality.ESTIMATED,
        cash_quality      = DataQuality.REAL,
        revenue_quality   = DataQuality.REAL,
    )

    try:
        kpis, mc, phase, sp = _pipeline(ctx)
        result = scenario_comparator(ctx, kpis, sp)

        check("pipeline sans erreur",       True, "OK")
        check("comparaisons non vides",
              len(result.comparaisons) > 0, result.comparaisons)
        check("resume non vide",
              len(result.resume) > 0,       result.resume)

        print(f"\n  ══ Rapport final — Startup Tunis ══")
        print(f"  Phase             : {phase.value}")
        print(f"  Score benchmark   : {result.score_vs_benchmark*100:.0f}%")
        print(f"  Scénario conseillé: {result.scenario_recommande}")
        print(f"  Résumé            : {result.resume}")
        print(f"  Points forts  ({len(result.points_forts)}) :")
        for p in result.points_forts:
            print(f"    ✓ {p}")
        print(f"  Points faibles ({len(result.points_faibles)}) :")
        for p in result.points_faibles:
            print(f"    ✗ {p}")
        print(f"\n  ── Comparaisons détaillées ──")
        for c in result.comparaisons:
            print(f"    {c.statut:15} {c.message}")

    except Exception as e:
        check("pipeline sans erreur", False, str(e))


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — scenario_comparator")
    print("=" * 50)

    test_score_bornes()
    test_startup_saine()
    test_avec_benchmarks_chroma()
    test_startup_mauvaise()
    test_pipeline_complet()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = Financial Modeling Engine complet.")
    print("=" * 50)