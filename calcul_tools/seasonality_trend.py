"""
calcul_tools/seasonality_trend.py
Trend + seasonality analysis blending client data with external sector signal.

Data-driven gating (replaces phase-based gating):
  0 pts      → sector estimation only            (confidence: NONE)
  1-2 pts    → very weak client signal            (confidence: VERY_LOW)
  3-5 pts    → partial client signal              (confidence: LOW)
  6-11 pts   → solid client signal                (confidence: MEDIUM)
  12+ pts    → full client signal + validation    (confidence: HIGH)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from models.data_models import FinancialContext, RevenueDataPoint

logger = logging.getLogger(__name__)

_MONTH_NAMES = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]

# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SeasonalityResult:
    # Forecasts
    forecast_3m:           float
    forecast_6m:           float
    forecast_12m:          float
    trend_direction:       str            # "hausse" | "baisse" | "stable"
    trend_monthly_pct:     float
    has_seasonality:       bool
    peak_months:           list
    low_months:            list
    forecast_12m_lower:    float
    forecast_12m_upper:    float
    n_data_points:         int
    prophet_available:     bool
    alerte:                str

    # ── Extended fields (external signal + reasoning) ─────────────────────────
    confidence_level:      str   = "UNKNOWN"    # NONE | VERY_LOW | LOW | MEDIUM | HIGH
    external_signal_used:  bool  = False
    sector_index:          list  = field(default_factory=list)   # 12 monthly multipliers
    anomaly_months:        list  = field(default_factory=list)   # client deviates > 25%
    market_context:        str   = ""
    blend_weight_client:   float = 1.0          # transparency: client data weight [0-1]
    reasoning:             str   = ""           # agent-grade natural language explanation


# ─────────────────────────────────────────────────────────────────────────────
# DATA SUFFICIENCY GATING
# ─────────────────────────────────────────────────────────────────────────────

_SUFFICIENCY_TABLE = [
    # (min_pts, max_pts, level,      client_w, ext_w, alerte_template)
    (0,  0,  "NONE",     0.00, 1.00, "Aucune donnée historique — estimation sectorielle pure"),
    (1,  2,  "VERY_LOW", 0.20, 0.80, "{n} point(s) — signal client très faible"),
    (3,  5,  "LOW",      0.40, 0.60, "{n} mois — confiance faible, saisonnalité estimée depuis le secteur"),
    (6,  11, "MEDIUM",   0.65, 0.35, "{n} mois — confiance moyenne, signal partiel"),
    (12, 9999,"HIGH",    0.85, 0.15, "{n} mois — confiance élevée, motif saisonnier détectable"),
]


def _compute_sufficiency(n: int) -> dict:
    for min_p, max_p, level, cw, ew, tpl in _SUFFICIENCY_TABLE:
        if min_p <= n <= max_p:
            return {
                "level":          level,
                "client_weight":  cw,
                "external_weight": ew,
                "alerte":         tpl.format(n=n),
            }
    return {"level": "HIGH", "client_weight": 0.85, "external_weight": 0.15,
            "alerte": f"{n} mois — confiance élevée"}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def seasonality_trend(
    context:          FinancialContext,
    revenue_history:  Optional[list] = None,
    phase             = None,          # kept for backward-compat; not used for gating
    forecast_horizon: int = 12,
    cache_path        = None,
) -> SeasonalityResult:
    """
    Analyse tendance + saisonnalité en fusionnant données client et signal sectoriel.
    Toujours produit un résultat — jamais silencieux.
    """
    from pathlib import Path
    history  = revenue_history or getattr(context, "revenue_history", []) or []
    suff     = _compute_sufficiency(len(history))

    # ── External sector signal ─────────────────────────────────────────────────
    try:
        from scraping.sector_calendar import get_sector_seasonality
        cp          = Path(cache_path) if cache_path else Path("./data/sector_seasonality_cache.json")
        sector_data = get_sector_seasonality(context.secteur, context.pays, cp)
    except Exception as e:
        logger.warning(f"sector_calendar unavailable: {e}; using static fallback")
        sector_data = _static_sector_fallback(context.secteur)

    # ── Client-side forecast ───────────────────────────────────────────────────
    client_fc = None
    if history:
        try:
            client_fc = _client_forecast(history, forecast_horizon)
        except Exception as e:
            logger.warning(f"Client forecast failed: {e}")

    # ── External-only forecast (sector pattern extrapolation) ─────────────────
    base_rev = (
        history[-1].revenue if history else
        (context.monthly_revenue or 0.0)
    )
    ext_fc   = _external_forecast(sector_data, base_rev, forecast_horizon)

    # ── Blend ─────────────────────────────────────────────────────────────────
    wc, we = suff["client_weight"], suff["external_weight"]
    blend  = _blend(client_fc, ext_fc, wc, we, base_rev, forecast_horizon)

    # ── Trend ─────────────────────────────────────────────────────────────────
    trend_pct, trend_dir = _compute_trend(history, client_fc)

    # ── Seasonality peaks / lows ───────────────────────────────────────────────
    if client_fc and client_fc.get("prophet_available") and client_fc.get("peak_months"):
        peak_months = client_fc["peak_months"]
        low_months  = client_fc["low_months"]
        has_season  = True
    else:
        peak_months, low_months, has_season = _sector_peaks_lows(
            sector_data.indices, suff["level"]
        )

    # ── Anomaly detection ─────────────────────────────────────────────────────
    anomaly_months = _detect_anomalies(history, sector_data.indices)

    # ── Natural language reasoning ─────────────────────────────────────────────
    reasoning = _generate_reasoning(
        suff, trend_dir, trend_pct, has_season,
        anomaly_months, peak_months, low_months,
        sector_data, context.secteur, len(history),
    )

    return SeasonalityResult(
        forecast_3m          = blend["f3"],
        forecast_6m          = blend["f6"],
        forecast_12m         = blend["f12"],
        trend_direction      = trend_dir,
        trend_monthly_pct    = round(trend_pct, 4),
        has_seasonality      = has_season,
        peak_months          = peak_months,
        low_months           = low_months,
        forecast_12m_lower   = blend["f12_lower"],
        forecast_12m_upper   = blend["f12_upper"],
        n_data_points        = len(history),
        prophet_available    = bool(client_fc and client_fc.get("prophet_available")),
        alerte               = suff["alerte"],
        confidence_level     = suff["level"],
        external_signal_used = True,
        sector_index         = sector_data.indices,
        anomaly_months       = anomaly_months,
        market_context       = sector_data.market_context,
        blend_weight_client  = wc,
        reasoning            = reasoning,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT-SIDE FORECAST (Prophet → linear fallback)
# ─────────────────────────────────────────────────────────────────────────────

def _client_forecast(history: list, horizon: int) -> dict:
    """Try Prophet; fall back to linear regression. Returns a plain dict."""
    try:
        return _prophet_forecast(history, horizon)
    except ImportError:
        return _linear_forecast(history, horizon)
    except Exception as e:
        logger.debug(f"Prophet failed ({e}); using linear forecast")
        return _linear_forecast(history, horizon)


def _prophet_forecast(history: list, horizon: int) -> dict:
    import pandas as pd
    from prophet import Prophet

    df = pd.DataFrame([{"ds": p.date, "y": p.revenue} for p in history])
    df["ds"] = pd.to_datetime(df["ds"])

    model = Prophet(
        interval_width     = 0.80,
        yearly_seasonality = len(history) >= 12,
        weekly_seasonality = False,
        daily_seasonality  = False,
        seasonality_mode   = "multiplicative",
    )
    model.fit(df)

    future   = model.make_future_dataframe(periods=horizon, freq="MS")
    forecast = model.predict(future)
    fut      = forecast.tail(horizon)

    # Monthly trend rate
    first_t = float(forecast.iloc[0]["trend"])
    last_t  = float(forecast.iloc[-1]["trend"])
    n       = max(len(forecast) - 1, 1)
    monthly_pct = ((last_t / max(first_t, 1e-9)) ** (1 / n)) - 1

    peak_months, low_months = _detect_seasonality_prophet(forecast)

    return {
        "prophet_available": True,
        "f3":          max(float(fut.iloc[2]["yhat"]) if horizon >= 3 else 0, 0),
        "f6":          max(float(fut.iloc[5]["yhat"]) if horizon >= 6 else 0, 0),
        "f12":         max(float(fut.iloc[-1]["yhat"]), 0),
        "f12_lower":   max(float(fut.iloc[-1]["yhat_lower"]), 0),
        "f12_upper":   max(float(fut.iloc[-1]["yhat_upper"]), 0),
        "monthly_pct": monthly_pct,
        "peak_months": peak_months,
        "low_months":  low_months,
    }


def _linear_forecast(history: list, horizon: int) -> dict:
    import numpy as np

    revenues = [p.revenue for p in history]
    n        = len(revenues)

    rates = []
    for i in range(1, n):
        if revenues[i - 1] > 0:
            rates.append((revenues[i] - revenues[i - 1]) / revenues[i - 1])
    monthly_pct = float(np.mean(rates)) if rates else 0.0
    monthly_pct = max(min(monthly_pct, 0.50), -0.30)

    last = revenues[-1]
    f3   = last * (1 + monthly_pct) ** 3
    f6   = last * (1 + monthly_pct) ** 6
    f12  = last * (1 + monthly_pct) ** 12

    return {
        "prophet_available": False,
        "f3":          max(f3, 0),
        "f6":          max(f6, 0),
        "f12":         max(f12, 0),
        "f12_lower":   max(f12 * 0.80, 0),
        "f12_upper":   max(f12 * 1.20, 0),
        "monthly_pct": monthly_pct,
        "peak_months": [],
        "low_months":  [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTERNAL (SECTOR) FORECAST
# ─────────────────────────────────────────────────────────────────────────────

def _external_forecast(sector_data, base_rev: float, horizon: int) -> dict:
    """
    Project revenue forward using sector monthly index + neutral trend.
    base_rev = last known revenue (or current monthly_revenue).
    """
    if base_rev <= 0:
        return {"f3": 0, "f6": 0, "f12": 0, "f12_lower": 0, "f12_upper": 0}

    from datetime import datetime
    current_month = datetime.now().month  # 1-indexed
    indices       = sector_data.indices  # 12 monthly multipliers (normalized)

    def _project(months_ahead: int) -> float:
        target_month_idx = (current_month - 1 + months_ahead) % 12
        return base_rev * indices[target_month_idx]

    f12 = _project(12)
    return {
        "f3":        _project(3),
        "f6":        _project(6),
        "f12":       f12,
        "f12_lower": f12 * (1 - sector_data.confidence * 0.25),
        "f12_upper": f12 * (1 + sector_data.confidence * 0.25),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BLENDING
# ─────────────────────────────────────────────────────────────────────────────

def _blend(
    client_fc: Optional[dict],
    ext_fc:    dict,
    wc:        float,
    we:        float,
    base_rev:  float,
    horizon:   int,
) -> dict:
    """Weighted blend of client and external forecasts."""

    def _bv(key: str) -> float:
        c_val = (client_fc or {}).get(key, 0) or 0
        e_val = ext_fc.get(key, 0) or 0
        if client_fc is None:
            return e_val
        return wc * c_val + we * e_val

    f3   = max(_bv("f3"),   base_rev * 0.5 if base_rev else 0)
    f6   = max(_bv("f6"),   base_rev * 0.5 if base_rev else 0)
    f12  = max(_bv("f12"),  base_rev * 0.5 if base_rev else 0)

    # Confidence interval widens as client weight decreases
    uncertainty = 0.15 + 0.25 * we
    lower = max(f12 * (1 - uncertainty), 0)
    upper = f12 * (1 + uncertainty)

    # If explicit CI from Prophet/linear → blend those too
    if client_fc:
        cl = client_fc.get("f12_lower", f12 * 0.85) or 0
        cu = client_fc.get("f12_upper", f12 * 1.15) or 0
        el = ext_fc.get("f12_lower",   f12 * 0.85) or 0
        eu = ext_fc.get("f12_upper",   f12 * 1.15) or 0
        lower = wc * cl + we * el
        upper = wc * cu + we * eu

    return {
        "f3":        round(f3, 0),
        "f6":        round(f6, 0),
        "f12":       round(f12, 0),
        "f12_lower": round(max(lower, 0), 0),
        "f12_upper": round(upper, 0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TREND
# ─────────────────────────────────────────────────────────────────────────────

def _compute_trend(
    history:   list,
    client_fc: Optional[dict],
) -> tuple:
    if client_fc and "monthly_pct" in client_fc:
        pct = client_fc["monthly_pct"]
    elif len(history) >= 2:
        import numpy as np
        revenues = [p.revenue for p in history]
        rates    = []
        for i in range(1, len(revenues)):
            if revenues[i - 1] > 0:
                rates.append((revenues[i] - revenues[i - 1]) / revenues[i - 1])
        pct = float(np.mean(rates)) if rates else 0.0
    else:
        pct = 0.0

    direction = "hausse" if pct > 0.02 else "baisse" if pct < -0.02 else "stable"
    return pct, direction


# ─────────────────────────────────────────────────────────────────────────────
# SEASONALITY PEAKS / LOWS
# ─────────────────────────────────────────────────────────────────────────────

def _sector_peaks_lows(indices: list, confidence_level: str) -> tuple:
    """Derive peak/low months from sector indices. Returns (peaks, lows, has_seasonality)."""
    if confidence_level == "NONE":
        # Return sector pattern as-is but flag it as external-only
        mean_i = sum(indices) / 12
        std_i  = (sum((x - mean_i) ** 2 for x in indices) / 12) ** 0.5
        peaks  = [i + 1 for i, v in enumerate(indices) if v > mean_i + 0.5 * std_i]
        lows   = [i + 1 for i, v in enumerate(indices) if v < mean_i - 0.5 * std_i]
        return sorted(peaks), sorted(lows), False  # has_seasonality=False: not confirmed by client data

    mean_i = sum(indices) / 12
    std_i  = (sum((x - mean_i) ** 2 for x in indices) / 12) ** 0.5
    if std_i < 0.05:
        return [], [], False

    peaks = [i + 1 for i, v in enumerate(indices) if v > mean_i + 0.5 * std_i]
    lows  = [i + 1 for i, v in enumerate(indices) if v < mean_i - 0.5 * std_i]
    return sorted(peaks), sorted(lows), std_i > 0.08


def _detect_seasonality_prophet(forecast) -> tuple:
    try:
        if "yearly" not in forecast.columns:
            return [], []
        monthly_avg = forecast.groupby(forecast["ds"].dt.month)["yearly"].mean()
        mean_v      = monthly_avg.mean()
        std_v       = monthly_avg.std()
        if std_v < 0.05:
            return [], []
        peaks = sorted([int(m) for m, v in monthly_avg.items() if v > mean_v + 0.5 * std_v])
        lows  = sorted([int(m) for m, v in monthly_avg.items() if v < mean_v - 0.5 * std_v])
        return peaks, lows
    except Exception:
        return [], []


# ─────────────────────────────────────────────────────────────────────────────
# ANOMALY DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_anomalies(history: list, sector_indices: list) -> list:
    """
    Months where client revenue deviates > 25% from what the sector pattern predicts.
    Only meaningful with >= 3 data points.
    """
    if len(history) < 3:
        return []

    try:
        from datetime import datetime

        revenues = [p.revenue for p in history]
        avg_rev  = sum(revenues) / len(revenues)
        if avg_rev <= 0:
            return []

        anomalies = []
        for point in history:
            try:
                month     = datetime.fromisoformat(point.date).month  # 1-indexed
                expected  = avg_rev * sector_indices[month - 1]
                actual    = point.revenue
                deviation = abs(actual - expected) / max(expected, 1e-9)
                if deviation > 0.25:
                    anomalies.append(month)
            except Exception:
                continue

        return sorted(set(anomalies))
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# REASONING GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def _generate_reasoning(
    suff:          dict,
    trend_dir:     str,
    trend_pct:     float,
    has_season:    bool,
    anomaly_months: list,
    peak_months:   list,
    low_months:    list,
    sector_data,
    secteur:       str,
    n_pts:         int,
) -> str:
    level     = suff["level"]
    wc        = suff["client_weight"]
    we        = suff["external_weight"]
    src_label = sector_data.source.replace("_", " ").title()

    # ── Opening: confidence framing ───────────────────────────────────────────
    confidence_phrases = {
        "NONE":     "Aucune donnée historique fournie. L'analyse repose entièrement sur les benchmarks sectoriels.",
        "VERY_LOW": f"Saisonnalité détectée avec une très faible confiance en raison des données limitées ({n_pts} point(s)).",
        "LOW":      f"Saisonnalité estimée avec une confiance faible ({n_pts} mois). Le signal sectoriel ({we:.0%}) compense le manque d'historique.",
        "MEDIUM":   f"Confiance moyenne — {n_pts} mois de données client ({wc:.0%}) renforcés par les benchmarks sectoriels ({we:.0%}).",
        "HIGH":     f"Confiance élevée — {n_pts} mois de données historiques ({wc:.0%} du modèle). Signal sectoriel utilisé pour validation ({we:.0%}).",
    }
    parts = [confidence_phrases.get(level, "")]

    # ── Trend observation ─────────────────────────────────────────────────────
    trend_str = {
        "hausse": f"Tendance mensuelle en hausse de {trend_pct:.1%}.",
        "baisse": f"Tendance mensuelle en baisse de {abs(trend_pct):.1%} — surveiller la trésorerie.",
        "stable": "Tendance mensuelle stable (< ±2%).",
    }.get(trend_dir, "")
    if trend_str:
        parts.append(trend_str)

    # ── Seasonality observation ───────────────────────────────────────────────
    if has_season and peak_months:
        peak_names = [_MONTH_NAMES[m - 1] for m in peak_months]
        parts.append(f"Saisonnalité détectée — pics prévus en {', '.join(peak_names)}.")
    elif not has_season and level not in ("NONE", "VERY_LOW"):
        parts.append("Pas de saisonnalité significative détectée sur le secteur.")

    # ── Anomaly warning ───────────────────────────────────────────────────────
    if anomaly_months:
        anom_names = [_MONTH_NAMES[m - 1] for m in anomaly_months]
        parts.append(
            f"Anomalie détectée en {', '.join(anom_names)} : vos revenus s'écartent "
            f"de plus de 25% du schéma sectoriel. Vérifiez les événements exceptionnels."
        )

    # ── Source transparency ───────────────────────────────────────────────────
    parts.append(f"Source externe : {src_label} ({secteur}).")

    return " ".join(p for p in parts if p)


# ─────────────────────────────────────────────────────────────────────────────
# STATIC FALLBACK (when sector_calendar unavailable)
# ─────────────────────────────────────────────────────────────────────────────

def _static_sector_fallback(secteur: str):
    """Minimal SectorSeasonalityData-like object using hardcoded defaults."""
    from dataclasses import dataclass as _dc, field as _f

    @_dc
    class _FallbackData:
        sector:         str
        indices:        list
        source:         str
        confidence:     float
        market_context: str
        fetched_at:     str

    default = [0.95, 0.94, 0.97, 0.98, 1.00, 0.98,
               0.96, 0.97, 1.02, 1.05, 1.07, 1.10]
    return _FallbackData(
        sector=secteur, indices=default, source="static",
        confidence=0.45, market_context="Données sectorielles par défaut.",
        fetched_at="",
    )
