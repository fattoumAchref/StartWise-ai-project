# tests/test_all_tools.py
# Lance avec : python test\test_all_tools.py
# Teste les 7 outils en séquence

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import (
    FinancialContext, Phase, DataQuality, BenchmarkResult
)
from tools.validate_inputs    import validate_inputs
from tools.route_by_phase     import route_by_phase, get_active_models
from tools.calculate_kpis     import calculate_kpis
from tools.monte_carlo    import run_monte_carlo
from tools.scenario_projection import scenario_projection
from tools.seasonality_trend  import seasonality_trend, RevenueDataPoint
from tools.scenario_comparator import scenario_comparator


def check(nom, condition, obtenu="", attendu=""):
    if condition:
        print(f"  ✓ {nom}")
    else:
        print(f"  ✗ FAIL — {nom}  |  obtenu:{obtenu}  attendu:{attendu}")


# ── Startup de base ────────────────────────────────────────────────────
CTX = FinancialContext(
    burn_rate=12000, cash_balance=80000, monthly_revenue=750,
    n_clients=15, prix_client=50, churn_rate=0.05,
    marketing_budget=2000, new_clients_month=8,
    secteur="food_delivery", months_data=0,
    intent_fundraising=False,
    burn_quality=DataQuality.ESTIMATED,
    cash_quality=DataQuality.REAL,
    revenue_quality=DataQuality.REAL,
)


def test_validate():
    print("\n══ validate_inputs ══════════════")
    r = validate_inputs(CTX)
    check("is_valid = True",             r.is_valid)
    check("data_quality_score = 0.9",    r.data_quality_score == 0.9)
    check("aucune incohérence",          len(r.incoherences) == 0)
    # Données manquantes
    r2 = validate_inputs(FinancialContext())
    check("tout None → is_valid=False",  not r2.is_valid)
    check("questions générées",          len(r2.questions_to_ask) >= 2)
    # Churn invalide
    r3 = validate_inputs(FinancialContext(burn_rate=1000, cash_balance=5000, churn_rate=50))
    check("churn>1 → incohérence",       len(r3.incoherences) > 0)


def test_route():
    print("\n══ route_by_phase ═══════════════")
    check("seed si 0 mois data",         route_by_phase(CTX) == Phase.SEED)
    check("traction si 6m+",             route_by_phase(FinancialContext(
        monthly_revenue=5000, months_data=8)) == Phase.TRACTION)
    check("fundraising si intent+traction", route_by_phase(FinancialContext(
        monthly_revenue=5000, months_data=8, intent_fundraising=True)) == Phase.FUNDRAISING)
    check("seed_raising si intent+seed", route_by_phase(FinancialContext(
        monthly_revenue=0, intent_fundraising=True)) == Phase.SEED_RAISING)
    check("sans flag → SEED même avec texte", route_by_phase(FinancialContext(
        monthly_revenue=0, intent_fundraising=False,
        hypotheses=["je cherche des investisseurs"])) == Phase.SEED)
    m = get_active_models(Phase.SEED)
    check("SEED → parametric+MC uniquement",
          m["use_parametric"] and m["use_monte_carlo"] and not m["use_prophet"])


def test_kpis():
    print("\n══ calculate_kpis ═══════════════")
    r = calculate_kpis(CTX)
    check("burn_net = 11250",            r.burn_net == 11250)
    check("runway ≈ 7.1",               6.9 <= r.runway_months <= 7.3)
    check("LTV = 1000",                  r.ltv == 1000.0)
    check("CAC = 250",                   r.cac == 250.0)
    check("LTV/CAC = 4.0 SAIN",         r.ltv_cac_ratio == 4.0 and r.ltv_cac_status == "SAIN")
    check("MRR = 750",                   r.mrr == 750)
    # Cas extrêmes
    r2 = calculate_kpis(FinancialContext(burn_rate=0, cash_balance=50000))
    check("burn=0 → runway=inf",         r2.runway_months == float('inf'))
    r3 = calculate_kpis(FinancialContext())
    check("tout None ne plante pas",     r3 is not None)


def test_monte_carlo():
    print("\n══ run_monte_carlo ══════════════")
    kpis = calculate_kpis(CTX)
    mc   = run_monte_carlo(CTX, kpis)
    check("P10 <= P50 <= P90",           mc.p10 <= mc.p50 <= mc.p90)
    check("probas dans [0,1]",           0 <= mc.proba_survie_12m <= 1)
    check("tightness dans [0,1]",        0 <= mc.mc_tightness <= 1)
    check("n_simulations = 1000",        mc.n_simulations == 1000)
    # Profitable → 100%
    kpis3 = calculate_kpis(FinancialContext(burn_rate=10000, cash_balance=100000, monthly_revenue=15000))
    mc3   = run_monte_carlo(FinancialContext(burn_rate=10000, cash_balance=100000, monthly_revenue=15000), kpis3)
    check("profitable → survie=100%",    mc3.proba_survie_12m == 1.0)


