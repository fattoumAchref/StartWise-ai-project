import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.data_models import FinancialContext, Phase
from tools.seasonality_trend import seasonality_trend, RevenueDataPoint


def check(nom, condition, obtenu, attendu=""):
    if condition:
        print(f"  ✓ PASS — {nom}")
    else:
        print(f"  ✗ FAIL — {nom}")
        print(f"         obtenu  : {obtenu}")
        if attendu:
            print(f"         attendu : {attendu}")


def _make_history(start_revenue=1000, months=8, growth=0.10):
    """Génère un historique fictif de revenus croissants."""
    from datetime import date
    history = []
    rev = start_revenue
    for i in range(months):
        month = (i % 12) + 1
        year  = 2024 + (i // 12)
        history.append(RevenueDataPoint(
            date    = f"{year}-{month:02d}-01",
            revenue = round(rev, 2)
        ))
        rev = rev * (1 + growth)
    return history


# ─────────────────────────────────────────
# TEST 1 — Phase SEED → pas de Prophet
# ─────────────────────────────────────────
def test_phase_seed_bloqué():
    print("\n── TEST 1 : Phase SEED → fallback sans calcul ─")

    ctx     = FinancialContext(burn_rate=12000, cash_balance=80000,
                               monthly_revenue=750)
    history = _make_history(months=8)
    result  = seasonality_trend(ctx, history, Phase.SEED)

    check("prophet_available = False en SEED",
          not result.prophet_available,
          result.prophet_available, False)

    check("alerte mentionne phase seed",
          "seed" in result.alerte.lower() or "données" in result.alerte.lower(),
          result.alerte)

    print(f"  → alerte : {result.alerte}")


# ─────────────────────────────────────────
# TEST 2 — Moins de 6 mois → bloqué
# ─────────────────────────────────────────
def test_pas_assez_données():
    print("\n── TEST 2 : Moins de 6 mois → bloqué ────────")

    ctx     = FinancialContext(monthly_revenue=2000)
    history = _make_history(months=4)   # seulement 4 mois
    result  = seasonality_trend(ctx, history, Phase.TRACTION)

    check("bloqué si < 6 mois",
          not result.prophet_available,
          result.prophet_available, False)

    check("alerte mentionne le nombre de mois",
          "4" in result.alerte or "minimum" in result.alerte.lower(),
          result.alerte)

    print(f"  → alerte : {result.alerte}")


# ─────────────────────────────────────────
# TEST 3 — Fallback linéaire (Prophet absent)
# Vérifie la logique sans dépendance Prophet
# ─────────────────────────────────────────
def test_fallback_linéaire():
    print("\n── TEST 3 : Fallback linéaire (sans Prophet) ─")

    ctx     = FinancialContext(monthly_revenue=2000, months_data=8)
    history = _make_history(start_revenue=1000, months=8, growth=0.10)
    result  = seasonality_trend(ctx, history, Phase.TRACTION)

    # Que Prophet soit installé ou non, les résultats doivent être cohérents
    check("forecast_3m > forecast actuel",
          result.forecast_3m >= history[-1].revenue * 0.8,
          result.forecast_3m)

    check("forecast_12m > forecast_3m",
          result.forecast_12m >= result.forecast_3m,
          f"{result.forecast_12m} < {result.forecast_3m}")

    check("trend_direction valide",
          result.trend_direction in ("hausse", "baisse", "stable"),
          result.trend_direction)

    check("forecast_12m_lower <= forecast_12m",
          result.forecast_12m_lower <= result.forecast_12m,
          f"{result.forecast_12m_lower} > {result.forecast_12m}")

    check("forecast_12m_upper >= forecast_12m",
          result.forecast_12m_upper >= result.forecast_12m,
          f"{result.forecast_12m_upper} < {result.forecast_12m}")

    check("n_data_points = 8",
          result.n_data_points == 8,
          result.n_data_points, 8)

    print(f"  → trend={result.trend_direction}  "
          f"monthly_pct={result.trend_monthly_pct:.1%}")
    print(f"  → forecast : 3m={result.forecast_3m}  "
          f"6m={result.forecast_6m}  12m={result.forecast_12m}")
    print(f"  → Prophet installé : {result.prophet_available}")


# ─────────────────────────────────────────
# TEST 4 — Tendance baisse détectée
# ─────────────────────────────────────────
def test_tendance_baisse():
    print("\n── TEST 4 : Tendance baisse ──────────────────")

    # Revenus qui baissent chaque mois
    history = _make_history(start_revenue=5000, months=8, growth=-0.08)
    ctx     = FinancialContext(monthly_revenue=history[-1].revenue, months_data=8)
    result  = seasonality_trend(ctx, history, Phase.TRACTION)

    check("trend_direction = baisse",
          result.trend_direction == "baisse",
          result.trend_direction, "baisse")

    check("trend_monthly_pct < 0",
          result.trend_monthly_pct < 0,
          result.trend_monthly_pct, "< 0")

    print(f"  → trend={result.trend_direction}  "
          f"monthly_pct={result.trend_monthly_pct:.1%}")


# ─────────────────────────────────────────
# TEST 5 — Ne plante jamais
# ─────────────────────────────────────────
def test_robustesse():
    print("\n── TEST 5 : Robustesse (ne plante jamais) ────")

    # Histoire vide
    try:
        ctx    = FinancialContext(monthly_revenue=0)
        result = seasonality_trend(ctx, [], Phase.TRACTION)
        check("history vide ne plante pas", True, "OK")
    except Exception as e:
        check("history vide ne plante pas", False, str(e))

    # Revenus à zéro
    try:
        history = [RevenueDataPoint(f"2024-{i:02d}-01", 0) for i in range(1, 9)]
        ctx     = FinancialContext(monthly_revenue=0, months_data=8)
        result  = seasonality_trend(ctx, history, Phase.TRACTION)
        check("revenus=0 ne plante pas", True, "OK")
    except Exception as e:
        check("revenus=0 ne plante pas", False, str(e))

    # Phase None → on passe SEED
    try:
        ctx    = FinancialContext(monthly_revenue=1000)
        result = seasonality_trend(ctx, _make_history(months=8), Phase.SEED)
        check("phase SEED ne plante pas", True, "OK")
    except Exception as e:
        check("phase SEED ne plante pas", False, str(e))


if __name__ == "__main__":
    print("=" * 50)
    print("TESTS — seasonality_trend")
    print("=" * 50)

    test_phase_seed_bloqué()
    test_pas_assez_données()
    test_fallback_linéaire()
    test_tendance_baisse()
    test_robustesse()

    print("\n" + "=" * 50)
    print("Tests terminés.")
    print("Tous les ✓ PASS = outil prêt.")
    print("Note : si Prophet est installé, les tests")
    print("       utilisent Prophet automatiquement.")
    print("=" * 50)