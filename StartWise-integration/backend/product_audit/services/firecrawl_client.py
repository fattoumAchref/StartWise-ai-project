from __future__ import annotations

import logging
import os

import httpx

from .schemas import AuditEvidence


logger = logging.getLogger(__name__)


class FirecrawlClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
        self.search_url = os.getenv("FIRECRAWL_SEARCH_URL", "https://api.firecrawl.dev/v2/search")
        self.scrape_url = os.getenv("FIRECRAWL_SCRAPE_URL", "https://api.firecrawl.dev/v1/scrape")

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, max_results: int = 5) -> list[AuditEvidence]:
        cleaned_query = (query or "").strip()
        if not cleaned_query or not self.api_key:
            return []

        payload: dict = {
            "query": cleaned_query,
            "limit": max(1, min(int(max_results or 5), 8)),
            "sources": ["web"],
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
            },
        }
        country = os.getenv("FIRECRAWL_COUNTRY", "").strip()
        if country:
            payload["country"] = country
        location = os.getenv("FIRECRAWL_LOCATION", "").strip()
        if location:
            payload["location"] = location

        try:
            with httpx.Client(
                timeout=httpx.Timeout(30.0),
                headers=self._headers(),
            ) as client:
                response = client.post(self.search_url, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Firecrawl search failed for %r: %s", cleaned_query, exc)
            return []

        web_results = (body.get("data") or {}).get("web") or []
        items: list[AuditEvidence] = []
        for index, raw in enumerate(web_results):
            if not isinstance(raw, dict):
                continue
            title = str(raw.get("title") or "").strip() or f"Web result {index + 1}"
            url = str(raw.get("url") or "").strip() or None
            description = str(raw.get("description") or "").strip()
            markdown = str(raw.get("markdown") or "").strip()
            content = description or _first_nonempty_line(markdown)
            if not content:
                continue
            items.append(
                AuditEvidence(
                    id=f"search-{index}",
                    title=title,
                    content=content,
                    source_type="firecrawl_search",
                    url=url,
                    metadata={"query": cleaned_query},
                )
            )
        return items

    def scrape(self, url: str) -> AuditEvidence | None:
        cleaned_url = (url or "").strip()
        if not cleaned_url or not self.api_key:
            return None

        payload = {
            "url": cleaned_url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(45.0),
                headers=self._headers(),
            ) as client:
                response = client.post(self.scrape_url, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            logger.warning("Firecrawl scrape failed for %r: %s", cleaned_url, exc)
            return None

        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            return None

        title = str(data.get("title") or cleaned_url).strip()
        markdown = str(data.get("markdown") or "").strip()
        if not markdown:
            return None
        return AuditEvidence(
            id="website-scrape",
            title=title,
            content=markdown,
            source_type="firecrawl_scrape",
            url=cleaned_url,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


def _first_nonempty_line(markdown: str) -> str:
    for line in markdown.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:300]
    return ""

