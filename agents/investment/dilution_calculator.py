"""
Dilution calculator - computes founder ownership after a funding round.
"""

from agents.investment.models import DilutionResult


class DilutionCalculator:
    """Calculates founder dilution including option pool."""

    def calculate(
        self,
        pre_money: float,
        equity_amount: float,
        founder_ownership_before: float = 0.80,
        option_pool: float = 0.10,
    ) -> DilutionResult:
        """
        Calculate dilution after equity raise.

        The option pool is carved out of the pre-money (standard practice),
        which means it dilutes founders before the investor comes in.

        Args:
            pre_money              : Pre-money valuation (TND)
            equity_amount          : Equity raised (TND)
            founder_ownership_before: Founder % before round (default 80%)
            option_pool            : Option pool to create (default 10%)

        Returns:
            DilutionResult
        """
        # Step 1: Option pool dilutes founders pre-money
        founder_after_pool = founder_ownership_before * (1 - option_pool)

        # Step 2: Investor dilutes everyone post-money
        post_money = pre_money + equity_amount
        new_investor_pct = equity_amount / post_money if post_money > 0 else 0

        dilution_factor = 1 - new_investor_pct
        founder_after_round = founder_after_pool * dilution_factor

        founder_dilution = founder_ownership_before - founder_after_round

        return DilutionResult(
            pre_money=pre_money,
            raise_amount=equity_amount,
            post_money=round(post_money),
            new_investor_pct=round(new_investor_pct * 100, 2),
            founder_before_pct=round(founder_ownership_before * 100, 2),
            founder_after_pct=round(founder_after_round * 100, 2),
            founder_dilution_pct=round(founder_dilution * 100, 2),
        )
