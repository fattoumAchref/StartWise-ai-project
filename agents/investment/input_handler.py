"""
Input handler - validates incoming data and detects inconsistencies with LLM.
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME


class InputHandler:
    """Validates and extracts data from Finance and Marketing agents."""

    REQUIRED_FIELDS = [
        "projected_revenue",
        "monthly_burn_rate",
        "funding_needed"
    ]

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.1,
            max_tokens=300,
        )

    def validate_and_extract(self, finance_data: dict, marketing_data: dict) -> dict:
        """
        Validate inputs, extract relevant data, and flag inconsistencies.
        """
        missing = [f for f in self.REQUIRED_FIELDS if f not in finance_data]
        if missing:
            return {"status": "error", "message": f"Missing required fields: {missing}"}

        extracted = {
            "annual_revenue":   finance_data.get("projected_revenue", 0),
            "growth_rate":      finance_data.get("revenue_growth_rate", 0),
            "monthly_burn_rate":finance_data.get("monthly_burn_rate", 0),
            "funding_needed":   finance_data.get("funding_needed", 0),
            "runway_months":    finance_data.get("runway_months", 18),
            "implied_valuation":finance_data.get("implied_valuation", 0),
            "traction_score":   finance_data.get("traction_score", 0.5),
            "has_export":       finance_data.get("has_export", False),
            "company_age":      finance_data.get("company_age", 3),
            # Marketing
            "industry":         marketing_data.get("industry", "tech"),
            "tam":              marketing_data.get("total_addressable_market", 0),
            "team_score":       marketing_data.get("team_score", 0.5),
            "product_score":    marketing_data.get("product_score", 0.5),
            "market_score":     marketing_data.get("market_score", 0.5),
        }

        # LLM consistency check
        extracted["data_warnings"] = self._check_consistency(extracted)

        return {"status": "success", "data": extracted}

    def _check_consistency(self, data: dict) -> str:
        """Ask LLM to flag any suspicious or inconsistent data points."""
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "You are a startup financial analyst. Review these startup metrics and flag "
                 "any inconsistencies, suspicious values, or red flags in 1-2 short sentences. "
                 "If everything looks reasonable, reply with 'No issues detected.' "
                 "Be concise and specific. Currency is TND (Tunisian Dinar)."),
                ("user",
                 "Revenue: {revenue} TND/year | Growth: {growth}% | "
                 "Burn: {burn} TND/month | Funding needed: {funding} TND | "
                 "Runway: {runway} months | Sector: {sector} | "
                 "Team score: {team} | Market score: {market}")
            ])
            chain = prompt | self.llm
            response = chain.invoke({
                "revenue":  f"{data['annual_revenue']:,.0f}",
                "growth":   f"{data['growth_rate']*100:.0f}",
                "burn":     f"{data['monthly_burn_rate']:,.0f}",
                "funding":  f"{data['funding_needed']:,.0f}",
                "runway":   data["runway_months"],
                "sector":   data["industry"],
                "team":     data["team_score"],
                "market":   data["market_score"],
            })
            return response.content.strip()
        except Exception as e:
            return f"(consistency check unavailable: {e})"
