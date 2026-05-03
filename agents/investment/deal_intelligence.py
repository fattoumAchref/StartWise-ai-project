"""
Deal Intelligence — High-impact decision quality features:

1. ComparableTransactions  — finds similar real deals from Kaggle data
2. InvestorMatcher         — maps stage + sector to real investors with check sizes
3. TermSheetGenerator      — LLM drafts a standard term sheet from the optimal scenario
"""

from __future__ import annotations

import pandas as pd
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME


# ─────────────────────────────────────────────────────────────────────────────
# 1. COMPARABLE TRANSACTIONS
# ─────────────────────────────────────────────────────────────────────────────

class ComparableTransactions:
    """
    Finds the 3 most similar real deals from the Kaggle Tunisia funding dataset.
    Similarity = same sector + closest funding amount.
    """

    USD_TO_TND = 3.1

    def __init__(self, data_dir: str = "data/"):
        self._df: Optional[pd.DataFrame] = None
        self._data_dir = data_dir

    def _load(self) -> pd.DataFrame:
        if self._df is not None:
            return self._df
        try:
            df = pd.read_csv(f"{self._data_dir}tunisia_funding_kaggle.csv")
            df["amount_tnd"] = pd.to_numeric(df["amount"], errors="coerce") * self.USD_TO_TND
            df["industry"]   = df["industry"].str.lower().str.strip()
            self._df = df
        except FileNotFoundError:
            self._df = pd.DataFrame()
        return self._df

    def find(self, sector: str, funding_amount: float, n: int = 3) -> list[dict]:
        """
        Return up to n comparable deals sorted by relevance.

        Args:
            sector         : startup sector (e.g. "fintech")
            funding_amount : target raise in TND
            n              : number of comparables to return

        Returns:
            List of dicts with company, round_type, amount_tnd, investors, date, similarity
        """
        df = self._load()
        if df.empty:
            return []

        # Filter by sector first, fallback to all if no match
        sector_df = df[df["industry"] == sector.lower()]
        pool = sector_df if len(sector_df) >= 1 else df

        # Score by proximity to funding amount (log scale to handle large ranges)
        import math
        def _score(row):
            amt = row.get("amount_tnd", 0) or 0
            if amt <= 0 or funding_amount <= 0:
                return 0
            ratio = min(amt, funding_amount) / max(amt, funding_amount)
            sector_bonus = 1.2 if row.get("industry") == sector.lower() else 1.0
            return ratio * sector_bonus

        pool = pool.copy()
        pool["_score"] = pool.apply(_score, axis=1)
        top = pool.nlargest(n, "_score")

        results = []
        for _, row in top.iterrows():
            results.append({
                "company":    row.get("company", "N/A"),
                "sector":     row.get("industry", "N/A"),
                "round_type": row.get("round_type", "N/A"),
                "amount_tnd": round(row.get("amount_tnd", 0)),
                "investors":  row.get("investors", "N/A"),
                "date":       row.get("date", "N/A"),
                "similarity": round(row["_score"] * 100),
            })
        return results


# ─────────────────────────────────────────────────────────────────────────────
# 2. INVESTOR MATCHER
# ─────────────────────────────────────────────────────────────────────────────

