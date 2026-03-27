import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, DataQuality
from tools.validate_inputs import validate_inputs


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


# ─────────────────────────────────────────
# TEST 1 — Données complètes et cohérentes
# → is_valid = True, score élevé
# ─────────────────────────────────────────
def test_donnees_completes():
    print("\n── TEST 1 : Données complètes et cohérentes ─")

    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,    # cohérent avec 15 × 50
        n_clients       = 15,
        prix_client     = 50,
        churn_rate      = 0.05,
        burn_quality    = DataQuality.ESTIMATED,
        cash_quality    = DataQuality.REAL,
        revenue_quality = DataQuality.REAL,
    )
    r = validate_inputs(ctx)

    check("is_valid = True",
          r.is_valid, r.is_valid, True)

    # score = (0.7 + 1.0 + 1.0) / 3 = 0.9
    check("data_quality_score = 0.9",
          r.data_quality_score == 0.9,
          r.data_quality_score, 0.9)

    check("aucune incohérence",
          len(r.incoherences) == 0,
          r.incoherences, [])

    check("aucun champ critique manquant",
          not any("burn_rate" in m or "cash_balance" in m
                  for m in r.missing_critical),
          r.missing_critical)

    print(f"  → score={r.data_quality_score}  valid={r.is_valid}")


# ─────────────────────────────────────────
# TEST 2 — Champ critique manquant
# → is_valid = False
# ─────────────────────────────────────────
def test_champ_critique_manquant():
    print("\n── TEST 2 : Champ critique manquant ─────────")

    # Pas de cash_balance
    ctx = FinancialContext(
        burn_rate    = 12000,
        # cash_balance manquant
        monthly_revenue = 750,
    )
    r = validate_inputs(ctx)

    check("is_valid = False si cash absent",
          not r.is_valid, r.is_valid, False)

    check("missing_critical non vide",
          len(r.missing_critical) > 0,
          r.missing_critical)

    check("question posée sur cash_balance",
          any("cash" in q.lower() for q in r.questions_to_ask),
          r.questions_to_ask)

    # Pas de burn_rate
    ctx2 = FinancialContext(cash_balance=80000)
    r2   = validate_inputs(ctx2)

    check("is_valid = False si burn absent",
          not r2.is_valid, r2.is_valid, False)

    print(f"  → questions posées : {len(r.questions_to_ask)}")
    for q in r.questions_to_ask:
        print(f"     · {q}")


# ─────────────────────────────────────────
# TEST 3 — Incohérence : revenue vs prix × clients
# ─────────────────────────────────────────
def test_incoherence_revenue():
    print("\n── TEST 3 : Incohérence revenue ─────────────")

    ctx = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 5000,   # INCOHÉRENT : 15 × 50 = 750, pas 5000
        n_clients       = 15,
        prix_client     = 50,
    )
    r = validate_inputs(ctx)

    check("is_valid = False si incohérence",
          not r.is_valid, r.is_valid, False)

    check("incohérence revenue détectée",
          len(r.incoherences) > 0,
          r.incoherences)

    check("question de clarification générée",
          len(r.questions_to_ask) > 0,
          r.questions_to_ask)

    print(f"  → incohérence : {r.incoherences[0]}")


# ─────────────────────────────────────────
# TEST 4 — Churn invalide (> 1)
# ─────────────────────────────────────────
def test_churn_invalide():
    print("\n── TEST 4 : Churn invalide ───────────────────")

    ctx = FinancialContext(
        burn_rate    = 12000,
        cash_balance = 80000,
        churn_rate   = 50,   # 50 au lieu de 0.50 — erreur fréquente
    )
    r = validate_inputs(ctx)

    check("is_valid = False si churn > 1",
          not r.is_valid, r.is_valid, False)

    check("incohérence churn détectée",
          any("churn" in i.lower() for i in r.incoherences),
          r.incoherences)

    print(f"  → {r.incoherences[0]}")


# ─────────────────────────────────────────
# TEST 5 — Qualité des données
# data_quality_score reflète les DataQuality
# ─────────────────────────────────────────
def test_data_quality_score():
    print("\n── TEST 5 : data_quality_score ──────────────")

    # Tout REAL → score = 1.0
    ctx_real = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        burn_quality    = DataQuality.REAL,
        cash_quality    = DataQuality.REAL,
        revenue_quality = DataQuality.REAL,
    )
    r_real = validate_inputs(ctx_real)
    check("tout REAL → score = 1.0",
          r_real.data_quality_score == 1.0,
          r_real.data_quality_score, 1.0)

    # Tout ASSUMPTION → score = 0.4
    ctx_assump = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        burn_quality    = DataQuality.ASSUMPTION,
        cash_quality    = DataQuality.ASSUMPTION,
        revenue_quality = DataQuality.ASSUMPTION,
    )
    r_assump = validate_inputs(ctx_assump)
    check("tout ASSUMPTION → score = 0.4",
          r_assump.data_quality_score == 0.4,
          r_assump.data_quality_score, 0.4)

    # Mix → score = (1.0 + 0.7 + 0.4) / 3 = 0.7
    ctx_mix = FinancialContext(
        burn_rate       = 12000,
        cash_balance    = 80000,
        monthly_revenue = 750,
        burn_quality    = DataQuality.REAL,
        cash_quality    = DataQuality.ESTIMATED,
        revenue_quality = DataQuality.ASSUMPTION,
    )
    r_mix = validate_inputs(ctx_mix)
    check("mix REAL/EST/ASSUMP → score ≈ 0.7",
          abs(r_mix.data_quality_score - 0.7) < 0.01,
          r_mix.data_quality_score, "≈ 0.7")

    print(f"  → REAL={r_real.data_quality_score}  "
          f"ASSUMPTION={r_assump.data_quality_score}  "
          f"MIX={r_mix.data_quality_score}")


# ─────────────────────────────────────────
# TEST 6 — Données minimales (ne plante pas)
# ─────────────────────────────────────────
def test_donnees_minimales():
    print("\n── TEST 6 : Données minimales (ne plante pas)")

    ctx = FinancialContext()  # tout à None
    try:
        r = validate_inputs(ctx)
        check("ne plante pas",   True, "OK")
        check("is_valid = False", not r.is_valid, r.is_valid, False)
        check("questions générées",
              len(r.questions_to_ask) >= 2,
              r.questions_to_ask)
    except Exception as e:
        check("ne plante pas", False, str(e))

    print(f"  → {len(r.questions_to_ask)} questions générées")


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — validate_inputs")
    print("=" * 50)

    test_donnees_completes()
    test_champ_critique_manquant()
    test_incoherence_revenue()
    test_churn_invalide()
    test_data_quality_score()
    test_donnees_minimales()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt pour la suite.")
    print("Un ✗ FAIL = bug à corriger avant de continuer.")
    print("=" * 50)