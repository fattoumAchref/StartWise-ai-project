# tools/seasonality_trend.py — Forecasting avec Prophet
# Activé UNIQUEMENT en phase traction (6+ mois de données)
# pip install prophet

from dataclasses import dataclass, field
from typing import Optional
from models.data_models import FinancialContext, Phase


# ─────────────────────────────────────────
# MODÈLE DE SORTIE
# ─────────────────────────────────────────

@dataclass
class SeasonalityResult:
    # Forecast
    forecast_3m:      float          # revenus prévus dans 3 mois
    forecast_6m:      float          # revenus prévus dans 6 mois
    forecast_12m:     float          # revenus prévus dans 12 mois

    # Tendance
    trend_direction:  str            # "hausse" | "baisse" | "stable"
    trend_monthly_pct: float         # % de croissance mensuelle détectée

    # Saisonnalité
    has_seasonality:  bool           # saisonnalité détectée ?
    peak_months:      list           # mois de pic (ex: [11, 12] = nov/déc)
    low_months:       list           # mois creux

    # Intervalles de confiance Prophet
    forecast_12m_lower: float        # borne basse 80%
    forecast_12m_upper: float        # borne haute 80%

    # Qualité
    n_data_points:    int            # nb de points utilisés
    prophet_available: bool          # Prophet installé ?
    alerte:           str


@dataclass
class RevenueDataPoint:
    """Un point de données mensuel."""
    date:    str    # format "YYYY-MM-DD" (1er du mois)
    revenue: float


# ─────────────────────────────────────────
# FONCTION PRINCIPALE
# ─────────────────────────────────────────

def seasonality_trend(
    context: FinancialContext,
    revenue_history: list,          # liste de RevenueDataPoint
    phase: Phase,
    forecast_horizon: int = 12,     # mois à prévoir
) -> SeasonalityResult:
    """
    Analyse la tendance et la saisonnalité des revenus.
    Utilise Prophet si disponible, sinon fallback linéaire.

    IMPORTANT : appeler uniquement si phase == TRACTION ou FUNDRAISING
    ET si len(revenue_history) >= 6

    Paramètres :
        context         : FinancialContext
        revenue_history : liste de RevenueDataPoint (min 6 points)
        phase           : Phase détectée par route_by_phase
        forecast_horizon: nombre de mois à prévoir

    Exemple :
        history = [
            RevenueDataPoint("2024-01-01", 1200),
            RevenueDataPoint("2024-02-01", 1450),
            ...  # 8 mois
        ]
        result = seasonality_trend(ctx, history, Phase.TRACTION)
        result.forecast_12m      → 8500.0
        result.trend_direction   → "hausse"
        result.trend_monthly_pct → 0.12
    """

    # ── Garde-fou : phase incorrecte ────────────────────────
    if phase not in (Phase.TRACTION, Phase.FUNDRAISING):
        return _fallback_result(
            context, revenue_history,
            alerte="Prophet non activé en phase seed — pas assez de données historiques"
        )

    # ── Garde-fou : pas assez de données ────────────────────
    if len(revenue_history) < 6:
        return _fallback_result(
            context, revenue_history,
            alerte=f"Seulement {len(revenue_history)} mois de données — minimum 6 requis pour Prophet"
        )

    # ── Essayer Prophet ──────────────────────────────────────
    try:
        return _prophet_forecast(context, revenue_history, forecast_horizon)
    except ImportError:
        return _fallback_linear(
            context, revenue_history, forecast_horizon,
            alerte="Prophet non installé — forecast linéaire utilisé. Installez : pip install prophet"
        )
    except Exception as e:
        return _fallback_linear(
            context, revenue_history, forecast_horizon,
            alerte=f"Erreur Prophet : {str(e)[:80]} — fallback linéaire utilisé"
        )


# ─────────────────────────────────────────
# PROPHET FORECAST
# ─────────────────────────────────────────

def _prophet_forecast(
    context: FinancialContext,
    revenue_history: list,
    horizon: int,
) -> SeasonalityResult:
    """Forecast avec Prophet — appelé seulement si Prophet est installé."""
    import pandas as pd
    from prophet import Prophet

    # Préparer le DataFrame Prophet (colonnes ds et y obligatoires)
    df = pd.DataFrame([
        {"ds": point.date, "y": point.revenue}
        for point in revenue_history
    ])
    df["ds"] = pd.to_datetime(df["ds"])

    # Configurer Prophet
    model = Prophet(
        interval_width      = 0.80,   # intervalle de confiance 80%
        yearly_seasonality  = len(revenue_history) >= 12,  # annuelle si 12m+
        weekly_seasonality  = False,  # données mensuelles
        daily_seasonality   = False,
        seasonality_mode    = "multiplicative",  # adapté aux startups en croissance
    )
    model.fit(df)

    # Générer les dates futures
    future = model.make_future_dataframe(periods=horizon, freq="MS")
    forecast = model.predict(future)

    # Extraire les prévisions futures uniquement
    future_fc = forecast.tail(horizon)
    forecast_3m  = float(future_fc.iloc[2]["yhat"])   if horizon >= 3  else None
    forecast_6m  = float(future_fc.iloc[5]["yhat"])   if horizon >= 6  else None
    forecast_12m = float(future_fc.iloc[-1]["yhat"])

    # Borne basse et haute
    forecast_12m_lower = float(future_fc.iloc[-1]["yhat_lower"])
    forecast_12m_upper = float(future_fc.iloc[-1]["yhat_upper"])

    # Tendance mensuelle
    if len(forecast) >= 2:
        first_trend = float(forecast.iloc[0]["trend"])
        last_trend  = float(forecast.iloc[-1]["trend"])
        n_periods   = len(forecast) - 1
        monthly_pct = ((last_trend / max(first_trend, 1)) ** (1 / max(n_periods, 1))) - 1
    else:
        monthly_pct = 0.0

    trend_direction = (
        "hausse" if monthly_pct > 0.02 else
        "baisse" if monthly_pct < -0.02 else
        "stable"
    )

    # Saisonnalité — détection des pics et creux
    peak_months, low_months = _detect_seasonality(forecast, revenue_history)
    has_seasonality = len(peak_months) > 0 or len(low_months) > 0

    return SeasonalityResult(
        forecast_3m         = round(max(forecast_3m or 0, 0), 0),
        forecast_6m         = round(max(forecast_6m or 0, 0), 0),
        forecast_12m        = round(max(forecast_12m, 0), 0),
        trend_direction     = trend_direction,
        trend_monthly_pct   = round(monthly_pct, 4),
        has_seasonality     = has_seasonality,
        peak_months         = peak_months,
        low_months          = low_months,
        forecast_12m_lower  = round(max(forecast_12m_lower, 0), 0),
        forecast_12m_upper  = round(max(forecast_12m_upper, 0), 0),
        n_data_points       = len(revenue_history),
        prophet_available   = True,
        alerte              = f"Forecast Prophet sur {len(revenue_history)} mois de données",
    )


