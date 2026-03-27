import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, Phase, DataQuality
from tools.calculate_kpis import calculate_kpis
from tools.monte_carlo import run_monte_carlo
from tools.route_by_phase import route_by_phase
from tools.scenario_projection import scenario_projection


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


# ─────────────────────────────────────────
# TEST 1 — Ordre logique des scénarios
# pessimiste <= réaliste <= optimiste
# ─────────────────────────────────────────
def test_ordre_scenarios():
    print("\n── TEST 1 : Ordre pessimiste ≤ réaliste ≤ optimiste ──")

    ctx   = FinancialContext(burn_rate=12000, cash_balance=80000,
                             monthly_revenue=750, secteur="food_delivery")
    kpis  = calculate_kpis(ctx)
    mc    = run_monte_carlo(ctx, kpis)
    phase = route_by_phase(ctx)
    sp    = scenario_projection(ctx, kpis, mc, phase)

    check("runway pessimiste <= réaliste",
          sp.pessimiste.runway_months <= sp.realiste.runway_months,
          f"{sp.pessimiste.runway_months} > {sp.realiste.runway_months}")

    check("runway réaliste <= optimiste",
          sp.realiste.runway_months <= sp.optimiste.runway_months,
          f"{sp.realiste.runway_months} > {sp.optimiste.runway_months}")

    check("growth pessimiste = 0",
          sp.pessimiste.growth_rate == 0.0,
          sp.pessimiste.growth_rate, 0.0)

    check("growth optimiste > réaliste",
          sp.optimiste.growth_rate > sp.realiste.growth_rate,
          f"{sp.optimiste.growth_rate} <= {sp.realiste.growth_rate}")

    print(f"  → runway : pess={sp.pessimiste.runway_months}  "
          f"real={sp.realiste.runway_months}  "
          f"opti={sp.optimiste.runway_months}")


# ─────────────────────────────────────────
# TEST 2 — Startup critique
# Même l'optimiste ne survit pas
# ─────────────────────────────────────────
def test_startup_critique():
    print("\n── TEST 2 : Startup critique ─────────────────")

    ctx   = FinancialContext(burn_rate=20000, cash_balance=15000,
                             monthly_revenue=1000)
    kpis  = calculate_kpis(ctx)
    mc    = run_monte_carlo(ctx, kpis)
    phase = route_by_phase(ctx)
    sp    = scenario_projection(ctx, kpis, mc, phase)

    check("pessimiste ne survit pas 12m",
          not sp.pessimiste.survie_12m,
          sp.pessimiste.survie_12m, False)

    check("recommandation mentionne urgence",
          "urgence" in sp.recommandation.lower() or
          "immédiatement" in sp.recommandation.lower(),
          sp.recommandation)

    print(f"  → recommandation : {sp.recommandation}")


# ─────────────────────────────────────────
# TEST 3 — Startup profitable
# Tous les scénarios survivent
# ─────────────────────────────────────────
def test_startup_profitable():
    print("\n── TEST 3 : Startup profitable ───────────────")

    ctx   = FinancialContext(burn_rate=10000, cash_balance=100000,
                             monthly_revenue=15000)
    kpis  = calculate_kpis(ctx)
    mc    = run_monte_carlo(ctx, kpis)
    phase = route_by_phase(ctx)
    sp    = scenario_projection(ctx, kpis, mc, phase)

    check("pessimiste survit 12m",
          sp.pessimiste.survie_12m, sp.pessimiste.survie_12m, True)
    check("réaliste survit 12m",
          sp.realiste.survie_12m, sp.realiste.survie_12m, True)
    check("optimiste survit 12m",
          sp.optimiste.survie_12m, sp.optimiste.survie_12m, True)

    print(f"  → tous survivent ✓")


# ─────────────────────────────────────────
# TEST 4 — Hypothèse doublement
# Growth optimiste ajustée
# ─────────────────────────────────────────
def test_hypothese_doublement():
    print("\n── TEST 4 : Hypothèse doublement ─────────────")

    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        hypotheses      = ["je pense doubler mes clients chaque mois"],
    )
    kpis  = calculate_kpis(ctx)
    mc    = run_monte_carlo(ctx, kpis)
    phase = route_by_phase(ctx)
    sp    = scenario_projection(ctx, kpis, mc, phase)

    # doublement → 100%/mois → divisé par 2 = 50% pour l'optimiste
    check("growth optimiste = 0.5 si doublement",
          sp.optimiste.growth_rate == 0.5,
          sp.optimiste.growth_rate, 0.5)

    check("revenue_12m optimiste >> réaliste",
          sp.optimiste.revenue_12m > sp.realiste.revenue_12m,
          f"{sp.optimiste.revenue_12m} <= {sp.realiste.revenue_12m}")

    print(f"  → growth opti={sp.optimiste.growth_rate}")
    print(f"  → revenue 12m : real={sp.realiste.revenue_12m}  "
          f"opti={sp.optimiste.revenue_12m}")


# ─────────────────────────────────────────
# TEST 5 — Enchaînement complet
# Les 4 outils s'enchaînent sans erreur
# ─────────────────────────────────────────
def test_enchaînement_complet():
    print("\n── TEST 5 : Enchaînement complet (4 outils) ──")

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
        kpis  = calculate_kpis(ctx)
        mc    = run_monte_carlo(ctx, kpis)
        phase = route_by_phase(ctx)
        sp    = scenario_projection(ctx, kpis, mc, phase)

        check("enchaînement sans erreur", True, "OK")
        check("3 scénarios produits",
              all([sp.pessimiste, sp.realiste, sp.optimiste]), "OK")
        check("recommandation non vide",
              len(sp.recommandation) > 0, sp.recommandation)
        check("phase = seed",
              sp.phase == "seed", sp.phase, "seed")

        print(f"\n  ══ Résumé startup Tunis ══")
        print(f"  Phase           : {sp.phase}")
        print(f"  Pessimiste      : runway={sp.pessimiste.runway_months}m  "
              f"survie12m={sp.pessimiste.survie_12m}")
        print(f"  Réaliste        : runway={sp.realiste.runway_months}m  "
              f"survie12m={sp.realiste.survie_12m}")
        print(f"  Optimiste       : runway={sp.optimiste.runway_months}m  "
              f"survie12m={sp.optimiste.survie_12m}")
        print(f"  Recommandation  : {sp.recommandation}")

    except Exception as e:
        check("enchaînement sans erreur", False, str(e))


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — scenario_projection")
    print("=" * 50)

    test_ordre_scenarios()
    test_startup_critique()
    test_startup_profitable()
    test_hypothese_doublement()
    test_enchaînement_complet()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt pour la suite.")
    print("Un ✗ FAIL = bug à corriger avant de continuer.")
    print("=" * 50)