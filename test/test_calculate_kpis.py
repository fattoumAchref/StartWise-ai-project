# tests/test_calculate_kpis.py
# Lance avec : python tests/test_calculate_kpis.py

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, DataQuality
from tools.calculate_kpis import calculate_kpis


# ─────────────────────────────────────────
# UTILITAIRE — affiche PASS ou FAIL
# ─────────────────────────────────────────

def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu   : {obtenu}")
        if attendu:
            print(f"         attendu  : {attendu}")


# ─────────────────────────────────────────
# TEST 1 — CAS NORMAL
# Données complètes et réalistes
# Startup food delivery Tunis
# ─────────────────────────────────────────

def test_cas_normal():
    print("\n── TEST 1 : Cas normal ──────────────────────")

    ctx = FinancialContext(
        burn_rate         = 12000,   # dépense 12 000 DT/mois
        cash_balance      = 80000,   # a 80 000 DT en banque
        monthly_revenue   = 750,     # gagne 750 DT/mois (15 clients × 50 DT)
        n_clients         = 15,
        prix_client       = 50,
        churn_rate        = 0.05,    # perd 5% de ses clients par mois
        marketing_budget  = 2000,
        new_clients_month = 8,
        burn_quality      = DataQuality.ESTIMATED,
        cash_quality      = DataQuality.REAL,
        revenue_quality   = DataQuality.REAL,
    )
    r = calculate_kpis(ctx)

    # Burn net = 12000 - 750 = 11250
    check("burn_net = 11250",
          r.burn_net == 11250,
          r.burn_net, 11250)

    # Runway = 80000 / 11250 = 7.1 mois
    # Vérifie toi-même : 80000 ÷ 11250 = 7.1
    check("runway ≈ 7.1 mois",
          6.9 <= r.runway_months <= 7.3,
          r.runway_months, "entre 6.9 et 7.3")

    # 7 mois c'est OK (pas critique)
    check("alerte runway = OK",
          r.cash_out_alert == "OK",
          r.cash_out_alert, "OK")

    # LTV = prix / churn = 50 / 0.05 = 1000 DT
    # Logique : si un client paie 50 DT/mois et part après 20 mois (1/0.05)
    # il t'a rapporté 50 × 20 = 1000 DT
    check("LTV = 1000",
          r.ltv == 1000.0,
          r.ltv, 1000.0)

    # CAC = budget marketing / nouveaux clients = 2000 / 8 = 250 DT
    check("CAC = 250",
          r.cac == 250.0,
          r.cac, 250.0)

    # LTV/CAC = 1000 / 250 = 4.0 → SAIN (doit être > 3)
    check("LTV/CAC = 4.0 → SAIN",
          r.ltv_cac_ratio == 4.0 and r.ltv_cac_status == "SAIN",
          f"{r.ltv_cac_ratio} → {r.ltv_cac_status}", "4.0 → SAIN")

    # MRR = 15 clients × 50 DT = 750 DT
    check("MRR = 750",
          r.mrr == 750,
          r.mrr, 750)

    # ARR = MRR × 12 = 9000 DT
    check("ARR = 9000",
          r.arr == 9000,
          r.arr, 9000)


# ─────────────────────────────────────────
# TEST 2 — CAS CRITIQUE
# Peu de cash, burn élevé
# ─────────────────────────────────────────

def test_cas_critique():
    print("\n── TEST 2 : Cas critique (peu de cash) ─────")

    ctx = FinancialContext(
        burn_rate       = 15000,
        cash_balance    = 20000,   # seulement 20k en banque
        monthly_revenue = 3000,
        n_clients       = 10,
        prix_client     = 300,
        churn_rate      = 0.10,
    )
    r = calculate_kpis(ctx)

    # Burn net = 15000 - 3000 = 12000
    # Runway = 20000 / 12000 = 1.67 mois → CRITIQUE
    check("runway < 3 mois",
          r.runway_months < 3,
          r.runway_months, "< 3")

    check("alerte = CRITIQUE",
          r.cash_out_alert == "CRITIQUE",
          r.cash_out_alert, "CRITIQUE")

    # L'agent doit avoir levé une alerte critique
    alertes_critiques = [a for a in r.alertes if "CRITIQUE" in a]
    check("au moins 1 alerte CRITIQUE",
          len(alertes_critiques) >= 1,
          r.alertes)


