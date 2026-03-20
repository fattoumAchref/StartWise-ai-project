"""
Strategy selector - scores and picks the optimal funding scenario.
"""

from agents.investment.models import FundingScenario


class StrategySelector:
    """Scores scenarios and selects the best one."""

    # Max acceptable dilution by stage
    DILUTION_TARGETS = {
        "idea":     15,
        "pre-seed": 15,
        "seed":     20,
        "early":    25,
        "growth":   30,
        "scale":    20,
    }

    def select_optimal(self, scenarios: list, stage: str = "seed") -> FundingScenario:
        """
        Score each scenario and return the best.

        Scoring (100 base):
        - Dilution vs target: -5 per % over target, +5 if under
        - Grants ratio: +20 max bonus
        - Scenario name: +10 for "optimal" (balanced raise)
        - Debt ratio: -5 if debt > 30% of raise (risky for early stage)
        """
        target_dilution = self.DILUTION_TARGETS.get(stage, 25)

        for s in scenarios:
            score = 100.0

            # Dilution scoring
            diff = s.dilution_pct - target_dilution
            if diff > 0:
                score -= diff * 5   # penalty for over-dilution
            else:
                score += abs(diff) * 2  # small bonus for under-dilution

            # Grants bonus (up to +20)
            grants_ratio = s.grants / s.raise_amount if s.raise_amount > 0 else 0
            score += grants_ratio * 20

            # Balanced raise bonus
            if s.name == "optimal":
                score += 10

            # Debt risk penalty for early stages
            debt_ratio = s.debt / s.raise_amount if s.raise_amount > 0 else 0
            if stage in ("idea", "pre-seed", "seed") and debt_ratio > 0.20:
                score -= 10

            s.score = round(score, 1)

        scenarios.sort(key=lambda s: s.score, reverse=True)
        return scenarios[0]
