"""
Benchmark Engine - Enhanced with Tunisian Startup Data
Uses real data from Startup.gov.tn, Kaggle, and INSME
"""

from typing import Dict, Optional
from finagents.investment.data_sources import TunisianStartupData, BenchmarkEngine as DataBenchmark
from finagents.investment.config import INDUSTRY_MULTIPLES


class BenchmarkEngine:
    """
    Enhanced benchmark engine that combines:
    1. Real Tunisian startup data
    2. Configured industry multiples
    3. Stage-based heuristics
    """
    
    def __init__(self, use_real_data: bool = True):
        self.use_real_data = use_real_data
        
        if use_real_data:
            try:
                self.data_sources = TunisianStartupData(data_dir="data/")
                self.data_sources.load_all_sources()
                self.data_benchmark = DataBenchmark(self.data_sources)
                print("[Benchmark] Using real Tunisian startup data")
            except Exception as e:
                print(f"[Benchmark] Warning: Could not load data sources: {e}")
                print("[Benchmark] Falling back to configured multiples")
                self.use_real_data = False
    
    def get_valuation_benchmark(self, sector: str, stage: str, revenue: float) -> Dict:
        """
        Get valuation benchmark combining multiple sources
        """
        result = {
            "estimated_valuation": None,
            "confidence": "low",
            "data_source": "config",
            "revenue_multiple": None,
            "sample_size": 0,
            "startup_act_rate": None
        }

        # Try real data first
        if self.use_real_data:
            data_result = self.data_benchmark.get_valuation_benchmark(sector, stage, revenue)
            benchmarks = self.data_sources.get_sector_benchmarks(sector, stage)
            result["startup_act_rate"] = benchmarks.get("startup_act_rate")
            result["sample_size"] = benchmarks.get("sample_size", 0)

            if data_result["estimated_valuation"] and data_result["sample_size"] >= 3:
                result["estimated_valuation"] = data_result["estimated_valuation"]
                result["confidence"] = data_result["confidence"]
                result["data_source"] = "real_data"
                result["revenue_multiple"] = data_result["data_based_multiple"]
                return result

        # Fallback to configured multiples
        multiple = INDUSTRY_MULTIPLES.get(sector.lower(), INDUSTRY_MULTIPLES["default"])

        if revenue > 0:
            result["estimated_valuation"] = revenue * multiple
            result["revenue_multiple"] = multiple
            result["confidence"] = "medium"
            result["data_source"] = "config"

        return result
    
    def get_funding_benchmark(self, sector: str, stage: str) -> Dict:
        """
        Get typical funding amounts for sector and stage
        
        Returns:
            {
                "typical_amount": float,
                "range_min": float,
                "range_max": float,
                "typical_dilution": float,
                "sample_size": int
            }
        """
        # Try real data
        if self.use_real_data:
            data_result = self.data_benchmark.get_funding_recommendation(sector, stage)
            
            if data_result["typical_amount"] and data_result["sample_size"] >= 3:
                return data_result
        
        # Fallback to stage-based heuristics
        stage_defaults = {
            "pre-seed": {"amount": 200000, "dilution": 15},
            "seed": {"amount": 500000, "dilution": 20},
            "early": {"amount": 1500000, "dilution": 25},
            "growth": {"amount": 3000000, "dilution": 20},
            "scale": {"amount": 5000000, "dilution": 15}
        }
        
        defaults = stage_defaults.get(stage.lower(), stage_defaults["seed"])
        
        return {
            "typical_amount": defaults["amount"],
            "range_min": defaults["amount"] * 0.5,
            "range_max": defaults["amount"] * 2.0,
            "typical_dilution": defaults["dilution"],
            "sample_size": 0
        }
    
    def get_dilution_benchmark(self, sector: str, stage: str) -> Optional[float]:
        """Get typical dilution percentage for sector and stage"""
        funding_bench = self.get_funding_benchmark(sector, stage)
        return funding_bench.get("typical_dilution")
    
    def get_available_grants(self, startup_data: dict) -> list:
        """
        Get list of grants the startup is eligible for
        
        Args:
            startup_data: Dict with sector, company_age, has_export, etc.
        
        Returns:
            List of eligible grants with amounts
        """
        if self.use_real_data:
            return self.data_sources.check_grant_eligibility(startup_data)
        
        # Fallback to basic Startup Act check
        grants = []
        
        if startup_data.get("company_age", 999) <= 8 and startup_data.get("tech_based", False):
            grants.append({
                "name": "Startup Act Label",
                "amount": 100000,
                "currency": "TND"
            })
        
        return grants
    
    def get_stage_statistics(self, stage: str) -> Dict:
        """Get comprehensive statistics for a stage"""
        if self.use_real_data:
            return self.data_sources.get_stage_statistics(stage)
        
        # Return empty stats
        return {
            "avg_funding": None,
            "median_funding": None,
            "avg_valuation": None,
            "median_valuation": None,
            "avg_dilution": None,
            "typical_runway_months": None,
            "sample_size": 0
        }