def test_scenario_proj():
    print("\n══ scenario_projection ══════════")
    kpis  = calculate_kpis(CTX)
    mc    = run_monte_carlo(CTX, kpis)
    phase = route_by_phase(CTX)
    sp    = scenario_projection(CTX, kpis, mc, phase)
    check("P_pess <= P_real runway",     sp.pessimiste.runway_months <= sp.realiste.runway_months)
    check("P_real <= P_opti runway",     sp.realiste.runway_months <= sp.optimiste.runway_months)
    check("growth pess = 0",             sp.pessimiste.growth_rate == 0.0)
    check("recommandation non vide",     len(sp.recommandation) > 0)
    check("phase = seed",                sp.phase == "seed")
    # Hypothèse doublement
    ctx_d = FinancialContext(burn_rate=12000, cash_balance=80000, monthly_revenue=750,
                              hypotheses=["je pense doubler mes clients"])
    kd = calculate_kpis(ctx_d); md = run_monte_carlo(ctx_d, kd); pd_ = route_by_phase(ctx_d)
    sp_d = scenario_projection(ctx_d, kd, md, pd_)
    check("doublement → growth opti=0.5", sp_d.optimiste.growth_rate == 0.5)


def test_seasonality():
    print("\n══ seasonality_trend ════════════")
    history = [RevenueDataPoint(f"2024-{i:02d}-01", 1000 * (1.10 ** i)) for i in range(1, 9)]
    ctx_t   = FinancialContext(monthly_revenue=2000, months_data=8)
    r = seasonality_trend(ctx_t, history, Phase.TRACTION)
    check("forecast_12m >= forecast_3m",  r.forecast_12m >= r.forecast_3m)
    check("trend_direction valide",       r.trend_direction in ("hausse", "baisse", "stable"))
    check("intervals cohérents",          r.forecast_12m_lower <= r.forecast_12m <= r.forecast_12m_upper)
    # Bloqué en seed
    r2 = seasonality_trend(CTX, history, Phase.SEED)
    check("seed → prophet=False",         not r2.prophet_available)
    # < 6 mois → bloqué
    r3 = seasonality_trend(ctx_t, history[:4], Phase.TRACTION)
    check("< 6 mois → bloqué",           not r3.prophet_available)
    # Ne plante jamais
    r4 = seasonality_trend(CTX, [], Phase.TRACTION)
    check("history vide ne plante pas",   r4 is not None)


def test_comparator():
    print("\n══ scenario_comparator ══════════")
    kpis  = calculate_kpis(CTX)
    mc    = run_monte_carlo(CTX, kpis)
    phase = route_by_phase(CTX)
    sp    = scenario_projection(CTX, kpis, mc, phase)
    r     = scenario_comparator(CTX, kpis, sp)
    check("score dans [0,1]",            0 <= r.score_vs_benchmark <= 1)
    check("5 comparaisons",              len(r.comparaisons) == 5)
    check("resume non vide",             len(r.resume) > 0)
    check("LTV/CAC=4 → AU_DESSUS",
          next(c for c in r.comparaisons if c.kpi_name == "LTV/CAC").statut == "AU_DESSUS")
    # Avec benchmarks Chroma
    bench = BenchmarkResult(cac_median=200, ltv_median=600, churn_median=0.07,
                             gross_margin_median=30.0, source="Chroma MENA 2024")
    r2 = scenario_comparator(CTX, kpis, sp, benchmarks=bench)
    check("source Chroma utilisée",      "Chroma" in r2.benchmark_source)


def test_pipeline_complet():
    print("\n══ Pipeline complet (7 outils) ══")
    try:
        v     = validate_inputs(CTX)
        phase = route_by_phase(CTX)
        kpis  = calculate_kpis(CTX)
        mc    = run_monte_carlo(CTX, kpis)
        sp    = scenario_projection(CTX, kpis, mc, phase)
        cmp   = scenario_comparator(CTX, kpis, sp)
        check("pipeline sans erreur",    True)
        check("phase = seed",            phase == Phase.SEED)
        check("confiance data = 0.9",    v.data_quality_score == 0.9)
        check("score benchmark > 0",     cmp.score_vs_benchmark > 0)
        print(f"\n  ══ Rapport Startup Tunis ══")
        print(f"  Phase      : {phase.value}")
        print(f"  Runway     : P10={mc.p10}  P50={mc.p50}  P90={mc.p90}")
        print(f"  Survie 12m : {mc.proba_survie_12m*100:.0f}%")
        print(f"  Benchmark  : {cmp.score_vs_benchmark*100:.0f}%")
        print(f"  Conseil    : {sp.recommandation}")
    except Exception as e:
        check("pipeline sans erreur", False, str(e))


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — Financial Modeling Engine complet")
    print("=" * 50)
    test_validate()
    test_route()
    test_kpis()
    test_monte_carlo()
    test_scenario_proj()
    test_seasonality()
    test_comparator()
    test_pipeline_complet()
    print("\n" + "=" * 50)
    print("Tous les tests terminés.")
    print("=" * 50)