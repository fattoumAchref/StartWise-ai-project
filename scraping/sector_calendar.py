"""
scraping/sector_calendar.py
Hybrid sector seasonality: static indices + Yahoo Finance quarterly cache.
No runtime API calls during analysis — offline-first, cache-backed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path("./data/sector_seasonality_cache.json")
CACHE_TTL_DAYS = 30

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SectorSeasonalityData:
    """Monthly seasonality indices for a sector (12 values, mean ≈ 1.0)."""
    sector:         str
    indices:        List[float]   # indices[0]=Jan … indices[11]=Dec
    source:         str           # "yahoo_finance" | "static" | "hybrid"
    confidence:     float         # [0-1] — 1 = derived from real market data
    market_context: str           # human-readable macro note
    fetched_at:     str           # ISO datetime


# ─────────────────────────────────────────────────────────────────────────────
# STATIC SECTOR INDICES — offline fallback, research-based
# Sources: SaaStr Annual, a16z, OpenView SaaS Benchmarks, MENA Venture Report
# ─────────────────────────────────────────────────────────────────────────────

# Monthly multipliers Jan–Dec, normalized so mean = 1.0
STATIC_SECTOR_INDICES: Dict[str, List[float]] = {
    # B2B SaaS: enterprise Q4 budget flush, Q1 slow start
    "saas": [0.85, 0.88, 0.92, 0.95, 0.97, 0.93,
             0.88, 0.90, 0.98, 1.05, 1.15, 1.22],

    # Marketplace: holiday shopping Nov-Dec, low Jan-Feb
    "marketplace": [0.82, 0.80, 0.90, 0.92, 0.95, 0.93,
                    0.92, 0.94, 0.98, 1.05, 1.25, 1.35],

    # E-commerce: same seasonal drivers as marketplace
    "ecommerce": [0.82, 0.80, 0.90, 0.92, 0.95, 0.93,
                  0.92, 0.94, 0.98, 1.05, 1.25, 1.35],

    # Food delivery: MENA summer peaks, softens during Ramadan fasting hours
    "food_delivery": [0.88, 0.85, 0.82, 0.90, 0.95, 1.10,
                      1.15, 1.12, 1.05, 1.00, 0.98, 1.05],

    # Fintech: tax season Q1, Q4 enterprise contract renewals
    "fintech": [1.10, 1.08, 1.05, 0.95, 0.93, 0.90,
                0.88, 0.87, 0.95, 1.02, 1.10, 1.15],

    # EdTech: school calendar — Sep/Jan spikes, summer collapse
    "edtech": [1.15, 1.10, 1.02, 0.95, 0.90, 0.75,
               0.65, 0.80, 1.25, 1.10, 1.05, 1.00],

    # HR/Recruiting: January hiring surge, summer slow
    "hrtech": [1.20, 1.15, 1.05, 1.00, 0.98, 0.88,
               0.80, 0.82, 1.05, 1.05, 1.02, 0.95],

    # Healthcare: steady with slight Q1 spike (new insurance year)
    "healthtech": [1.10, 1.05, 1.02, 1.00, 0.98, 0.97,
                   0.96, 0.97, 1.00, 1.02, 1.04, 1.06],

    # Default / generic early-stage startup
    "default": [0.95, 0.94, 0.97, 0.98, 1.00, 0.98,
                0.96, 0.97, 1.02, 1.05, 1.07, 1.10],
}

# Tickers per sector for Yahoo Finance quarterly revenue extraction
SECTOR_TICKERS: Dict[str, List[str]] = {
    "saas":          ["CRM", "SNOW", "DDOG"],
    "marketplace":   ["ETSY", "EBAY"],
    "ecommerce":     ["SHOP", "ETSY"],
    "food_delivery": ["DASH", "UBER"],
    "fintech":       ["SQ", "PYPL"],
    "edtech":        ["DUOL", "CHGG"],
}

# ─────────────────────────────────────────────────────────────────────────────
# MENA MACRO CALENDAR
# ─────────────────────────────────────────────────────────────────────────────

# Approximate Ramadan start month (1-indexed) per Gregorian year
RAMADAN_START_MONTH: Dict[int, int] = {
    2023: 3,   # March
    2024: 3,   # March
    2025: 3,   # March  (~March 1)
    2026: 2,   # February (~Feb 18)
    2027: 2,   # February
    2028: 1,   # January
}

MENA_COUNTRIES = {"TN", "MA", "DZ", "EG", "SA", "AE", "QA", "KW", "LY", "JO"}

_MONTH_NAMES = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]


def get_mena_context(month: int, year: Optional[int] = None) -> Optional[str]:
    """Return a human-readable note if a known MENA macro event affects this month."""
    year = year or datetime.now().year
    rm   = RAMADAN_START_MONTH.get(year)
    if rm:
        if month == rm:
            return f"Ramadan {year} : activité diurne réduite (~-20%), pics nocturnes"
        if month == rm % 12 + 1:
            return f"Post-Ramadan / Eid {year} : rebond consommation +10-15%"
    if month == 12:
        return "Décembre : fin d'exercice — pic budgets B2B, consommation grand public"
    if month == 1:
        return "Janvier : début d'exercice — ralentissement décisionnel B2B"
    if month in (6, 7, 8):
        return "Été MENA : chaleur → hausse livraison/digital, baisse présentiel"
    return None


def _apply_mena_adjustments(
    indices: List[float], pays: str, year: int
) -> List[float]:
    """Shift monthly indices by known MENA seasonal effects (Ramadan etc.)."""
    if pays not in MENA_COUNTRIES:
        return indices

    adjusted = indices[:]
    rm = RAMADAN_START_MONTH.get(year)
    if rm and 1 <= rm <= 12:
        adjusted[rm - 1] = round(adjusted[rm - 1] * 0.82, 3)   # -18% Ramadan
        next_m = rm % 12                                         # 0-indexed next month
        adjusted[next_m] = round(adjusted[next_m] * 1.12, 3)   # +12% post-Ramadan
    return adjusted


# ─────────────────────────────────────────────────────────────────────────────
# DISK CACHE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_cache(cache_path: Path) -> dict:
    try:
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(cache_path: Path, data: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not save seasonality cache: {e}")


def _cache_is_fresh(entry: dict, ttl_days: int = CACHE_TTL_DAYS) -> bool:
    try:
        fetched = datetime.fromisoformat(entry.get("fetched_at", "2000-01-01"))
        return (datetime.now() - fetched).days < ttl_days
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# YAHOO FINANCE — quarterly revenue → monthly seasonality pattern
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_yahoo_quarterly_pattern(tickers: List[str]) -> Optional[List[float]]:
    """
    Fetch quarterly revenue from Yahoo Finance for the given tickers.
    Aggregates Q1/Q2/Q3/Q4 weights across tickers and returns 12 monthly
    seasonality indices (mean = 1.0).
    No runtime dependency: called only during cache refresh, never during analysis.
    """
    try:
        import numpy as np
        import yfinance as yf

        q_buckets: Dict[int, List[float]] = {1: [], 2: [], 3: [], 4: []}

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                qf    = stock.quarterly_financials
                if qf is None or qf.empty:
                    continue

                rev_row = None
                for label in ("Total Revenue", "TotalRevenue", "Revenue"):
                    if label in qf.index:
                        rev_row = qf.loc[label]
                        break
                if rev_row is None:
                    continue

                for col in rev_row.index:
                    try:
                        month = col.month
                        q     = (month - 1) // 3 + 1
                        val   = float(rev_row[col])
                        if val > 0:
                            q_buckets[q].append(val)
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Yahoo Finance {ticker}: {e}")

        q_means = {
            q: float(np.mean(vals)) if vals else 1.0
            for q, vals in q_buckets.items()
        }
        total = sum(q_means.values())
        if total == 0:
            return None

        # Normalize: mean quarter = 1.0
        q_shares = {q: v / total * 4 for q, v in q_means.items()}

        # Expand Q → 3 months (equal within quarter; intra-quarter smoothing in v2)
        monthly = []
        for q in range(1, 5):
            monthly.extend([round(q_shares[q], 3)] * 3)

        mean_val = sum(monthly) / 12
        return [round(v / mean_val, 3) for v in monthly]

    except Exception as e:
        logger.warning(f"Yahoo Finance quarterly fetch failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_sector_seasonality(
    secteur:       str,
    pays:          str   = "TN",
    cache_path:    Path  = CACHE_PATH,
    force_refresh: bool  = False,
) -> SectorSeasonalityData:
    """
    Hybrid lookup — priority order:
      1. Disk cache (TTL = 30 days)
      2. Yahoo Finance live fetch → saved to cache
      3. Static hardcoded indices (always available)
    Then applies MENA macro calendar adjustments.
    """
    sector_key = (secteur or "default").lower().replace(" ", "_").replace("-", "_")
    year       = datetime.now().year

    # ── 1. Cache check ────────────────────────────────────────────────────────
    cache  = _load_cache(cache_path)
    cached = cache.get(sector_key)

    if cached and not force_refresh and _cache_is_fresh(cached):
        indices    = cached["indices"]
        source     = cached.get("source", "cache")
        confidence = cached.get("confidence", 0.70)
    else:
        # ── 2. Yahoo Finance fetch ────────────────────────────────────────────
        tickers       = SECTOR_TICKERS.get(sector_key, [])
        yahoo_indices = _fetch_yahoo_quarterly_pattern(tickers) if tickers else None

        if yahoo_indices:
            indices    = yahoo_indices
            source     = "yahoo_finance"
            confidence = 0.80
        else:
            # ── 3. Static fallback ────────────────────────────────────────────
            indices    = STATIC_SECTOR_INDICES.get(sector_key, STATIC_SECTOR_INDICES["default"])
            source     = "static"
            confidence = 0.55

        cache[sector_key] = {
            "indices":    indices,
            "source":     source,
            "confidence": confidence,
            "fetched_at": datetime.now().isoformat(),
        }
        _save_cache(cache_path, cache)

    # ── MENA adjustments ──────────────────────────────────────────────────────
    indices = _apply_mena_adjustments(indices, pays, year)

    # ── Market context string ─────────────────────────────────────────────────
    peak_m = indices.index(max(indices)) + 1
    low_m  = indices.index(min(indices)) + 1
    parts  = [
        f"Pic sectoriel : {_MONTH_NAMES[peak_m - 1]} ({indices[peak_m - 1]:.2f}x)",
        f"Creux : {_MONTH_NAMES[low_m - 1]} ({indices[low_m - 1]:.2f}x)",
    ]
    mena_note = get_mena_context(datetime.now().month, year)
    if mena_note:
        parts.append(mena_note)

    return SectorSeasonalityData(
        sector         = sector_key,
        indices        = indices,
        source         = source,
        confidence     = confidence,
        market_context = " · ".join(parts),
        fetched_at     = datetime.now().isoformat(),
    )
