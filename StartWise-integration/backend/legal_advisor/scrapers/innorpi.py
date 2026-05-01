"""
Scraper INNORPI — marques tunisiennes.
Utilise crawl4ai (navigateur headless Chromium) pour contourner
le JavaScript Drupal et accéder au contenu réel des pages.
"""

import re
import asyncio
import random
from datetime import datetime
from typing import Optional
import urllib3
import structlog
from embeddings import PhoneticNormalizer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("innorpi")

BASE_URL = "https://www.innorpi.tn"

# Pages procédurales INNORPI — accessibles publiquement
PROCEDURAL_PAGES = [
    {"url": f"{BASE_URL}/fr/la-protection-des-marques-de-fabrique-de-commerce-et-de-services", "label": "INNORPI — Protection des marques"},
    {"url": f"{BASE_URL}/fr/la-propriete-industrielle", "label": "INNORPI — Propriété industrielle"},
    {"url": f"{BASE_URL}/fr/la-protection-par-brevet-dinvention", "label": "INNORPI — Brevets d'invention"},
    {"url": f"{BASE_URL}/fr/la-protection-des-dessins-et-modeles-industriels", "label": "INNORPI — Dessins et modèles industriels"},
    {"url": f"{BASE_URL}/fr/officiel-de-la-propriete-industrielle", "label": "INNORPI — Bulletin officiel propriété industrielle"},
    {"url": f"{BASE_URL}/fr/academie-nationale-de-la-propriete-intellectuelle", "label": "INNORPI — Académie propriété intellectuelle"},
    {"url": f"{BASE_URL}/fr/procedure-delaboration-dune-norme-tunisienne", "label": "INNORPI — Procédure normes tunisiennes"},
    {"url": BASE_URL, "label": "INNORPI — Portail officiel"},
]


def _make_crawler_config():
    """Crée la configuration crawl4ai adaptée aux sites gouvernementaux tunisiens."""
    from crawl4ai import BrowserConfig, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=False,
        ignore_https_errors=True,
        headers={
            "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        extra_args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )

    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",   # pas networkidle — les sites Drupal/Liferay ne se stabilisent pas
        page_timeout=30000,
        delay_before_return_html=2.0,    # laisse le JS s'exécuter
        remove_overlay_elements=True,
        excluded_tags=["nav", "footer", "header", "script", "style", "aside"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.4, threshold_type="fixed"),
        ),
    )
    return browser, run_cfg


