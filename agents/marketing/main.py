"""
Marketing Agent - analyzes market positioning and produces structured output
for the Investment Agent.
"""

from orchestrateur.models import AgentMessage, StartupProject


class MarketingAgent:
    """
    Analyzes market data from a StartupProject.
    Produces the data contract expected by InvestmentAgent.input_handler.
    """

    # Sector-based market score priors (Tunisia context)
    SECTOR_MARKET_SCORES = {
        "fintech":     0.85,
        "healthtech":  0.80,
        "edtech":      0.75,
        "saas":        0.80,
        "tech":        0.75,
        "ecommerce":   0.70,
        "marketplace": 0.72,
        "logistics":   0.68,
        "agritech":    0.65,
        "cleantech":   0.65,
        "artisanat":   0.60,
        "food":        0.60,
        "travel":      0.62,
        "retail":      0.55,
        "other":       0.60,
    }

    def analyze(self, project: StartupProject) -> AgentMessage:
        print(f"\n[Marketing Agent] Analyzing {project.project_id}...")

        industry = (project.industry or "tech").lower()
        tam      = project.tam or 1_000_000_000
        team_size = project.team_size or 3

        market_score  = self.SECTOR_MARKET_SCORES.get(industry, 0.65)
        team_score    = min(0.4 + team_size * 0.06, 0.95)   # grows with team size
        product_score = 0.65  # default — no product data yet

        data = {
            "industry":                  industry,
            "total_addressable_market":  tam,
            "projected_market_share_pct": 0.02,
            "team_score":                round(team_score, 2),
            "product_score":             product_score,
            "market_score":              market_score,
            "target_segment":            "B2C" if industry in ("ecommerce", "food", "travel", "artisanat") else "B2B",
        }

        print(f"[Marketing Agent] ✓ industry={industry} | TAM={tam/1e6:.0f}M TND | market_score={market_score}")

        return AgentMessage(
            agent_id="marketing",
            project_id=project.project_id,
            recommendation=f"Target {industry} market — TAM {tam/1e6:.0f}M TND, aim for 2% share",
            confidence_score=0.75,
            data=data,
        )
