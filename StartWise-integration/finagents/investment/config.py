"""
Configuration Investment Agent MVP.
"""

# Agent ID
AGENT_ID = "investment"

# LLM (TokenFactory)
TOKENFACTORY_API_KEY = "sk-3af10c5256a547299d9402856f312f8f"
BASE_URL = "https://tokenfactory.esprit.tn/api"
MODEL_NAME = "hosted_vllm/Llama-3.1-70B-Instruct"

# Valuation parameters — all sectors from enriched dataset
INDUSTRY_MULTIPLES = {
    "saas":        8.0,
    "fintech":     6.0,
    "tech":        6.0,
    "healthtech":  5.0,
    "marketplace": 5.0,
    "edtech":      4.0,
    "cleantech":   4.0,
    "agritech":    3.5,
    "logistics":   3.5,
    "ecommerce":   2.5,
    "food":        2.5,
    "travel":      3.0,
    "artisanat":   3.0,
    "retail":      2.0,
    "other":       4.0,
    "default":     4.0,
}

# DCF parameters
DISCOUNT_RATE = 0.25
TERMINAL_GROWTH_RATE = 0.03

# Stage thresholds (annual revenue in TND)
STAGE_THRESHOLDS = {
    "idea":       0,
    "pre-seed":   50_000,
    "seed":       200_000,
    "early":      500_000,
    "growth":     2_000_000,
    "scale":      float("inf"),
}

# Grants (Tunisia) — fallback if real data unavailable
GRANTS_DATABASE = {
    "startup_act": {
        "amount": 100_000,
        "requirements": {
            "startup_act_label": True,
            "company_age_max": 8
        }
    },
    "bts": {
        "amount": 200_000,
        "requirements": {
            "sector": ["tech", "fintech", "healthtech", "saas", "edtech"],
            "has_export": True
        }
    },
    "anpr": {
        "amount": 150_000,
        "requirements": {
            "sector": ["tech", "saas", "fintech", "cleantech", "agritech"],
            "innovative": True
        }
    }
}

# Scenario factors
SCENARIO_FACTORS = {
    "conservative": 0.8,
    "optimal":      1.0,
    "aggressive":   1.2,
}

# Equity/debt split by stage
EQUITY_DEBT_SPLIT = {
    "idea":     (1.00, 0.00),
    "pre-seed": (1.00, 0.00),
    "seed":     (0.90, 0.10),
    "early":    (0.80, 0.20),
    "growth":   (0.70, 0.30),
    "scale":    (0.60, 0.40),
}