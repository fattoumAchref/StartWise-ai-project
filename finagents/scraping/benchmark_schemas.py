from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

class CompanyBenchmark(BaseModel):
    company_name: str
    sector: str
    stage: str
    geography: str
    year: int
    arr: Optional[float] = None
    mrr: Optional[float] = None
    growth_rate_yoy: Optional[float] = None
    burn_rate: Optional[float] = None
    runway_months: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    cac_payback_months: Optional[float] = None
    net_revenue_retention: Optional[float] = None
    churn_rate_monthly: Optional[float] = None
    gross_margin: Optional[float] = None
    last_round_size: Optional[float] = None
    valuation: Optional[float] = None
    ev_revenue_multiple: Optional[float] = None
    source: str
    scraped_at: datetime = Field(default_factory=datetime.now)
    confidence_score: float = 0.0

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        allowed = ["Seed", "Series A", "Series B", "Series C", "Public"]
        if v not in allowed:
            raise ValueError(f"Stage must be one of {allowed}")
        return v

    @field_validator("gross_margin")
    @classmethod
    def validate_gross_margin(cls, v: Optional[float]) -> Optional[float]:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("gross_margin must be between 0.0 and 1.0")
        return v

    @field_validator("churn_rate_monthly")
    @classmethod
    def validate_churn(cls, v: Optional[float]) -> Optional[float]:
        import math
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if not (0.0 <= v <= 1.0):
            raise ValueError("churn_rate_monthly must be between 0.0 and 1.0")
        return v

    @field_validator("net_revenue_retention")
    @classmethod
    def validate_nrr(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("net_revenue_retention must be positive")
        return v