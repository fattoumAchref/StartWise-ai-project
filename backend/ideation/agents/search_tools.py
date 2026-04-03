from __future__ import annotations

import logging
import os

import httpx


logger = logging.getLogger(__name__)

FIRECRAWL_SEARCH_URL = "https://api.firecrawl.dev/v2/search"


def firecrawl_search(query: str, max_results: int = 5) -> str:
    """Search the web with Firecrawl and return concise results with links."""
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return "No search query provided."

    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        return "FIRECRAWL_API_KEY is not configured."

    try:
        limit = max(1, min(int(max_results or 5), 8))
    except (TypeError, ValueError):
        limit = 5

    payload = {
        "query": cleaned_query,
        "limit": limit,
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
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = client.post(FIRECRAWL_SEARCH_URL, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Firecrawl search failed for query %r: %s", cleaned_query, exc)
        return "Search unavailable right now."

    if body.get("success") is False:
        logger.warning("Firecrawl returned unsuccessful response for query %r", cleaned_query)
        return "Search unavailable right now."

    web_results = (body.get("data") or {}).get("web") or []
    results: list[str] = []
    for item in web_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        url = str(item.get("url") or "").strip()
        markdown = str(item.get("markdown") or "").strip()
        summary = description or _first_nonempty_line(markdown)
        if not title or not url:
            continue
        if summary:
            results.append(f"- {title}: {summary} ({url})")
        else:
            results.append(f"- {title}: {url}")
        if len(results) >= limit:
            break

    if not results:
        return "No search results found."
    return "\n".join(results)


def _first_nonempty_line(markdown: str) -> str:
    for line in markdown.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:240]
    return ""
