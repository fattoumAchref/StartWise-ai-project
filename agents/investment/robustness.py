"""
Robustness module — Medium-impact features:

1. MultiRoundDilution   — dilution waterfall across 3 funding rounds
2. SensitivityAnalysis  — valuation sensitivity to key assumptions
3. ExitScenarios        — founder wealth at exit in year 5
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from agents.investment.config import INDUSTRY_MULTIPLES


# ─────────────────────────────────────────────────────────────────────────────
# 1. MULTI-ROUND DILUTION WATERFALL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RoundResult:
    round_name:       str
    raise_amount:     float
    pre_money:        float
    post_money:       float
    investor_pct:     float
    founder_pct:      float   # cumulative founder ownership after this round
    option_pool_pct:  float


class MultiRoundDilution:
    """
    Models founder dilution across 3 sequential funding rounds.

    Standard Tunisian/MENA progression:
      Round 1 (current)  : as computed by the agent
      Round 2 (seed)     : ~2x current raise, valuation grows 3x
      Round 3 (series_a) : ~5x current raise, valuation grows 5x
    """

    ROUND_PROFILES = {
        "idea": [
            {"name": "Pre-seed (actuel)", "raise_factor": 1.0,  "val_factor": 1.0,  "option_pool": 0.10},
            {"name": "Seed",              "raise_factor": 2.5,  "val_factor": 4.0,  "option_pool": 0.08},
            {"name": "Series A",          "raise_factor": 8.0,  "val_factor": 12.0, "option_pool": 0.05},
        ],
        "seed": [
            {"name": "Seed (actuel)",     "raise_factor": 1.0,  "val_factor": 1.0,  "option_pool": 0.10},
            {"name": "Series A",          "raise_factor": 4.0,  "val_factor": 5.0,  "option_pool": 0.08},
            {"name": "Series B",          "raise_factor": 10.0, "val_factor": 15.0, "option_pool": 0.05},
        ],
        "series_a": [
            {"name": "Series A (actuel)", "raise_factor": 1.0,  "val_factor": 1.0,  "option_pool": 0.08},
            {"name": "Series B",          "raise_factor": 3.0,  "val_factor": 4.0,  "option_pool": 0.05},
            {"name": "Series C",          "raise_factor": 8.0,  "val_factor": 10.0, "option_pool": 0.03},
        ],
        "growth": [
            {"name": "Series A (actuel)", "raise_factor": 1.0,  "val_factor": 1.0,  "option_pool": 0.05},
            {"name": "Series B",          "raise_factor": 2.5,  "val_factor": 3.0,  "option_pool": 0.03},
            {"name": "Series C",          "raise_factor": 6.0,  "val_factor": 8.0,  "option_pool": 0.02},
        ],
    }

    def compute(
        self,
        stage:          str,
        current_raise:  float,
        current_premoney: float,
        founder_start:  float = 0.80,
    ) -> list[RoundResult]:
        """
        Compute cumulative founder ownership after each round.

        Args:
            stage           : current startup stage
            current_raise   : current round raise amount (TND)
            current_premoney: current pre-money valuation (TND)
            founder_start   : founder ownership before any round (default 80%)

        Returns:
            List of RoundResult, one per round
        """
        profiles = self.ROUND_PROFILES.get(stage, self.ROUND_PROFILES["seed"])
        results  = []
        founder_pct = founder_start

        for p in profiles:
            raise_amt  = round(current_raise * p["raise_factor"])
            pre_money  = round(current_premoney * p["val_factor"])
            option_pool = p["option_pool"]

            # Option pool carved pre-money
            founder_pct = founder_pct * (1 - option_pool)

            # Investor dilution
            post_money   = pre_money + raise_amt
            investor_pct = raise_amt / post_money if post_money > 0 else 0
            founder_pct  = founder_pct * (1 - investor_pct)

            results.append(RoundResult(
                round_name      = p["name"],
                raise_amount    = raise_amt,
                pre_money       = pre_money,
                post_money      = post_money,
                investor_pct    = round(investor_pct * 100, 1),
                founder_pct     = round(founder_pct * 100, 1),
                option_pool_pct = round(option_pool * 100, 1),
            ))

        return results


# ─────────────────────────────────────────────────────────────────────────────
# 2. SENSITIVITY ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SensitivityRow:
    assumption:   str
    base_value:   str
    minus_20_val: float   # valuation at -20%
    base_val:     float   # valuation at base
    plus_20_val:  float   # valuation at +20%
    impact:       str     # "high" | "medium" | "low"


class SensitivityAnalysis:
    """
    Shows how the final valuation changes when key assumptions shift ±20%.
    Uses the same revenue multiple + scorecard logic as ValuationEngine.
    """

    def compute(
        self,
        annual_revenue:  float,
        growth_rate:     float,
        team_score:      float,
        market_score:    float,
        industry:        str,
        base_valuation:  float,
    ) -> list[SensitivityRow]:
        """
        Returns sensitivity rows for: revenue, growth rate, team score, market score.
        """
        rows = []
        multiple = INDUSTRY_MULTIPLES.get(industry.lower(), INDUSTRY_MULTIPLES["default"])

        def _val(rev, growth, team, market):
            # Revenue multiple
            m = multiple
            if growth > 1.0:
                m *= (1 + min((growth - 1.0) * 0.2, 1.0))
            rev_val = rev * m if rev > 0 else 0

            # Scorecard adjustment
            composite = team * 0.30 + 0.65 * 0.25 + market * 0.25 + 0.5 * 0.20
            scorecard = (rev_val or 1_000_000) * (0.5 + composite)

            # Blend (simplified: 50% rev multiple, 20% scorecard)
            if rev > 0:
                blended = (rev_val * 0.5 + scorecard * 0.2) / 0.7
            else:
                blended = scorecard
            return round(blended / 100_000) * 100_000

        base = base_valuation

        # Revenue sensitivity
        if annual_revenue > 0:
            v_minus = _val(annual_revenue * 0.8, growth_rate, team_score, market_score)
            v_plus  = _val(annual_revenue * 1.2, growth_rate, team_score, market_score)
            impact  = "high" if abs(v_plus - v_minus) / base > 0.3 else "medium"
            rows.append(SensitivityRow(
                assumption   = "Revenus annuels",
                base_value   = f"{annual_revenue:,.0f} TND",
                minus_20_val = v_minus,
                base_val     = base,
                plus_20_val  = v_plus,
                impact       = impact,
            ))

        # Growth rate sensitivity
        if growth_rate > 0:
            v_minus = _val(annual_revenue, growth_rate * 0.8, team_score, market_score)
            v_plus  = _val(annual_revenue, growth_rate * 1.2, team_score, market_score)
            impact  = "high" if abs(v_plus - v_minus) / base > 0.2 else "medium"
            rows.append(SensitivityRow(
                assumption   = "Taux de croissance",
                base_value   = f"{growth_rate*100:.0f}%",
                minus_20_val = v_minus,
                base_val     = base,
                plus_20_val  = v_plus,
                impact       = impact,
            ))

        # Team score sensitivity
        v_minus = _val(annual_revenue, growth_rate, max(team_score * 0.8, 0.1), market_score)
        v_plus  = _val(annual_revenue, growth_rate, min(team_score * 1.2, 1.0), market_score)
        rows.append(SensitivityRow(
            assumption   = "Score equipe",
            base_value   = f"{team_score:.2f}",
            minus_20_val = v_minus,
            base_val     = base,
            plus_20_val  = v_plus,
            impact       = "medium",
        ))

        # Market score sensitivity
        v_minus = _val(annual_revenue, growth_rate, team_score, max(market_score * 0.8, 0.1))
        v_plus  = _val(annual_revenue, growth_rate, team_score, min(market_score * 1.2, 1.0))
        rows.append(SensitivityRow(
            assumption   = "Score marche",
            base_value   = f"{market_score:.2f}",
            minus_20_val = v_minus,
            base_val     = base,
            plus_20_val  = v_plus,
            impact       = "low",
        ))

        return rows


# ─────────────────────────────────────────────────────────────────────────────
# 3. EXIT SCENARIO MODELING
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExitScenario:
    name:              str
    exit_multiple:     float   # EV/Revenue multiple at exit
    revenue_year5:     float   # projected revenue at year 5 (TND)
    exit_valuation:    float   # total company value at exit (TND)
    founder_proceeds:  float   # founder's share of exit (TND)
    roi_multiple:      float   # founder proceeds / current pre-money


class ExitScenarios:
    """
    Models founder wealth at exit in year 5 under 3 scenarios.
    Uses projected revenue growth and sector exit multiples.
    """

    # Typical exit multiples by sector (EV/Revenue)
    EXIT_MULTIPLES = {
        "saas":        {"bear": 4.0, "base": 8.0,  "bull": 15.0},
        "fintech":     {"bear": 3.0, "base": 6.0,  "bull": 12.0},
        "tech":        {"bear": 3.0, "base": 6.0,  "bull": 10.0},
        "healthtech":  {"bear": 2.5, "base": 5.0,  "bull": 9.0},
        "marketplace": {"bear": 2.0, "base": 4.0,  "bull": 8.0},
        "edtech":      {"bear": 2.0, "base": 4.0,  "bull": 7.0},
        "ecommerce":   {"bear": 1.5, "base": 3.0,  "bull": 5.0},
        "logistics":   {"bear": 1.5, "base": 3.0,  "bull": 5.0},
        "agritech":    {"bear": 1.5, "base": 3.0,  "bull": 6.0},
        "cleantech":   {"bear": 2.0, "base": 4.0,  "bull": 8.0},
        "default":     {"bear": 2.0, "base": 4.0,  "bull": 8.0},
    }

    def compute(
        self,
        annual_revenue:   float,
        growth_rate:      float,
        industry:         str,
        pre_money:        float,
        founder_after_pct: float,  # founder % after current round
    ) -> list[ExitScenario]:
        """
        Args:
            annual_revenue    : current annual revenue (TND)
            growth_rate       : annual growth rate (e.g. 0.8 = 80%)
            industry          : sector
            pre_money         : current pre-money valuation (TND)
            founder_after_pct : founder ownership after current round (%)

        Returns:
            3 exit scenarios: bear / base / bull
        """
        multiples = self.EXIT_MULTIPLES.get(industry.lower(), self.EXIT_MULTIPLES["default"])
        founder_share = founder_after_pct / 100

        # Project revenue to year 5 with decaying growth
        # Growth decays by 15% per year (realistic for early-stage)
        rev = annual_revenue if annual_revenue > 0 else 100_000  # floor for idea stage
        for year in range(1, 6):
            effective_growth = growth_rate * max(1 - year * 0.12, 0.25)
            rev = rev * (1 + effective_growth)
        revenue_year5 = round(rev)

        scenarios = []
        for scenario_name, mult_key in [("Pessimiste", "bear"), ("Realiste", "base"), ("Optimiste", "bull")]:
            mult          = multiples[mult_key]
            exit_val      = round(revenue_year5 * mult)
            proceeds      = round(exit_val * founder_share)
            roi           = round(proceeds / pre_money, 1) if pre_money > 0 else 0

            scenarios.append(ExitScenario(
                name             = scenario_name,
                exit_multiple    = mult,
                revenue_year5    = revenue_year5,
                exit_valuation   = exit_val,
                founder_proceeds = proceeds,
                roi_multiple     = roi,
            ))

        return scenarios
