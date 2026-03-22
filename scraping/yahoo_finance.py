import asyncio
import yfinance as yf
from .schemas import CompanyBenchmark
from datetime import datetime
from typing import List
import logging

logger = logging.getLogger(__name__)

class YahooFinanceScraper:

    TICKERS = ["CRM", "SNOW", "DDOG", "MDB", "BILL", "ZM"]

    def get_multiples(self, ticker: str) -> dict:
        try:
            stock = yf.Ticker(ticker)
            info  = stock.info
            return {
                "ev_revenue_multiple": info.get("enterpriseToRevenue"),
                "gross_margin":        info.get("grossMargins"),
                "growth_rate_yoy":     info.get("revenueGrowth"),
            }
        except Exception as e:
            logger.error(f"Failed {ticker}: {e}")
            return {}

    async def scrape_all(self) -> List[CompanyBenchmark]:
        benchmarks = []
        for ticker in self.TICKERS:
            # get_multiples uses yfinance which is synchronous and blocking;
            # run it in a thread to avoid blocking the asyncio event loop
            data = await asyncio.to_thread(self.get_multiples, ticker)
            if not data:
                logger.warning(f"No data for {ticker}")
                continue
            try:
                b = CompanyBenchmark(
                    company_name=ticker,
                    sector="SaaS B2B",
                    stage="Public",
                    geography="US",
                    year=datetime.now().year,
                    ev_revenue_multiple=data.get("ev_revenue_multiple"),
                    gross_margin=data.get("gross_margin"),
                    growth_rate_yoy=data.get("growth_rate_yoy"),
                    source="yahoo_finance",
                    scraped_at=datetime.now(),
                )
                benchmarks.append(b)
                logger.info(f"OK {ticker}")
            except Exception as e:
                logger.error(f"Error {ticker}: {e}")
        return benchmarks