# Real investor database — Tunisia & North Africa ecosystem
INVESTOR_DATABASE = [
    # ── Accelerators / Pre-seed ──────────────────────────────────────────────
    {
        "name":        "Flat6Labs Tunis",
        "type":        "accelerator",
        "stages":      ["idea", "seed"],
        "sectors":     ["tech", "fintech", "edtech", "healthtech", "saas", "ecommerce", "marketplace"],
        "check_min":   50_000,
        "check_max":   200_000,
        "currency":    "TND",
        "website":     "flat6labs.com/tunis",
        "note":        "Equity-free grant + 3% equity. 4-month program.",
    },
    {
        "name":        "Smart Capital",
        "type":        "public_fund",
        "stages":      ["idea", "seed"],
        "sectors":     ["tech", "fintech", "healthtech", "cleantech", "agritech", "saas"],
        "check_min":   50_000,
        "check_max":   500_000,
        "currency":    "TND",
        "website":     "smartcapital.tn",
        "note":        "Government-backed. Convertible note or equity.",
    },
    # ── Seed / Early ─────────────────────────────────────────────────────────
    {
        "name":        "Algebra Ventures",
        "type":        "vc",
        "stages":      ["seed", "series_a"],
        "sectors":     ["tech", "fintech", "saas", "marketplace", "healthtech"],
        "check_min":   500_000,
        "check_max":   3_000_000,
        "currency":    "TND",
        "website":     "algebraventures.com",
        "note":        "Egypt-based, active in Tunisia. Focus on scalable tech.",
    },
    {
        "name":        "Wamda Capital",
        "type":        "vc",
        "stages":      ["seed", "series_a"],
        "sectors":     ["tech", "fintech", "ecommerce", "logistics", "marketplace"],
        "check_min":   300_000,
        "check_max":   2_000_000,
        "currency":    "TND",
        "website":     "wamda.com",
        "note":        "Pan-Arab VC. Strong network in MENA.",
    },
    {
        "name":        "BIAT Capital",
        "type":        "corporate_vc",
        "stages":      ["seed", "series_a"],
        "sectors":     ["fintech", "tech", "saas", "logistics"],
        "check_min":   200_000,
        "check_max":   1_500_000,
        "currency":    "TND",
        "website":     "biatcapital.com.tn",
        "note":        "Tunisian bank-backed VC. Prefers revenue-generating startups.",
    },
    # ── Growth / Series A ────────────────────────────────────────────────────
    {
        "name":        "AfricInvest",
        "type":        "pe_vc",
        "stages":      ["series_a", "growth"],
        "sectors":     ["fintech", "healthtech", "logistics", "tech", "agritech"],
        "check_min":   1_500_000,
        "check_max":   15_000_000,
        "currency":    "TND",
        "website":     "africinvest.com",
        "note":        "Largest PE/VC in Tunisia. Requires proven revenue.",
    },
    {
        "name":        "Partech Africa",
        "type":        "vc",
        "stages":      ["series_a", "growth"],
        "sectors":     ["fintech", "tech", "saas", "logistics", "healthtech"],
        "check_min":   3_000_000,
        "check_max":   30_000_000,
        "currency":    "TND",
        "website":     "partechpartners.com",
        "note":        "Pan-African VC. Backed Expensya (Tunisia). High bar.",
    },
    {
        "name":        "Sawari Ventures",
        "type":        "vc",
        "stages":      ["seed", "series_a"],
        "sectors":     ["tech", "fintech", "edtech", "saas"],
        "check_min":   500_000,
        "check_max":   5_000_000,
        "currency":    "TND",
        "website":     "sawariventures.com",
        "note":        "Egypt-based, MENA focus. Co-invested with Flat6Labs.",
    },
    {
        "name":        "Endeavor Catalyst",
        "type":        "vc",
        "stages":      ["series_a", "growth"],
        "sectors":     ["tech", "saas", "fintech", "marketplace"],
        "check_min":   3_000_000,
        "check_max":   20_000_000,
        "currency":    "TND",
        "website":     "endeavor.org",
        "note":        "Co-invests alongside lead VCs. Requires Endeavor selection.",
    },
    # ── Sector-specific ──────────────────────────────────────────────────────
    {
        "name":        "GreenTech Capital",
        "type":        "impact_vc",
        "stages":      ["seed", "series_a"],
        "sectors":     ["cleantech", "agritech"],
        "check_min":   200_000,
        "check_max":   2_000_000,
        "currency":    "TND",
        "website":     "N/A",
        "note":        "Impact-focused. Requires measurable environmental KPIs.",
    },
    {
        "name":        "Enda Tamweel",
        "type":        "microfinance",
        "stages":      ["idea", "seed"],
        "sectors":     ["artisanat", "food", "retail", "agritech"],
        "check_min":   10_000,
        "check_max":   100_000,
        "currency":    "TND",
        "website":     "enda.com.tn",
        "note":        "Microfinance for informal/traditional sectors. Low dilution.",
    },
]


