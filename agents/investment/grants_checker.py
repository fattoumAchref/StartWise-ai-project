"""
Grants Checker - Enhanced with Real INSME/Startup Act Data
Checks eligibility for Tunisian startup grants and incentives
"""

from typing import Dict, List
from agents.investment.benchmark_engine import BenchmarkEngine


class GrantsChecker:
    """
    Checks eligibility for Tunisian grants:
    - Startup Act Label
    - BTS Innovation Grant
    - ANPR grants
    - Other INSME incentives
    """
    
    def __init__(self, use_real_data: bool = True):
        self.benchmark = BenchmarkEngine(use_real_data=use_real_data)
    
    def check_eligibility(self, data: dict) -> dict:
        """
        Check eligibility for all available grants
        
        Args:
            data: Startup data with keys:
                - sector/industry
                - company_age/company_age_years
                - has_export/export_pct
                - tech_based/innovative
                - startup_act_label
        
        Returns:
            {
                "eligible": bool,
                "grants": List[dict],
                "total_potential": float
            }
        """
        # Normalize data format
        normalized_data = self._normalize_data(data)
        
        # Get eligible grants from real data
        eligible_grants = self.benchmark.get_available_grants(normalized_data)
        
        # If no real data, use fallback logic
        if not eligible_grants:
            eligible_grants = self._fallback_check(normalized_data)
        
        total_amount = sum(grant.get("amount", 0) for grant in eligible_grants)
        
        return {
            "eligible": len(eligible_grants) > 0,
            "grants": eligible_grants,
            "total_potential": total_amount
        }
    
    def _normalize_data(self, data: dict) -> dict:
        """Normalize different data formats"""
        return {
            "sector": data.get("industry") or data.get("sector"),
            "company_age": data.get("company_age_years") or data.get("company_age", 0),
            "has_export": data.get("export_pct", 0) > 0 or data.get("has_export", False),
            "tech_based": data.get("industry") in ["tech", "fintech", "healthtech", "edtech", "saas"] or data.get("tech_based", False),
            "innovative": data.get("innovative", True),
            "startup_act_label": data.get("startup_act_label", False),
            "rd_investment": data.get("rd_investment", False)
        }
    
    def _fallback_check(self, data: dict) -> List[Dict]:
        """Fallback grant checking logic when no real data available"""
        grants = []
        
        # Startup Act Label
        if data.get("company_age", 999) <= 8 and data.get("tech_based"):
            grants.append({
                "name": "Startup Act Label",
                "amount": 100000,
                "currency": "TND",
                "requirements": ["Label Startup Act", "< 8 years", "Tech-based"]
            })
        
        # BTS Innovation Grant
        if (data.get("sector") in ["tech", "fintech", "healthtech"] and 
            data.get("has_export") and 
            data.get("rd_investment")):
            grants.append({
                "name": "BTS Innovation Grant",
                "amount": 200000,
                "currency": "TND",
                "requirements": ["Tech sector", "Export activity", "R&D investment"]
            })
        
        return grants
    
    def get_grant_details(self, grant_name: str) -> Dict:
        """Get detailed information about a specific grant"""
        # This would query the real data source
        # For now, return basic info
        grant_info = {
            "Startup Act Label": {
                "description": "Label for innovative tech startups in Tunisia",
                "amount": 100000,
                "application_url": "https://startup.gov.tn",
                "requirements": [
                    "Company age < 8 years",
                    "Tech-based or innovative",
                    "Registered in Tunisia"
                ]
            },
            "BTS Innovation Grant": {
                "description": "Grant for R&D and export-oriented startups",
                "amount": 200000,
                "application_url": "https://www.bts.com.tn",
                "requirements": [
                    "Tech/Fintech/Healthtech sector",
                    "Export activity",
                    "R&D investment"
                ]
            }
        }
        
        return grant_info.get(grant_name, {})