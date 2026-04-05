import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)
#akhbar essouk
@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    url: str
    published: Optional[datetime]
    sector: str

class NewsScraper:

    FEEDS = {
        "saas":    "https://techcrunch.com/tag/saas/feed/",
        "fintech": "https://techcrunch.com/tag/fintech/feed/",
        "funding": "https://techcrunch.com/tag/funding/feed/",
    }

    def _parse_date(self, raw: str) -> Optional[datetime]:
        try:
            return parsedate_to_datetime(raw)
        except Exception:
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                logger.warning(f"Could not parse date: {raw!r}")
                return None

    def scrape(self, sector: str = "saas", limit: int = 10) -> List[NewsItem]:
        url = self.FEEDS.get(sector, self.FEEDS["funding"])
        feed = feedparser.parse(url)
        if feed.bozo:
            logger.warning(f"Feed parse error for sector '{sector}': {feed.bozo_exception}")
        results = []

        for entry in feed.entries[:limit]:
            item = NewsItem(
                title=entry.get("title", ""),
                summary=entry.get("summary", "")[:300],
                source="techcrunch",
                url=entry.get("link", ""),
                published=self._parse_date(entry.get("published", "")),
                sector=sector
            )
            results.append(item)

        return results

    def scrape_all_sectors(self) -> List[NewsItem]:
        all_news = []
        for sector in self.FEEDS.keys():
            all_news.extend(self.scrape(sector))
        return all_news