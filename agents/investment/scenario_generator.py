"""
Scenario generator - creates conservative / optimal / aggressive funding scenarios.
"""

from agents.investment.config import SCENARIO_FACTORS, GRANTS_DATABASE, EQUITY_DEBT_SPLIT
from agents.investment.models import FundingScenario


class ScenarioGenerator:
    """Generates 3 funding scenarios using real grant data and stage-aware splits."""

    def generate(
        self,
        funding_needed: float,
        valuation: float,
        data: dict,
        available_grants: list = None,
    ) -> list:
        """
        Generate conservative / optimal / aggressive scenarios.

        Args:
            funding_needed : Total funding needed (TND)
            valuation      : Pre-money valuation (TND)
            data           : Startup data dict
            available_grants: List of grant dicts from BenchmarkEngine (optional)

        Returns:
            List of FundingScenario
        """
        stage = data.get("stage", "seed")
        equity_ratio, debt_ratio = EQUITY_DEBT_SPLIT.get(stage, (0.80, 0.20))

        # Total grants available
        grants_pool = self._total_grants(data, available_grants)

        scenarios = []
        for name, factor in SCENARIO_FACTORS.items():
            total_raise = funding_needed * factor

            # Grants first (capped at total raise)
            grants = min(grants_pool, total_raise * 0.30)  # max 30% from grants
            remaining = total_raise - grants

            equity = remaining * equity_ratio
            debt   = remaining * debt_ratio

            post_money  = valuation + equity
            dilution_pct = (equity / post_money * 100) if post_money > 0 else 0

            scenarios.append(FundingScenario(
                name=name,
                raise_amount=round(total_raise),
                grants=round(grants),
                equity=round(equity),
                debt=round(debt),
                pre_money=valuation,
                post_money=round(post_money),
                dilution_pct=round(dilution_pct, 2),
            ))

        return scenarios

    def _total_grants(self, data: dict, available_grants: list) -> float:
        """Sum up available grants, falling back to config if none provided."""
        if available_grants:
            return sum(g.get("amount", 0) for g in available_grants)

        # Fallback: config-based check
        total = 0
        industry = (data.get("industry") or data.get("sector", "")).lower()
        for grant in GRANTS_DATABASE.values():
            req = grant.get("requirements", {})
            sector_req = req.get("sector")
            if sector_req:
                allowed = sector_req if isinstance(sector_req, list) else [sector_req]
                if industry not in allowed:
                    continue
            total += grant["amount"]
        return total