class INNORPIScraper:
    def __init__(self):
        self.phonetizer = PhoneticNormalizer()

    async def scrape_all(self) -> list[dict]:
        """Scrape toutes les pages INNORPI avec crawl4ai."""
        from crawl4ai import AsyncWebCrawler

        results = []
        browser_cfg, run_cfg = _make_crawler_config()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            for page in PROCEDURAL_PAGES:
                try:
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                    result = await crawler.arun(page["url"], config=run_cfg)
                    if not result.success:
                        log.warning("crawl_failed", url=page["url"], error=result.error_message)
                        continue
                    content = result.markdown.raw_markdown if result.markdown else ""
                    if not content:
                        content = result.cleaned_html or ""
                    if len(content) < 100:
                        log.warning("empty_content", url=page["url"])
                        continue
                    results.append({
                        "name_exact": page["label"],
                        "name_phonetic": "",
                        "name_normalized": page["label"].lower(),
                        "holder_name": "INNORPI",
                        "nice_classes": [],
                        "filing_date": None,
                        "expiry_date": None,
                        "registration_number": "",
                        "status": "ACTIF",
                        "_procedural": True,
                        "_content": content[:6000],
                        "_source_label": page["label"],
                        "_url": page["url"],
                    })
                    log.info("procedural_page", label=page["label"], chars=len(content))
                except Exception as e:
                    log.warning("crawl_error", url=page["url"], error=str(e)[:100])

        # NOTE : La base de marques INNORPI (intranet.innorpi.tn) est inaccessible
        # publiquement — _scrape_classes() est désactivé car toutes les URLs retournent ✗.
        return self._deduplicate_results(results)

    async def search(self, name: str, nice_classes: list[int]) -> list[dict]:
        """Recherche en temps réel d'une marque par nom."""
        from crawl4ai import AsyncWebCrawler
        results = []
        browser_cfg, run_cfg = _make_crawler_config()

        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            results.extend(await self._search_by_name(crawler, run_cfg, name, nice_classes))
            for variant in self.phonetizer.generate_variants(name)[:2]:
                if variant != name:
                    results.extend(await self._search_by_name(crawler, run_cfg, variant, nice_classes))

        seen, unique = set(), []
        for r in results:
            key = r.get("registration_number") or r.get("name_exact")
            if key not in seen:
                seen.add(key)
                r["phonetic_similarity"] = self.phonetizer.similarity_score(name, r["name_exact"])
                unique.append(r)

        return sorted(unique, key=lambda x: x["phonetic_similarity"], reverse=True)

    # ── Privé ──────────────────────────────────────────────────────────────────

    async def _scrape_classes(self, crawler, run_cfg) -> list[dict]:
        from bs4 import BeautifulSoup
        results = []

        # PUISSANCE AUGMENTÉE : Plus de classes Nice et plus d'URLs
        for nice_class in range(1, 46):  # Toutes les classes Nice
            url_patterns = [
                f"{BASE_URL}/fr/marques/recherche?classe={nice_class}&page=1",
                f"{BASE_URL}/marques/recherche?classe={nice_class}&page=1",
                f"{BASE_URL}/fr/marques?classe={nice_class}",
                f"{BASE_URL}/fr/marques/recherche?classe={nice_class}&page=2",  # Page 2
                f"{BASE_URL}/fr/search?q=classe+{nice_class}",  # Recherche générale
            ]

            for url in url_patterns:
                try:
                    await asyncio.sleep(random.uniform(2.0, 3.0))  # Plus d'attente
                    result = await crawler.arun(url, config=run_cfg)
                    if not result.success:
                        continue
                    html = result.html or ""
                    if not html:
                        continue
                    soup = BeautifulSoup(html, "lxml")
                    batch = self._parse_list(soup, nice_class)
                    if not batch:
                        batch = self._parse_fallback(soup, nice_class)
                    if batch:
                        results.extend(batch)
                        log.info("class_done_powerful", nice_class=nice_class, count=len(batch), url=url)
                        break
                except Exception as e:
                    log.warning("class_error", nice_class=nice_class, url=url, error=str(e)[:80])
                    continue

            # Limite pour éviter la surcharge, mais plus généreuse
            if len(results) > 200:
                log.info("innorpi_limit_reached", total=len(results))
                break

        return results

    async def _search_by_name(self, crawler, run_cfg, name: str, nice_classes: list[int]) -> list[dict]:
        from bs4 import BeautifulSoup
        classes_param = ",".join(str(c) for c in nice_classes)
        url_patterns = [
            f"{BASE_URL}/fr/marques/recherche?nom={name}&classes={classes_param}",
            f"{BASE_URL}/marques/recherche?nom={name}&classes={classes_param}",
            f"{BASE_URL}/fr/marques?nom={name}",
        ]
        for url in url_patterns:
            try:
                result = await crawler.arun(url, config=run_cfg)
                if not result.success:
                    continue
                soup = BeautifulSoup(result.html or "", "lxml")
                batch = self._parse_list(soup)
                if batch:
                    return batch
            except Exception:
                continue
        return []

    def _parse_list(self, soup, default_class: Optional[int] = None) -> list[dict]:
        rows = soup.select(
            "table.trademarks-table tr, .trademark-row, "
            "table tr, .views-row, .result-row, .item-row"
        )
        return [r for row in rows if (r := self._parse_row(row, default_class))]

    def _parse_row(self, row, default_class: Optional[int] = None) -> Optional[dict]:
        cells = row.select("td")
        if len(cells) < 2:
            return None
        name_exact = cells[0].get_text(" ", strip=True)
        if not name_exact:
            return None
        holder = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        reg_num = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        filing = self._parse_date(cells[3].get_text(strip=True) if len(cells) > 3 else "")
        expiry = self._parse_date(cells[4].get_text(strip=True) if len(cells) > 4 else "")
        nice = self._parse_classes(cells[5].get_text(strip=True) if len(cells) > 5 else "")
        if not nice and default_class:
            nice = [default_class]
        status = "EXPIRE" if expiry and expiry < datetime.now().strftime("%Y-%m-%d") else "ACTIF"
        return dict(
            name_exact=name_exact,
            name_phonetic=self.phonetizer.encode(name_exact),
            name_normalized=self.phonetizer.normalize(name_exact),
            holder_name=holder,
            nice_classes=nice,
            filing_date=filing,
            expiry_date=expiry,
            registration_number=reg_num,
            status=status,
        )

    def _parse_fallback(self, soup, default_class: Optional[int] = None) -> list[dict]:
        text = soup.get_text("\n", strip=True)
        lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 2]
        candidates = []
        for i, ln in enumerate(lines):
            low = ln.lower()
            if any(k in low for k in ["marque", "classe", "enregistrement", "n°", "numero"]):
                name = lines[i - 1] if i > 0 else ln
                if len(name) < 3:
                    continue
                nice = self._parse_classes(ln)
                if not nice and default_class:
                    nice = [default_class]
                reg = ""
                m = re.search(r"(?:n°|num[eé]ro|enregistrement)\s*[:#-]?\s*([A-Za-z0-9\-/]+)", ln, re.I)
                if m:
                    reg = m.group(1)
                candidates.append(dict(
                    name_exact=name,
                    name_phonetic=self.phonetizer.encode(name),
                    name_normalized=self.phonetizer.normalize(name),
                    holder_name="",
                    nice_classes=nice,
                    filing_date=None,
                    expiry_date=None,
                    registration_number=reg,
                    status="ACTIF",
                ))
        deduped, seen = [], set()
        for c in candidates:
            key = (c.get("name_exact", "").lower(), c.get("registration_number", ""))
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped[:50]

    def _parse_date(self, text: str) -> Optional[str]:
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None

    def _parse_classes(self, text: str) -> list[int]:
        return sorted({int(n) for n in re.findall(r"\b([1-9]|[1-3][0-9]|4[0-5])\b", text)})

    def _deduplicate_results(self, rows: list[dict]) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}
        for row in rows:
            if row.get("_procedural"):
                key = ("proc", row.get("_url", ""))
                merged[key] = row
                continue
            name = (row.get("name_exact") or "").strip()
            reg = (row.get("registration_number") or "").strip()
            key = (reg.lower(), (row.get("name_normalized") or name).lower())
            if key not in merged:
                merged[key] = dict(row)
                merged[key]["nice_classes"] = list(row.get("nice_classes") or [])
                continue
            cur = merged[key]
            cur_classes = set(cur.get("nice_classes") or [])
            new_classes = set(row.get("nice_classes") or [])
            cur["nice_classes"] = sorted(cur_classes | new_classes)
            for field in ["holder_name", "filing_date", "expiry_date", "registration_number"]:
                if not cur.get(field) and row.get(field):
                    cur[field] = row.get(field)
            if cur.get("status") != "ACTIF" and row.get("status") == "ACTIF":
                cur["status"] = "ACTIF"
        deduped = list(merged.values())
        log.info("deduplicated", before=len(rows), after=len(deduped))
        return deduped
