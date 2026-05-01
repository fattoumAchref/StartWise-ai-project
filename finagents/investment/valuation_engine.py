"""
Valuation engine - calculates startup valuation using multiple methods.
"""

from finagents.investment.config import INDUSTRY_MULTIPLES, DISCOUNT_RATE, TERMINAL_GROWTH_RATE
from finagents.investment.models import ValuationResult


class ValuationEngine:
    """Calculates valuation using Revenue Multiple, DCF, and Scorecard methods."""

    def calculate(self, data: dict) -> ValuationResult:
        """
        Calculate valuation using all available methods and blend them.

        Args:
            data: Extracted startup data dict

        Returns:
            ValuationResult
        """
        result = ValuationResult()

        revenue    = data.get("annual_revenue", 0)
        growth     = data.get("growth_rate", 0)
        industry   = data.get("industry", "tech")
        burn       = data.get("monthly_burn_rate", 0)
        team       = data.get("team_score", 0.5)
        product    = data.get("product_score", 0.5)
        market     = data.get("market_score", 0.5)
        traction   = data.get("traction_score", 0.5)

        estimates = []

        # Method 1: Revenue Multiple
        if revenue > 0:
            result.revenue_multiple = self._revenue_multiple(revenue, industry, growth)
            estimates.append((result.revenue_multiple, 0.5))

        # Method 2: DCF (only if revenue > 0 and growth known)
        if revenue > 0 and growth > 0:
            result.dcf = self._dcf(revenue, growth, burn)
            # DCF weight is lower for early stages (high uncertainty)
            stage = data.get("stage", "seed")
            dcf_weight = 0.1 if stage in ("idea", "pre-seed") else 0.2 if stage == "seed" else 0.3
            if result.dcf and result.dcf > 0:
                estimates.append((result.dcf, dcf_weight))

        # Method 3: Scorecard (always)
        base = result.revenue_multiple or 1_000_000
        result.scorecard = self._scorecard(base, team, product, market, traction)
        estimates.append((result.scorecard, 0.2 if revenue > 0 else 1.0))

        # Weighted blend
        total_weight = sum(w for _, w in estimates)
        result.final_valuation = sum(v * w for v, w in estimates) / total_weight

        # Round to nearest 100k
        result.final_valuation = round(result.final_valuation / 100_000) * 100_000

        if len(estimates) == 1:
            result.method_used = "scorecard_only"
        elif result.dcf:
            result.method_used = "hybrid_dcf"
        else:
            result.method_used = "hybrid"

        return result

    def _revenue_multiple(self, revenue: float, industry: str, growth_rate: float) -> float:
        base_multiple = INDUSTRY_MULTIPLES.get(industry.lower(), INDUSTRY_MULTIPLES["default"])

        # Growth premium: each 50% above 100% growth adds 10% to multiple
        if growth_rate > 1.0:
            premium = min((growth_rate - 1.0) * 0.2, 1.0)  # cap at 2x
            base_multiple *= (1 + premium)

        return round((revenue * base_multiple) / 100_000) * 100_000

    def _dcf(self, revenue: float, growth_rate: float, monthly_burn: float) -> float:
        """Simple 5-year DCF."""
        try:
            cash_flows = []
            r = revenue
            for year in range(1, 6):
                # Revenue grows, burn stays constant (conservative)
                r = r * (1 + growth_rate * max(1 - year * 0.15, 0.3))
                annual_burn = monthly_burn * 12
                fcf = r - annual_burn
                pv = fcf / ((1 + DISCOUNT_RATE) ** year)
                cash_flows.append(pv)

            # Terminal value
            terminal_fcf = cash_flows[-1] * (1 + TERMINAL_GROWTH_RATE)
            terminal_value = terminal_fcf / (DISCOUNT_RATE - TERMINAL_GROWTH_RATE)
            terminal_pv = terminal_value / ((1 + DISCOUNT_RATE) ** 5)

            dcf_value = sum(cash_flows) + terminal_pv
            return max(round(dcf_value / 100_000) * 100_000, 0)
        except Exception:
            return None

    def _scorecard(
        self,
        base: float,
        team_score: float,
        product_score: float,
        market_score: float,
        traction_score: float,
    ) -> float:
        weights = {"team": 0.30, "product": 0.25, "market": 0.25, "traction": 0.20}
        composite = (
            team_score    * weights["team"] +
            product_score * weights["product"] +
            market_score  * weights["market"] +
            traction_score * weights["traction"]
        )
        # Adjustment factor: 0.5x–1.5x base
        adjustment = 0.5 + composite
        return round((base * adjustment) / 100_000) * 100_000
