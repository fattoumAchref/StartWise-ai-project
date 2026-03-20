# Responsabilité:

#Recevoir les données du Meta-Orchestrator
#Valider la complétude
#Extraire les champs nécessaires

"""
Input handler - validates incoming data.
"""


class InputHandler:
    """Validates and extracts data from Finance and Marketing agents."""
    
    REQUIRED_FIELDS = [
        "projected_revenue",
        "monthly_burn_rate",
        "funding_needed"
    ]
    
    def validate_and_extract(self, finance_data: dict, marketing_data: dict) -> dict:
        """
        Validate inputs and extract relevant data.
        
        Returns:
            dict with extracted data or error
        """
        # Check required fields
        missing = [f for f in self.REQUIRED_FIELDS if f not in finance_data]
        
        if missing:
            return {
                "status": "error",
                "message": f"Missing required fields: {missing}"
            }
        
        # Extract data
        extracted = {
            "annual_revenue": finance_data.get("projected_revenue", 0),
            "growth_rate": finance_data.get("revenue_growth_rate", 0),
            "monthly_burn_rate": finance_data.get("monthly_burn_rate", 0),
            "funding_needed": finance_data.get("funding_needed", 0),
            "runway_months": finance_data.get("runway_months", 18),
            "implied_valuation": finance_data.get("implied_valuation", 0),
            
            # Marketing data
            "industry": marketing_data.get("industry", "tech"),
            "tam": marketing_data.get("total_addressable_market", 0),
            "team_score": marketing_data.get("team_score", 0.5),
            "product_score": marketing_data.get("product_score", 0.5),
            "market_score": marketing_data.get("market_score", 0.5),
        }
        
        return {
            "status": "success",
            "data": extracted
        }