"""
Data Sources Integration - Tunisian Startup Data
Integrates external data for benchmarking and validation
"""

import json
import pandas as pd
from typing import Dict, List, Optional


class TunisianStartupData:
    """
    Manages external data sources for Investment Agent:
    - Startup.gov.tn database
    - Kaggle funding data
    - INSME/Startup Act incentives
    """
    
    def __init__(self, data_dir: str = "data/"):
        self.data_dir = data_dir
        self.startup_gov_data = None
        self.kaggle_data = None
        self.incentives_data = None
        self.enriched_data = None  # Real 930-record enriched dataset

    def load_all_sources(self):
        """Load all data sources"""
        self.load_startup_gov_data()
        self.load_kaggle_data()
        self.load_incentives_data()
        self.load_enriched_data()
    
    def load_startup_gov_data(self):
        """
        Load Startup.gov.tn database.
        If file not found, derives a minimal benchmark table from the enriched dataset.
        """
        try:
            self.startup_gov_data = pd.read_csv(f"{self.data_dir}startup_gov_tn.csv")
            print(f"[Data] Loaded {len(self.startup_gov_data)} records from Startup.gov.tn")
        except FileNotFoundError:
            print("[Data] startup_gov_tn.csv not found — deriving benchmarks from enriched data")
            self.startup_gov_data = None  # will fall through to enriched-based sample_size

    def load_kaggle_data(self):
        """
        Load Kaggle Tunisia funding data.
        Amounts are in USD — converted to TND at 1 USD = 3.1 TND.
        """
        USD_TO_TND = 3.1
        try:
            df = pd.read_csv(f"{self.data_dir}tunisia_funding_kaggle.csv")
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce") * USD_TO_TND
            df["industry"] = df["industry"].str.lower().str.strip()
            self.kaggle_data = df
            print(f"[Data] Loaded {len(self.kaggle_data)} records from Kaggle (converted to TND)")
        except FileNotFoundError:
            print("[Data] Warning: tunisia_funding_kaggle.csv not found, using defaults")
            self.kaggle_data = None
    
    def load_incentives_data(self):
        """
        Load INSME/Startup Act incentives
        Expected format: JSON with grant programs and eligibility
        """
        try:
            with open(f"{self.data_dir}startup_act_incentives.json", 'r', encoding='utf-8') as f:
                self.incentives_data = json.load(f)
            print(f"[Data] Loaded {len(self.incentives_data.get('programs', []))} grant programs")
        except FileNotFoundError:
            print("[Data] Warning: startup_act_incentives.json not found, using defaults")
            self.incentives_data = self._get_default_incentives()

    def load_enriched_data(self):
        """
        Load the real enriched Tunisian startup dataset (930 records).
        Columns: name, sector, confidence, has_startup_act_label, year_founded, label_date, website
        """
        try:
            self.enriched_data = pd.read_csv(
                f"{self.data_dir}tunisia_labeled_startups_enriched.csv",
                encoding="utf-8"
            )
            # Normalize sector column
            self.enriched_data["sector"] = self.enriched_data["sector"].str.lower().str.strip()
            print(f"[Data] Loaded {len(self.enriched_data)} records from enriched dataset")
        except FileNotFoundError:
            print("[Data] Warning: tunisia_labeled_startups_enriched.csv not found")
            self.enriched_data = None
    
    def _get_default_incentives(self) -> dict:
        """Default Startup Act incentives (fallback)"""
        return {
            "programs": [
                {
                    "name": "Startup Act Label",
                    "amount": 100000,
                    "currency": "TND",
                    "requirements": {
                        "company_age_max": 8,
                        "innovative": True,
                        "tech_based": True
                    }
                },
                {
                    "name": "BTS Innovation Grant",
                    "amount": 200000,
                    "currency": "TND",
                    "requirements": {
                        "sector": ["tech", "fintech", "healthtech"],
                        "has_export": True,
                        "rd_investment": True
                    }
                }
            ]
        }
    
    def get_sector_distribution(self) -> Dict:
        """
        Returns sector counts from the real enriched dataset.
        Useful for understanding market composition.
        """
        if self.enriched_data is None:
            return {}
        return self.enriched_data["sector"].value_counts().to_dict()

    def get_sector_startup_act_rate(self, sector: str) -> Optional[float]:
        """
        Returns the % of startups in a sector that have the Startup Act label.
        Useful as a proxy for sector maturity / fundability.
        """
        if self.enriched_data is None:
            return None
        df = self.enriched_data[self.enriched_data["sector"] == sector.lower()]
        if len(df) == 0:
            return None
        labeled = df["has_startup_act_label"].astype(str).str.lower().isin(["true", "1", "yes"])
        return round(labeled.sum() / len(df), 3)

    def get_sector_benchmarks(self, sector: str, stage: str) -> Dict:
        """
        Get benchmarks for a specific sector and stage
        Returns: avg_valuation, avg_funding, avg_dilution, sample_size, startup_act_rate
        """
        benchmarks = {
            "avg_valuation": None,
            "avg_funding": None,
            "avg_dilution": None,
            "sample_size": 0,
            "startup_act_rate": self.get_sector_startup_act_rate(sector)
        }

        # Try Startup.gov.tn data first
        if self.startup_gov_data is not None:
            filtered = self.startup_gov_data[
                (self.startup_gov_data['sector'].str.lower() == sector.lower()) &
                (self.startup_gov_data['stage'].str.lower() == stage.lower())
            ]

            if len(filtered) > 0:
                benchmarks["avg_valuation"] = filtered['valuation'].mean()
                benchmarks["avg_funding"] = filtered['funding_amount'].mean()
                benchmarks["avg_dilution"] = filtered['dilution_pct'].mean() if 'dilution_pct' in filtered.columns else None
                benchmarks["sample_size"] = len(filtered)

        # Fallback to Kaggle data
        if benchmarks["avg_valuation"] is None and self.kaggle_data is not None:
            filtered = self.kaggle_data[
                (self.kaggle_data['industry'].str.lower() == sector.lower())
            ]

            if len(filtered) > 0:
                benchmarks["avg_funding"] = filtered['amount'].mean()
                benchmarks["sample_size"] = len(filtered)

        # Supplement sample_size from enriched data if still 0
        if benchmarks["sample_size"] == 0 and self.enriched_data is not None:
            count = (self.enriched_data["sector"] == sector.lower()).sum()
            benchmarks["sample_size"] = int(count)

        return benchmarks
    
    def get_revenue_multiple(self, sector: str, stage: str) -> Optional[float]:
        """
        Calculate revenue multiple from historical data
        """
        if self.startup_gov_data is None:
            return None
        
        filtered = self.startup_gov_data[
            (self.startup_gov_data['sector'].str.lower() == sector.lower()) &
            (self.startup_gov_data['stage'].str.lower() == stage.lower()) &
            (self.startup_gov_data['revenue'] > 0)
        ]
        
        if len(filtered) > 0:
            # Calculate valuation/revenue ratio using .loc to avoid SettingWithCopyWarning
            multiples = filtered['valuation'].values / filtered['revenue'].values
            import numpy as np
            return float(np.median(multiples))
        
        return None
    
    def check_grant_eligibility(self, startup_data: dict) -> List[Dict]:
        """
        Check which grants the startup is eligible for
        
        Args:
            startup_data: Dict with keys like sector, company_age, has_export, etc.
        
        Returns:
            List of eligible grants with amounts
        """
        eligible_grants = []
        
        if self.incentives_data is None:
            return eligible_grants
        
        for program in self.incentives_data.get("programs", []):
            if self._check_requirements(startup_data, program["requirements"]):
                eligible_grants.append({
                    "name": program["name"],
                    "amount": program["amount"],
                    "currency": program.get("currency", "TND")
                })
        
        return eligible_grants
    
    def _check_requirements(self, startup_data: dict, requirements: dict) -> bool:
        """Check if startup meets grant requirements"""
        for key, value in requirements.items():
            if key == "company_age_max":
                if startup_data.get("company_age", 999) > value:
                    return False
            elif key == "sector":
                if isinstance(value, list):
                    if startup_data.get("sector") not in value:
                        return False
                else:
                    if startup_data.get("sector") != value:
                        return False
            elif key in startup_data:
                if startup_data[key] != value:
                    return False
        
        return True
    
    def get_stage_statistics(self, stage: str) -> Dict:
        """
        Get comprehensive statistics for a stage
        """
        stats = {
            "avg_funding": None,
            "median_funding": None,
            "avg_valuation": None,
            "median_valuation": None,
            "avg_dilution": None,
            "typical_runway_months": None,
            "sample_size": 0
        }
        
        if self.startup_gov_data is not None:
            filtered = self.startup_gov_data[
                self.startup_gov_data['stage'].str.lower() == stage.lower()
            ]
            
            if len(filtered) > 0:
                stats["avg_funding"] = filtered['funding_amount'].mean()
                stats["median_funding"] = filtered['funding_amount'].median()
                stats["avg_valuation"] = filtered['valuation'].mean()
                stats["median_valuation"] = filtered['valuation'].median()
                
                if 'dilution_pct' in filtered.columns:
                    stats["avg_dilution"] = filtered['dilution_pct'].mean()
                
                if 'runway_months' in filtered.columns:
                    stats["typical_runway_months"] = filtered['runway_months'].median()
                
                stats["sample_size"] = len(filtered)
        
        return stats


