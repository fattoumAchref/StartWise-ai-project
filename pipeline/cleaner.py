import pandas as pd
from scraping.schemas import CompanyBenchmark
from typing import List
import logging

logger = logging.getLogger(__name__)

class DataCleaner:

    NUMERIC_COLS = [
        "ev_revenue_multiple", "growth_rate_yoy",
        "ltv_cac_ratio", "churn_rate_monthly",
        "gross_margin", "cac_payback_months"
    ]
    KEY_FIELDS = [
        "arr", "growth_rate_yoy", "gross_margin",
        "ltv_cac_ratio", "churn_rate_monthly"
    ]

    def clean(self, raw: List[dict]) -> List[CompanyBenchmark]:
        df = pd.DataFrame(raw)
        if df.empty:
            return []

        df = df.drop_duplicates(subset=["company_name", "year"])

        for col in self.NUMERIC_COLS:
            if col in df.columns:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                df = df[
                    df[col].isna() |
                    ((df[col] >= Q1 - 3*IQR) &
                     (df[col] <= Q3 + 3*IQR))
                ]

        def score(row):
            filled = sum(1 for f in self.KEY_FIELDS if pd.notna(row.get(f)))
            return round(filled / len(self.KEY_FIELDS), 2)

        df["confidence_score"] = df.apply(score, axis=1)
        df = df[df["confidence_score"] >= 0.4]

        results = []
        for row in df.to_dict("records"):
            try:
                results.append(CompanyBenchmark(**row))
            except Exception as e:
                logger.warning(f"Skipped: {e}")
        return results