# ─────────────────────────────────────────
# TEST 3 — CAS DÉGRADÉ
# Données manquantes — l'outil ne doit pas planter
# ─────────────────────────────────────────

def test_cas_degrade():
    print("\n── TEST 3 : Données manquantes (ne doit pas planter) ──")

    # Seulement burn et cash — le minimum absolu
    ctx = FinancialContext(
        burn_rate    = 8000,
        cash_balance = 50000,
        # tout le reste est None
    )

    # Ne doit pas lever d'exception
    try:
        r = calculate_kpis(ctx)
        check("ne plante pas",
              True, "OK")
    except Exception as e:
        check("ne plante pas",
              False, str(e))
        return

    # Runway calculable même sans revenue
    # 50000 / 8000 = 6.25 mois
    check("runway calculable sans revenue",
          r.runway_months is not None,
          r.runway_months)

    # CAC et LTV doivent être None (pas de données)
    check("CAC = None si données absentes",
          r.cac is None,
          r.cac, None)

    check("LTV = None si prix absent",
          r.ltv is None,
          r.ltv, None)

    # Des alertes doivent signaler les manques
    check("alertes non vides pour données manquantes",
          len(r.alertes) > 0,
          r.alertes)


# ─────────────────────────────────────────
# TEST 4 — CAS EXTRÊME
# Valeurs à zéro — division par zéro ?
# ─────────────────────────────────────────

def test_cas_extreme():
    print("\n── TEST 4 : Valeurs extrêmes (pas de crash) ──")

    # burn = 0 et revenue = 0
    ctx1 = FinancialContext(
        burn_rate       = 0,
        cash_balance    = 50000,
        monthly_revenue = 0,
    )
    try:
        r1 = calculate_kpis(ctx1)
        check("burn=0 ne plante pas",
              True, "OK")
        # Pas de burn → runway infini
        check("runway = infini si burn=0",
              r1.runway_months == float('inf'),
              r1.runway_months, "inf")
    except Exception as e:
        check("burn=0 ne plante pas", False, str(e))

    # cash = 0
    ctx2 = FinancialContext(
        burn_rate    = 5000,
        cash_balance = 0,
    )
    try:
        r2 = calculate_kpis(ctx2)
        check("cash=0 ne plante pas",
              True, "OK")
        check("runway=0 si cash=0",
              r2.runway_months == 0.0,
              r2.runway_months, 0.0)
    except Exception as e:
        check("cash=0 ne plante pas", False, str(e))

    # Tous les champs à None sauf le minimum
    ctx3 = FinancialContext()
    try:
        r3 = calculate_kpis(ctx3)
        check("tout None ne plante pas",
              True, "OK")
    except Exception as e:
        check("tout None ne plante pas", False, str(e))


# ─────────────────────────────────────────
# TEST 5 — CAS PROFITABLE
# Revenue > burn
# ─────────────────────────────────────────

def test_cas_profitable():
    print("\n── TEST 5 : Startup déjà profitable ─────────")

    ctx = FinancialContext(
        burn_rate       = 10000,
        cash_balance    = 100000,
        monthly_revenue = 15000,   # gagne plus qu'elle dépense
        n_clients       = 50,
        prix_client     = 300,
        churn_rate      = 0.03,
        cogs            = 30,
        marketing_budget = 1000,
        new_clients_month = 5,
    )
    r = calculate_kpis(ctx)

    # Burn net = 0 (revenue > burn)
    check("burn_net = 0 si profitable",
          r.burn_net == 0.0,
          r.burn_net, 0.0)

    # Runway = infini si pas de burn net
    check("runway = infini si profitable",
          r.runway_months == float('inf'),
          r.runway_months, "inf")

    check("alerte = OK si profitable",
          r.cash_out_alert == "OK",
          r.cash_out_alert, "OK")

    # Gross margin = (15000 - 30×50) / 15000 = (15000-1500)/15000 = 90%
    check("gross_margin > 60% → SAIN",
          r.gross_margin_pct is not None and r.gross_margin_pct >= 60,
          r.gross_margin_pct)


# ─────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — calculate_kpis")
    print("=" * 50)

    test_cas_normal()
    test_cas_critique()
    test_cas_degrade()
    test_cas_extreme()
    test_cas_profitable()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt pour la suite.")
    print("Un ✗ FAIL = bug à corriger avant de continuer.")
    print("=" * 50)