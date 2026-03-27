# tests/test_run_monte_carlo.py
# Lance avec : python tests\test_run_monte_carlo.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, DataQuality
from tools.calculate_kpis import calculate_kpis
from tools.monte_carlo import run_monte_carlo


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


def test_ordre_percentiles():
    print("\n── TEST 1 : Ordre P10 <= P50 <= P90 ────────")
    ctx  = FinancialContext(burn_rate=12000, cash_balance=80000, monthly_revenue=750, secteur="food_delivery")
    kpis = calculate_kpis(ctx)
    mc   = run_monte_carlo(ctx, kpis)

    check("P10 <= P50",      mc.p10 <= mc.p50, f"{mc.p10} > {mc.p50}")
    check("P50 <= P90",      mc.p50 <= mc.p90, f"{mc.p50} > {mc.p90}")
    check("P10 >= 0",        mc.p10 >= 0,       mc.p10)
    check("P90 <= 24 mois",  mc.p90 <= 24,      mc.p90)
    print(f"  → P10={mc.p10}  P50={mc.p50}  P90={mc.p90}")


def test_startup_critique():
    print("\n── TEST 2 : Startup critique → survie basse ─")
    # 20k cash, 12k burn net → survit ~1-2 mois
    ctx  = FinancialContext(burn_rate=15000, cash_balance=20000, monthly_revenue=3000)
    kpis = calculate_kpis(ctx)
    mc   = run_monte_carlo(ctx, kpis)

    check("P50 <= 3 mois",         mc.p50 <= 3,            mc.p50, "<= 3")
    check("Survie 12m < 20%",      mc.proba_survie_12m < 0.20, mc.proba_survie_12m, "< 0.20")
    print(f"  → P50={mc.p50}  survie12m={mc.proba_survie_12m*100:.1f}%")


def test_startup_profitable():
    print("\n── TEST 3 : Startup profitable → survie 100% ─")
    ctx  = FinancialContext(burn_rate=10000, cash_balance=100000, monthly_revenue=15000)
    kpis = calculate_kpis(ctx)
    mc   = run_monte_carlo(ctx, kpis)

    check("P10 = P50 = P90 = 24",  mc.p10 == 24 and mc.p50 == 24 and mc.p90 == 24,
          f"P10={mc.p10} P50={mc.p50} P90={mc.p90}", "tous = 24")
    check("Survie 12m = 100%",     mc.proba_survie_12m == 1.0, mc.proba_survie_12m, 1.0)
    check("Breakeven = 100%",      mc.proba_breakeven == 1.0,  mc.proba_breakeven,  1.0)


def test_probas_dans_bornes():
    print("\n── TEST 4 : Probabilités dans [0,1] ────────")
    ctx  = FinancialContext(burn_rate=8000, cash_balance=60000, monthly_revenue=2000)
    kpis = calculate_kpis(ctx)
    mc   = run_monte_carlo(ctx, kpis)

    check("proba_survie dans [0,1]",   0 <= mc.proba_survie_12m <= 1, mc.proba_survie_12m)
    check("proba_breakeven dans [0,1]", 0 <= mc.proba_breakeven <= 1,  mc.proba_breakeven)
    check("mc_tightness dans [0,1]",   0 <= mc.mc_tightness <= 1,     mc.mc_tightness)


def test_tightness_logique():
    print("\n── TEST 5 : Tightness cohérente ─────────────")
    # Startup avec données très certaines → tightness haute
    ctx_certain = FinancialContext(
        burn_rate=10000, cash_balance=100000, monthly_revenue=15000
    )
    # Startup avec beaucoup d'incertitude (peu de cash)
    ctx_incertain = FinancialContext(
        burn_rate=12000, cash_balance=80000, monthly_revenue=750
    )

    kpis_c = calculate_kpis(ctx_certain)
    kpis_i = calculate_kpis(ctx_incertain)

    mc_c = run_monte_carlo(ctx_certain,   kpis_c)
    mc_i = run_monte_carlo(ctx_incertain, kpis_i)

    check("Profitable → tightness >= incertain",
          mc_c.mc_tightness >= mc_i.mc_tightness,
          f"certain={mc_c.mc_tightness} incertain={mc_i.mc_tightness}")
    print(f"  → tightness certain={mc_c.mc_tightness}  incertain={mc_i.mc_tightness}")


def test_enchaînement_avec_calculate_kpis():
    print("\n── TEST 6 : Enchaînement calculate_kpis → run_monte_carlo ──")
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
        kpis = calculate_kpis(ctx)
        mc   = run_monte_carlo(ctx, kpis)
        check("enchaînement sans erreur",    True, "OK")
        check("n_simulations = 1000",        mc.n_simulations == 1000, mc.n_simulations, 1000)
        check("résultats non None",          all([
            mc.p10 is not None, mc.p50 is not None, mc.p90 is not None
        ]), "un résultat est None")
        print(f"  → P10={mc.p10}  P50={mc.p50}  P90={mc.p90}")
        print(f"  → Survie 12m : {mc.proba_survie_12m*100:.1f}%")
        print(f"  → Breakeven  : {mc.proba_breakeven*100:.1f}%")
        print(f"  → Tightness  : {mc.mc_tightness}")
    except Exception as e:
        check("enchaînement sans erreur", False, str(e))


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — run_monte_carlo")
    print("=" * 50)

    test_ordre_percentiles()
    test_startup_critique()
    test_startup_profitable()
    test_probas_dans_bornes()
    test_tightness_logique()
    test_enchaînement_avec_calculate_kpis()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt pour la suite.")
    print("Un ✗ FAIL = bug à corriger avant de continuer.")
    print("=" * 50)