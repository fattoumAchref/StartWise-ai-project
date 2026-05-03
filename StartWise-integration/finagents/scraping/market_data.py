import httpx
import logging
from typing import List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)
#oomla 
@dataclass
class MarketData:
    metric: str
    value: float
    currency: str
    source: str
    fetched_at: datetime

class MarketDataScraper:
    """
    Taux de change via frankfurter.app (BCE) — gratuit, sans clé API.
    https://www.frankfurter.app
    """

    BASE = "https://api.frankfurter.app/latest"

    # Paires à récupérer : (from, to)
    PAIRS = [
        ("EUR", "USD"),
        ("EUR", "GBP"),
        ("EUR", "CHF"),
        ("EUR", "JPY"),
    ]

    async def get_all(self) -> List[MarketData]:
        # Récupère toutes les paires en une seule requête
        symbols = ",".join({to for _, to in self.PAIRS})
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(self.BASE, params={"from": "EUR", "symbols": symbols})
                r.raise_for_status()
                data = r.json()
                rates = data.get("rates", {})

            results = []
            for from_cur, to_cur in self.PAIRS:
                # frankfurter.app donne les taux depuis EUR
                raw = rates.get(to_cur)
                if raw is None:
                    logger.warning(f"No rate returned for {from_cur}/{to_cur}")
                    continue
                results.append(MarketData(
                    metric=f"{from_cur}/{to_cur}",
                    value=float(raw),
                    currency=to_cur,
                    source="frankfurter_ecb",
                    fetched_at=datetime.now(),
                ))

            logger.info(f"Fetched {len(results)}/{len(self.PAIRS)} currency rates")
            return results

        except Exception as e:
            logger.error(f"MarketDataScraper failed: {e}")
            return []