# ─────────────────────────────────────────
# FALLBACK LINÉAIRE (sans Prophet)
# ─────────────────────────────────────────

def _fallback_linear(
    context: FinancialContext,
    revenue_history: list,
    horizon: int,
    alerte: str,
) -> SeasonalityResult:
    """
    Fallback si Prophet non installé.
    Régression linéaire simple sur les revenus historiques.
    """
    import numpy as np

    revenues = [p.revenue for p in revenue_history]
    n        = len(revenues)

    # Taux de croissance moyen mois sur mois
    if n >= 2 and revenues[0] > 0:
        growth_rates = []
        for i in range(1, n):
            if revenues[i - 1] > 0:
                g = (revenues[i] - revenues[i - 1]) / revenues[i - 1]
                growth_rates.append(g)
        monthly_pct = float(np.mean(growth_rates)) if growth_rates else 0.0
    else:
        monthly_pct = 0.0

    # Clamp pour éviter les explosions
    monthly_pct = max(min(monthly_pct, 0.50), -0.30)

    last_rev = revenues[-1]
    forecast_3m  = last_rev * ((1 + monthly_pct) ** 3)
    forecast_6m  = last_rev * ((1 + monthly_pct) ** 6)
    forecast_12m = last_rev * ((1 + monthly_pct) ** 12)

    # Intervalles approximatifs (±20%)
    forecast_12m_lower = forecast_12m * 0.80
    forecast_12m_upper = forecast_12m * 1.20

    trend_direction = (
        "hausse" if monthly_pct > 0.02 else
        "baisse" if monthly_pct < -0.02 else
        "stable"
    )

    return SeasonalityResult(
        forecast_3m         = round(max(forecast_3m, 0), 0),
        forecast_6m         = round(max(forecast_6m, 0), 0),
        forecast_12m        = round(max(forecast_12m, 0), 0),
        trend_direction     = trend_direction,
        trend_monthly_pct   = round(monthly_pct, 4),
        has_seasonality     = False,
        peak_months         = [],
        low_months          = [],
        forecast_12m_lower  = round(max(forecast_12m_lower, 0), 0),
        forecast_12m_upper  = round(max(forecast_12m_upper, 0), 0),
        n_data_points       = n,
        prophet_available   = False,
        alerte              = alerte,
    )


def _fallback_result(
    context: FinancialContext,
    revenue_history: list,
    alerte: str,
) -> SeasonalityResult:
    """Résultat vide quand les conditions ne sont pas remplies."""
    rev = context.monthly_revenue or 0.0
    return SeasonalityResult(
        forecast_3m         = rev,
        forecast_6m         = rev,
        forecast_12m        = rev,
        trend_direction     = "stable",
        trend_monthly_pct   = 0.0,
        has_seasonality     = False,
        peak_months         = [],
        low_months          = [],
        forecast_12m_lower  = rev * 0.8,
        forecast_12m_upper  = rev * 1.2,
        n_data_points       = len(revenue_history),
        prophet_available   = False,
        alerte              = alerte,
    )


def _detect_seasonality(forecast, revenue_history: list) -> tuple:
    """
    Détecte les mois de pic et creux depuis le forecast Prophet.
    Retourne (peak_months, low_months).
    """
    try:
        import pandas as pd
        # Regarder la composante saisonnalité annuelle si disponible
        if "yearly" not in forecast.columns:
            return [], []

        monthly_avg = forecast.groupby(forecast["ds"].dt.month)["yearly"].mean()
        mean_val    = monthly_avg.mean()
        std_val     = monthly_avg.std()

        if std_val < 0.05:  # pas assez de variation pour parler de saisonnalité
            return [], []

        peaks = [int(m) for m, v in monthly_avg.items() if v > mean_val + 0.5 * std_val]
        lows  = [int(m) for m, v in monthly_avg.items() if v < mean_val - 0.5 * std_val]
        return sorted(peaks), sorted(lows)
    except Exception:
        return [], []