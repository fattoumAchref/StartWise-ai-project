"""
Scraper JORT — Journal Officiel de la République Tunisienne.
Source : legislation.tn
Utilise crawl4ai pour un scraping plus robuste.

Stratégie critique : parsing hiérarchique Titre → Chapitre → Article
Le contexte parent est injecté dans chaque chunk pour le retrieval RAG.
"""

import re
import asyncio
import random
from datetime import datetime
from typing import Optional
import urllib3
from bs4 import BeautifulSoup
import structlog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("jort")

TEXT_TYPE_MAP = {
    "loi": "loi", "قانون": "loi",
    "décret-loi": "decret-loi", "مرسوم": "decret-loi",
    "décret": "decret", "arrêté": "arrete",
    "قرار": "arrete", "circulaire": "circulaire", "code": "code",
}


def _make_crawler_config():
    """Configuration crawl4ai pour legislation.tn."""
    from crawl4ai import BrowserConfig, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=False,
        ignore_https_errors=True,
        headers={
            "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        extra_args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )

    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=30000,
        delay_before_return_html=2.0,
        remove_overlay_elements=True,
        excluded_tags=["nav", "footer", "header", "script", "style", "aside"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.4, threshold_type="fixed"),
        ),
    )
    return browser, run_cfg


class JORTScraper:
    def __init__(self, base_url: str = "https://legislation-securite.tn"):
        self.base_url = base_url.rstrip("/")
        self._base_candidates = [
            self.base_url,
            "https://legislation-securite.tn",
            "https://legislation.tn",
        ]

    async def scrape_all(self) -> list[dict]:
        """Scraping complet du JORT avec crawl4ai - PUISSANCE MAXIMALE (50 textes)."""
        from crawl4ai import AsyncWebCrawler
        
        results, errors = [], []
        browser_cfg, run_cfg = _make_crawler_config()
        
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            refs = await self._list_texts(crawler, run_cfg)
            log.info("texts_found_powerful", count=len(refs))
            
            # PUISSANCE AUGMENTÉE : 50 textes au lieu de 15
            for ref in refs[:50]:
                try:
                    data = await self._scrape_one(crawler, run_cfg, ref)
                    if data:
                        results.append(data)
                except Exception as e:
                    errors.append(str(e))
                    log.warning("scrape_failed", url=ref.get("url"), error=str(e))
        
        log.info("done_powerful", total=len(results), errors=len(errors))
        return results

    async def scrape_since(self, since: datetime, crawler, run_cfg) -> list[dict]:
        results = []
        refs = await self._list_texts(crawler, run_cfg, since=since)
        for ref in refs[:10]:  # Limité
            try:
                data = await self._scrape_one(crawler, run_cfg, ref)
                if data:
                    results.append(data)
            except Exception:
                pass
        return results

    # ── Privé ─────────────────────────────────────────────────────

    async def _list_texts(
        self, crawler, run_cfg, since: Optional[datetime] = None
    ) -> list[dict]:
        refs = []
        html = None
        active_base = None

        for base in self._base_candidates:
            url = f"{base}/latest-laws/"
            try:
                result = await crawler.arun(url, config=run_cfg)
                if result.success:
                    html = result.html or ""
                    if html:
                        active_base = base
                        break
            except Exception:
                continue

        if not html:
            log.warning("jort_unreachable", base_candidates=self._base_candidates)
            return refs

        self.base_url = active_base or self.base_url

        # PUISSANCE AUGMENTÉE : Parse plusieurs pages
        for page in range(1, 4):  # Pages 1, 2, 3
            try:
                if page > 1:
                    page_url = f"{self.base_url}/latest-laws/page/{page}/"
                    result = await crawler.arun(page_url, config=run_cfg)
                    if not result.success:
                        break
                    html = result.html or ""
                
                soup = BeautifulSoup(html, "lxml")
                links = soup.select(
                    "a[href*='/latest-laws/'], "
                    "a[href*='/texte/'], a[href*='/loi/'], a[href*='/decret/'], "
                    "a[href*='/arrete/'], a[href*='/circulaire/']"  # Plus de types
                )
                
                page_refs = 0
                for a in links[:30]:  # Plus de liens par page
                    href = a.get("href", "")
                    if not href or href.rstrip("/").endswith("/latest-laws"):
                        continue
                    
                    pub_date = self._date_from_row(a)
                    if since and pub_date and pub_date < since:
                        break
                    
                    full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                    refs.append({
                        "url": full_url,
                        "pub_date": pub_date,
                    })
                    page_refs += 1

                log.info("jort_page_powerful", page=page, refs=page_refs)
                
                if page_refs == 0:
                    break
                    
            except Exception as e:
                log.warning("jort_page_error_powerful", page=page, error=str(e))
                break

        # Déduplication
        deduped = []
        seen = set()
        for ref in refs:
            u = ref.get("url", "")
            if u and u not in seen:
                seen.add(u)
                deduped.append(ref)
        
        log.info("jort_refs_powerful", total=len(deduped))
        return deduped

    async def _scrape_one(self, crawler, run_cfg, ref: dict) -> Optional[dict]:
        result = await crawler.arun(ref["url"], config=run_cfg)
        if not result.success:
            return None
        
        html = result.html or ""
        if not html:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        meta = self._extract_meta(soup)
        if not meta:
            return None
        articles = self._extract_articles(soup)
        return {**meta, "source_url": ref["url"], "articles": articles}

    def _extract_meta(self, soup: BeautifulSoup) -> Optional[dict]:
        h1 = soup.select_one("h1.text-title, .legislation-title h1, h1")
        title_fr = h1.get_text(strip=True) if h1 else None
        if not title_fr:
            og = soup.select_one("meta[property='og:title']")
            if og and og.get("content"):
                title_fr = og.get("content", "").strip()
        if not title_fr:
            title_tag = soup.select_one("title")
            if title_tag:
                raw_title = title_tag.get_text(" ", strip=True)
                # Nettoie les suffixes fréquents de template.
                title_fr = raw_title.split("|")[0].strip() if raw_title else None
        if not title_fr:
            return None
        title_ar_el = soup.select_one(".title-ar, h1[dir='rtl']")
        title_ar = title_ar_el.get_text(strip=True) if title_ar_el else None
        jort_number = self._extract_jort_number(soup.get_text())
        pub_date = self._extract_date(soup)
        text_type = next(
            (v for k, v in TEXT_TYPE_MAP.items() if k in title_fr.lower()), "loi"
        )
        status = self._detect_status(soup.get_text() + title_fr)
        return dict(
            jort_number=jort_number,
            publication_date=pub_date,
            text_type=text_type,
            title_fr=title_fr,
            title_ar=title_ar,
            status=status,
        )

    def _extract_articles(self, soup: BeautifulSoup) -> list[dict]:
        """
        Parcours séquentiel du DOM pour préserver la hiérarchie.
        Contexte parent injecté dans chaque article pour le RAG.
        """
        articles = []
        cur_titre = cur_chapitre = cur_section = ""
        zone = soup.select_one(".legislation-content, .text-content, #contenu") or soup

        for el in zone.find_all(["h2", "h3", "h4", "h5", "p", "div"]):
            txt = el.get_text(strip=True)
            if not txt:
                continue
            if re.match(r"^(Titre|TITRE|الباب)\s+[IVXLC\d]+", txt, re.I):
                cur_titre, cur_chapitre, cur_section = txt, "", ""
            elif re.match(r"^(Chapitre|CHAPITRE|الفصل)\s+[IVXLC\d]+", txt, re.I):
                cur_chapitre, cur_section = txt, ""
            elif re.match(r"^(Section|القسم)\s+[IVXLC\d]+", txt, re.I):
                cur_section = txt
            elif re.match(r"^(Article|Art\.?|المادة)\s+\d+", txt, re.I):
                m = re.search(r"(Article|Art\.?|المادة)\s+\d+\w*", txt, re.I)
                num = m.group(0) if m else txt[:30]
                parts = [p for p in [cur_titre, cur_chapitre, cur_section] if p]
                hierarchy = " > ".join(parts) + f" > {num}"
                content = self._next_text(el)
                articles.append(dict(
                    article_number=num,
                    hierarchy_path=hierarchy,
                    parent_title=" | ".join(parts),
                    content_fr=content,
                ))

        # Fallback WordPress/Elementor : pas d'"Article X", on indexe un bloc unique.
        if not articles:
            title = None
            og = soup.select_one("meta[property='og:title']")
            if og and og.get("content"):
                title = og.get("content", "").strip()

            # Supprime les zones de navigation avant extraction brute.
            for tag in soup.select("script, style, nav, header, footer, aside"):
                tag.decompose()

            full_text = soup.get_text("\n", strip=True)
            lines = [ln.strip() for ln in full_text.split("\n") if ln and len(ln.strip()) > 20]

            # Filtre les lignes de menu récurrentes pour garder le texte juridique.
            blacklist = (
                "libya", "tunisia", "palestine", "accueil", "menu",
                "politique de confidential", "rechercher", "a propos",
            )
            kept = [ln for ln in lines if not any(b in ln.lower() for b in blacklist)]
            content = "\n".join(kept)

            if len(content) > 300:
                articles.append(dict(
                    article_number="Texte intégral",
                    hierarchy_path=f"Publication > {title or 'Texte'}",
                    parent_title=title or "Publication",
                    content_fr=content,
                ))
        return articles

    def _next_text(self, el) -> str:
        """Collecte le texte des éléments suivants jusqu'au prochain titre."""
        parts = []
        node = el.next_sibling
        while node:
            if hasattr(node, "get_text"):
                t = node.get_text(strip=True)
                if t and re.match(r"^(Titre|Chapitre|Section|Article|Art\.|المادة|TITRE|CHAPITRE)", t, re.I):
                    break
                if t:
                    parts.append(t)
            node = node.next_sibling
        return "\n".join(parts) or el.get_text(strip=True)

    def _extract_jort_number(self, text: str) -> Optional[str]:
        m = re.search(r"JORT\s*[Nn]°?\s*\d+", text)
        return m.group(0) if m else None

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        el = soup.select_one(".pub-date, time[datetime]")
        if el:
            return el.get("datetime") or el.get_text(strip=True)
        m = re.search(
            r"(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|"
            r"septembre|octobre|novembre|décembre)\s+(\d{4})",
            soup.get_text(), re.I,
        )
        return m.group(0) if m else None

    def _detect_status(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["abrogé", "abrogée", "ملغى"]):
            return "ABROGE"
        if any(k in t for k in ["modifié", "معدل"]):
            return "MODIFIE"
        return "EN_VIGUEUR"

    def _date_from_row(self, link_el) -> Optional[datetime]:
        row = link_el.find_parent("tr")
        if not row:
            return None
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", row.get_text())
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        return None