class BenchmarkEngine:
    """
    Enhanced benchmark engine using real Tunisian data
    """
    
    def __init__(self, data_sources: TunisianStartupData):
        self.data = data_sources
    
    def get_valuation_benchmark(self, sector: str, stage: str, revenue: float) -> Dict:
        """
        Get valuation benchmark using multiple data sources
        """
        # Get sector benchmarks
        benchmarks = self.data.get_sector_benchmarks(sector, stage)
        
        # Get revenue multiple from data
        data_multiple = self.data.get_revenue_multiple(sector, stage)
        
        # Calculate valuation
        valuation_estimates = []
        
        if benchmarks["avg_valuation"]:
            valuation_estimates.append(benchmarks["avg_valuation"])
        
        if data_multiple and revenue > 0:
            valuation_estimates.append(revenue * data_multiple)
        
        return {
            "estimated_valuation": sum(valuation_estimates) / len(valuation_estimates) if valuation_estimates else None,
            "data_based_multiple": data_multiple,
            "benchmark_valuation": benchmarks["avg_valuation"],
            "sample_size": benchmarks["sample_size"],
            "confidence": "high" if benchmarks["sample_size"] > 10 else "medium" if benchmarks["sample_size"] > 3 else "low"
        }
    
    def get_funding_recommendation(self, sector: str, stage: str) -> Dict:
        """
        Get funding amount recommendation based on historical data
        """
        benchmarks = self.data.get_sector_benchmarks(sector, stage)
        stage_stats = self.data.get_stage_statistics(stage)
        
        return {
            "typical_amount": benchmarks["avg_funding"] or stage_stats["median_funding"],
            "range_min": stage_stats["median_funding"] * 0.7 if stage_stats["median_funding"] else None,
            "range_max": stage_stats["median_funding"] * 1.3 if stage_stats["median_funding"] else None,
            "typical_dilution": benchmarks["avg_dilution"] or stage_stats["avg_dilution"],
            "sample_size": benchmarks["sample_size"]
        }
