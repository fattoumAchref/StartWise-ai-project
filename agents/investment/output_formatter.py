"""
Output formatter - creates final investment recommendation.
"""

from agents.investment.models import InvestmentRecommendation


class OutputFormatter:
    """Formats final investment recommendation."""

    NEXT_STEPS = {
        "idea": [
            "Join an incubator (Flat6Labs, Cogite, or StartupHouse)",
            "Validate your idea with 20+ potential customers",
            "Apply for Smart Capital Pre-Seed grant (50k TND)",
        ],
        "pre-seed": [
            "Apply for Startup Act label at startup.gov.tn",
            "Pitch to angel investors and family offices",
            "Build MVP and reach first 10 paying customers",
        ],
        "seed": [
            "Apply for Startup Act label (if not yet labeled)",
            "Target accelerators: Flat6Labs, Wamda, Sawari Ventures",
            "Prepare pitch deck with traction metrics",
        ],
        "early": [
            "Approach seed VCs: AfricInvest, BIAT Capital, Algebra Ventures",
            "Apply for BTS Innovation Grant if tech/export-oriented",
            "Prepare 18-month financial model for due diligence",
        ],
        "growth": [
            "Target Series A VCs: Partech Africa, AfricInvest, Endeavor",
            "Explore debt financing via BTS or Amen Bank",
            "Consider FAMEX grant for export expansion",
        ],
        "scale": [
            "Engage growth equity funds and international VCs",
            "Explore strategic partnerships or acquisition opportunities",
            "Prepare for potential IPO or secondary market listing",
        ],
    }

    def format(self, valuation, optimal_scenario, all_scenarios, dilution, data) -> InvestmentRecommendation:
        text = self._build_text(valuation, optimal_scenario, dilution, data)
        confidence = self._calculate_confidence(data, valuation)

        return InvestmentRecommendation(
            recommendation=text,
            confidence_score=confidence,
            valuation=valuation,
            optimal_scenario=optimal_scenario,
            all_scenarios=all_scenarios,
            dilution=dilution,
        )

    def _build_text(self, valuation, scenario, dilution, data) -> str:
        sector = data.get("sector") or data.get("industry", "N/A")
        stage  = data.get("stage", "seed")

        # Market context
        sample_size = data.get("market_sample_size", 0)
        act_rate    = data.get("startup_act_rate")
        market_line = f"Market data  : {sample_size} similar {sector} startups in Tunisia"
        if act_rate is not None:
            market_line += f" | Startup Act rate: {act_rate*100:.0f}%"

        # Valuation methods breakdown
        # DCF is unreliable at idea/pre-seed — hide it to avoid misleading numbers
        show_dcf = stage not in ("idea", "pre-seed")
        methods = []
        if valuation.revenue_multiple:
            methods.append(f"Revenue multiple: {valuation.revenue_multiple:,.0f} TND")
        if valuation.dcf and show_dcf:
            methods.append(f"DCF            : {valuation.dcf:,.0f} TND")
        if valuation.scorecard:
            methods.append(f"Scorecard      : {valuation.scorecard:,.0f} TND")
        methods_text = "\n  ".join(methods) if methods else "N/A"

        # Grants
        grants_list = data.get("available_grants", [])
        if grants_list:
            total_grants = sum(g.get("amount", 0) for g in grants_list)
            grants_text = "\n".join(
                f"  - {g['name']}: {g['amount']:,.0f} TND"
                for g in grants_list
            )
            grants_text += f"\n  Total potential: {total_grants:,.0f} TND"
        else:
            grants_text = "  - No matching grants found"

        # All scenarios comparison
        scenarios_text = ""
        for s in sorted(data.get("_all_scenarios", []), key=lambda x: x.get("score", 0), reverse=True):
            scenarios_text += f"\n  {s['name']:<14} raise: {s['raise_amount']:>10,.0f} TND  dilution: {s['dilution_pct']:.1f}%  score: {s['score']:.0f}"

        # Stage-aware next steps
        steps = self.NEXT_STEPS.get(stage, self.NEXT_STEPS["seed"])
        steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))

        return f"""
INVESTMENT RECOMMENDATION
{'='*55}
Stage        : {stage.upper()}
Sector       : {sector}
{market_line}

VALUATION  ({valuation.method_used})
  {methods_text}
  >> Final: {valuation.final_valuation:,.0f} TND (pre-money)

OPTIMAL STRATEGY  ({scenario.name.upper()})
  Total raise : {scenario.raise_amount:,.0f} TND
  Grants      : {scenario.grants:,.0f} TND  ({scenario.grants/scenario.raise_amount*100:.0f}%)
  Equity      : {scenario.equity:,.0f} TND  ({scenario.equity/scenario.raise_amount*100:.0f}%)
  Debt        : {scenario.debt:,.0f} TND  ({scenario.debt/scenario.raise_amount*100:.0f}%)
  Post-money  : {scenario.post_money:,.0f} TND

DILUTION
  Before round : {dilution.founder_before_pct:.1f}%
  After round  : {dilution.founder_after_pct:.1f}%
  Diluted by   : {dilution.founder_dilution_pct:.1f}%  (incl. {10:.0f}% option pool)

ELIGIBLE GRANTS
{grants_text}

NEXT STEPS
{steps_text}
""".strip()

    def _calculate_confidence(self, data: dict, valuation) -> float:
        confidence = 0.60  # base

        # Revenue data available
        if data.get("annual_revenue", 0) > 0:
            confidence += 0.10

        # Multiple valuation methods used
        if valuation.method_used == "hybrid_dcf":
            confidence += 0.10
        elif valuation.method_used == "hybrid":
            confidence += 0.05

        # Strong team/market signals
        if data.get("team_score", 0) >= 0.7:
            confidence += 0.05
        if data.get("market_score", 0) >= 0.7:
            confidence += 0.05

        # Real market data available
        if data.get("market_sample_size", 0) >= 10:
            confidence += 0.05

        return min(round(confidence, 2), 0.95)
