import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, Phase, DataQuality
from tools.route_by_phase import route_by_phase, get_active_models


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


# ─────────────────────────────────────────
# TEST 1 — Phase SEED
# Revenue = 0, pas de levée
# ─────────────────────────────────────────
def test_seed():
    print("\n── TEST 1 : Phase SEED ──────────────────────")

    # Cas de base : pas de revenue
    ctx1 = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 0,
        months_data     = 0,
    )
    p1 = route_by_phase(ctx1)
    check("revenue=0 → SEED", p1 == Phase.SEED, p1.value, "seed")

    # Revenue mais moins de 6 mois de données
    ctx2 = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        months_data     = 3,   # seulement 3 mois
    )
    p2 = route_by_phase(ctx2)
    check("revenue présent mais < 6 mois → SEED",
          p2 == Phase.SEED, p2.value, "seed")

    # Revenue None
    ctx3 = FinancialContext(burn_rate=12000, cash_balance=80000)
    p3   = route_by_phase(ctx3)
    check("revenue None → SEED", p3 == Phase.SEED, p3.value, "seed")

    print(f"  → tous SEED : {p1.value}, {p2.value}, {p3.value}")


# ─────────────────────────────────────────
# TEST 2 — Phase TRACTION
# Revenue > 0 ET 6+ mois de données
# ─────────────────────────────────────────
def test_traction():
    print("\n── TEST 2 : Phase TRACTION ──────────────────")

    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 5000,
        months_data     = 8,   # 8 mois d'historique
    )
    p = route_by_phase(ctx)
    check("revenue + 8 mois → TRACTION",
          p == Phase.TRACTION, p.value, "traction")

    # Exactement 6 mois
    ctx2 = FinancialContext(
        monthly_revenue = 2000,
        months_data     = 6,
    )
    p2 = route_by_phase(ctx2)
    check("revenue + exactement 6 mois → TRACTION",
          p2 == Phase.TRACTION, p2.value, "traction")

    print(f"  → {p.value}, {p2.value}")


# ─────────────────────────────────────────
# TEST 3 — Phase FUNDRAISING
# En traction ET cherche à lever
# ─────────────────────────────────────────
def test_fundraising():
    print("\n── TEST 3 : Phase FUNDRAISING ───────────────")

    # Flag explicite
    ctx1 = FinancialContext(
        monthly_revenue    = 5000,
        months_data        = 8,
        intent_fundraising = True,
    )
    p1 = route_by_phase(ctx1)
    check("traction + intent_fundraising=True → FUNDRAISING",
          p1 == Phase.FUNDRAISING, p1.value, "fundraising")

    # Via hypothèse textuelle
    ctx2 = FinancialContext(
        monthly_revenue = 5000,
        months_data     = 8,
        hypotheses      = ["je cherche à lever 500k auprès d'investisseurs"],
    )
    p2 = route_by_phase(ctx2)
    check("traction + hypothèse levée → FUNDRAISING",
          p2 == Phase.FUNDRAISING, p2.value, "fundraising")

    # Via phase_hint
    ctx3 = FinancialContext(
        monthly_revenue = 5000,
        months_data     = 8,
        phase_hint      = "fundraising",
    )
    p3 = route_by_phase(ctx3)
    check("traction + phase_hint fundraising → FUNDRAISING",
          p3 == Phase.FUNDRAISING, p3.value, "fundraising")

    print(f"  → {p1.value}, {p2.value}, {p3.value}")


# ─────────────────────────────────────────
# TEST 4 — Phase SEED_RAISING
# Seed ET cherche à lever
# ─────────────────────────────────────────
def test_seed_raising():
    print("\n── TEST 4 : Phase SEED_RAISING ──────────────")

    ctx1 = FinancialContext(
        monthly_revenue    = 0,
        months_data        = 0,
        intent_fundraising = True,
    )
    p1 = route_by_phase(ctx1)
    check("seed + intent_fundraising → SEED_RAISING",
          p1 == Phase.SEED_RAISING, p1.value, "seed+fundraising")

    ctx2 = FinancialContext(
        monthly_revenue = 750,
        months_data     = 2,   # pas assez pour traction
        hypotheses      = ["je veux pitcher des VCs"],
    )
    p2 = route_by_phase(ctx2)
    check("revenue faible + hypothèse pitch → SEED_RAISING",
          p2 == Phase.SEED_RAISING, p2.value, "seed+fundraising")

    print(f"  → {p1.value}, {p2.value}")


# ─────────────────────────────────────────
# TEST 5 — get_active_models
# Les bons modèles s'activent selon la phase
# ─────────────────────────────────────────
def test_active_models():
    print("\n── TEST 5 : get_active_models ───────────────")

    # SEED → paramétrique uniquement
    m_seed = get_active_models(Phase.SEED)
    check("SEED → use_parametric=True",
          m_seed["use_parametric"], m_seed)
    check("SEED → use_prophet=False",
          not m_seed["use_prophet"], m_seed)
    check("SEED → use_dcf=False",
          not m_seed["use_dcf"], m_seed)
    check("SEED → monte_carlo=True",
          m_seed["use_monte_carlo"], m_seed)

    # TRACTION → Prophet uniquement
    m_trac = get_active_models(Phase.TRACTION)
    check("TRACTION → use_prophet=True",
          m_trac["use_prophet"], m_trac)
    check("TRACTION → use_dcf=False",
          not m_trac["use_dcf"], m_trac)

    # FUNDRAISING → Prophet + DCF + cap table
    m_fund = get_active_models(Phase.FUNDRAISING)
    check("FUNDRAISING → use_prophet=True",
          m_fund["use_prophet"], m_fund)
    check("FUNDRAISING → use_dcf=True",
          m_fund["use_dcf"], m_fund)
    check("FUNDRAISING → use_cap_table=True",
          m_fund["use_cap_table"], m_fund)

    # SEED_RAISING → paramétrique + DCF + cap table
    m_sr = get_active_models(Phase.SEED_RAISING)
    check("SEED_RAISING → use_parametric=True",
          m_sr["use_parametric"], m_sr)
    check("SEED_RAISING → use_dcf=True",
          m_sr["use_dcf"], m_sr)
    check("SEED_RAISING → use_prophet=False",
          not m_sr["use_prophet"], m_sr)

    print(f"  → SEED={m_seed}")
    print(f"  → TRACTION={m_trac}")


# ─────────────────────────────────────────
# TEST 6 — Startup Tunis
# ─────────────────────────────────────────
def test_startup_tunis():
    print("\n── TEST 6 : Startup Tunis (cas réel) ────────")

    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        n_clients       = 15,
        prix_client     = 50,
        months_data     = 0,   # vient de démarrer
        secteur         = "food_delivery",
    )
    phase  = route_by_phase(ctx)
    models = get_active_models(phase)

    check("startup Tunis → SEED",
          phase == Phase.SEED, phase.value, "seed")
    check("modèle paramétrique activé",
          models["use_parametric"], models)
    check("Prophet non activé (pas assez de data)",
          not models["use_prophet"], models)

    print(f"  → phase={phase.value}")
    print(f"  → modèles actifs : {[k for k,v in models.items() if v]}")


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — route_by_phase")
    print("=" * 50)

    test_seed()
    test_traction()
    test_fundraising()
    test_seed_raising()
    test_active_models()
    test_startup_tunis()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt pour la suite.")
    print("Un ✗ FAIL = bug à corriger avant de continuer.")
    print("=" * 50)