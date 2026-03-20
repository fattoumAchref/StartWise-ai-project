"""
Finance Agent - analyzes startup financials and produces structured output
for the Investment Agent.
"""

from orchestrateur.models import AgentMessage, StartupProject


class FinanceAgent:
    """
    Analyzes financial data from a StartupProject.
    Produces the data contract expected by InvestmentAgent.input_handler.
    """

    def analyze(self, project: StartupProject) -> AgentMessage:
        print(f"\n[Finance Agent] Analyzing {project.project_id}...")

        revenue      = project.annual_revenue or 0
        burn_rate    = project.monthly_burn_rate or 50_000
        growth_rate  = project.growth_rate or 0.5
        funding      = project.funding_needed or (burn_rate * 18)

        # Break-even estimate: month when cumulative revenue covers burn
        runway_months = int(funding / burn_rate) if burn_rate > 0 else 18
        monthly_revenue = revenue / 12
        break_even = None
        cumulative = 0
        for month in range(1, 37):
            monthly_rev = monthly_revenue * ((1 + growth_rate / 12) ** month)
            cumulative += monthly_rev - burn_rate
            if cumulative >= 0:
                break_even = month
                break

        # Traction score: based on revenue and growth
        traction = min(0.3 + (revenue / 1_000_000) * 0.4 + growth_rate * 0.1, 1.0)

        data = {
            "projected_revenue":    revenue,
            "revenue_growth_rate":  growth_rate,
            "monthly_burn_rate":    burn_rate,
            "runway_months":        runway_months,
            "funding_needed":       funding,
            "break_even_month":     break_even,
            "traction_score":       round(traction, 2),
            "implied_valuation":    revenue * 7 if revenue > 0 else 1_000_000,
            "has_export":           False,
            "company_age":          3,
        }

        print(f"[Finance Agent] ✓ revenue={revenue:,.0f} TND | burn={burn_rate:,.0f}/mo | runway={runway_months}mo")

        return AgentMessage(
            agent_id="finance",
            project_id=project.project_id,
            recommendation=f"Raise {funding:,.0f} TND for {runway_months}-month runway",
            confidence_score=0.80,
            data=data,
        )