class InvestorMatcher:
    """
    Matches a startup to the most relevant investors based on stage, sector,
    and funding amount. Returns ranked list with fit score.
    """

    def match(
        self,
        sector: str,
        stage: str,
        funding_amount: float,
        top_n: int = 5,
    ) -> list[dict]:
        """
        Args:
            sector         : startup sector
            stage          : startup stage (idea/seed/series_a/growth)
            funding_amount : target raise in TND
            top_n          : number of investors to return

        Returns:
            List of investor dicts with fit_score
        """
        scored = []
        for inv in INVESTOR_DATABASE:
            score = 0

            # Stage match
            if stage in inv["stages"]:
                score += 40
            elif any(abs(INVESTOR_DATABASE.index(inv) - i) <= 1
                     for i, s in enumerate(inv["stages"]) if s == stage):
                score += 15  # adjacent stage

            # Sector match
            if sector.lower() in [s.lower() for s in inv["sectors"]]:
                score += 35

            # Check size match
            if inv["check_min"] <= funding_amount <= inv["check_max"]:
                score += 25
            elif funding_amount < inv["check_min"]:
                gap = (inv["check_min"] - funding_amount) / inv["check_min"]
                score += max(0, 15 - int(gap * 30))
            else:
                gap = (funding_amount - inv["check_max"]) / inv["check_max"]
                score += max(0, 10 - int(gap * 20))

            if score > 0:
                scored.append({**inv, "fit_score": score})

        scored.sort(key=lambda x: x["fit_score"], reverse=True)
        return scored[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# 3. TERM SHEET GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

class TermSheetGenerator:
    """
    Generates a draft term sheet from the optimal funding scenario using LLM.
    Covers standard VC clauses adapted to Tunisian law.
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.2,
            max_tokens=800,
        )

    def generate(
        self,
        sector: str,
        stage: str,
        pre_money: float,
        equity: float,
        post_money: float,
        investor_pct: float,
        founder_after_pct: float,
        raise_amount: float,
        investors: list[dict] = None,
    ) -> str:
        """
        Generate a draft term sheet.

        Args:
            sector           : startup sector
            stage            : startup stage
            pre_money        : pre-money valuation (TND)
            equity           : equity raised (TND)
            post_money       : post-money valuation (TND)
            investor_pct     : investor ownership % after round
            founder_after_pct: founder ownership % after round
            raise_amount     : total raise (TND)
            investors        : matched investors list (optional)

        Returns:
            Draft term sheet as string
        """
        top_investor = investors[0]["name"] if investors else "Investisseur Lead"

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "Tu es un avocat spécialisé en droit des startups tunisiennes et en venture capital. "
                 "Génère un term sheet de financement professionnel et concis. "
                 "Utilise les clauses standards du marché tunisien/MENA. "
                 "Format : sections claires avec les termes clés. Devise : TND. "
                 "Inclus : valorisation, structure du tour, droits des investisseurs, "
                 "gouvernance, anti-dilution, liquidation preference, drag-along, tag-along. "
                 "Sois précis et actionnable. Maximum 600 mots."),
                ("user",
                 "Startup : secteur {sector}, stade {stage}\n"
                 "Valorisation pre-money : {pre_money} TND\n"
                 "Montant levé : {raise_amount} TND (equity uniquement)\n"
                 "Valorisation post-money : {post_money} TND\n"
                 "Part investisseur : {investor_pct}%\n"
                 "Part fondateurs post-tour : {founder_pct}%\n"
                 "Investisseur lead : {investor}")
            ])
            chain = prompt | self.llm
            r = chain.invoke({
                "sector":       sector,
                "stage":        stage,
                "pre_money":    f"{pre_money:,.0f}",
                "raise_amount": f"{raise_amount:,.0f}",
                "post_money":   f"{post_money:,.0f}",
                "investor_pct": f"{investor_pct:.1f}",
                "founder_pct":  f"{founder_after_pct:.1f}",
                "investor":     top_investor,
            })
            return r.content.strip()
        except Exception as e:
            return f"(term sheet unavailable: {e})"
