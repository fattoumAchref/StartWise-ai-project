"""
Scraper DGI + CNSS — sources officielles tunisiennes.
Utilise crawl4ai pour un scraping plus robuste.
"""

import re
import asyncio
import random
import urllib3
import structlog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("dgi_cnss")

# Sources essentielles + PUISSANCE AUGMENTÉE
SOURCES = [
    # Ministère des Finances - PLUS DE PAGES
    {"url": "https://www.finances.gov.tn/fr", "label": "Ministère des Finances Tunisie — Accueil FR"},
    {"url": "https://www.finances.gov.tn/fr/apercu-general-sur-la-fiscalite", "label": "Fiscalité — Ministère des Finances Tunisie"},
    {"url": "https://www.finances.gov.tn/fr/impots-et-taxes", "label": "Impôts et Taxes — Ministère des Finances"},
    {"url": "https://www.finances.gov.tn/fr/budget-de-letat", "label": "Budget de l'État — Ministère des Finances"},
    {"url": "https://jibaya.tn/documentation/", "label": "Documentation Fiscale — Jibaya"},
    {"url": "https://jibaya.tn/", "label": "Jibaya — Portail Fiscal Tunisien"},
    # CNSS - PLUS DE PAGES
    {"url": "https://www.cnss.tn/fr", "label": "CNSS Tunisie — Accueil FR"},
    {"url": "https://www.cnss.tn/web/employeur/employeurs", "label": "CNSS Tunisie — Employeurs"},
    {"url": "https://www.cnss.tn/web/guest", "label": "CNSS Tunisie — Portail"},
    {"url": "https://www.cnss.tn/web/guest/telecharger/-/document_library_display/9MhK/view/20609", "label": "CNSS Tunisie — Textes législatifs"},
    {"url": "https://www.cnss.tn/web/guest/telecharger/-/document_library_display/9MhK/view/2369916", "label": "CNSS Tunisie — Assistance Télédeclaration"},
    # DGI - NOUVELLES SOURCES
    {"url": "https://www.impots.finances.gov.tn/", "label": "DGI — Direction Générale des Impôts"},
    {"url": "https://www.douane.gov.tn/", "label": "Douane Tunisienne"},
]


def _make_crawler_config():
    """Configuration crawl4ai pour sites gouvernementaux tunisiens."""
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


async def scrape_all() -> list[dict]:
    """Lance le scraping DGI/CNSS avec crawl4ai - PUISSANCE MAXIMALE."""
    from crawl4ai import AsyncWebCrawler
    from bs4 import BeautifulSoup
    
    chunks = []
    browser_cfg, run_cfg = _make_crawler_config()

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        for i, source in enumerate(SOURCES):
            try:
                await asyncio.sleep(random.uniform(2.0, 3.5))
                log.info("fetching_powerful", url=source["url"], page=i+1, total=len(SOURCES))
                
                result = await crawler.arun(source["url"], config=run_cfg)
                
                if not result.success:
                    log.warning("crawl_failed", url=source["url"], error=result.error_message)
                    continue

                content = result.markdown.raw_markdown if result.markdown else ""
                if not content:
                    content = result.cleaned_html or ""

                if len(content) < 150:
                    log.warning("empty_content", url=source["url"])
                    continue

                chunks.append({
                    "source": source["url"],
                    "source_label": source["label"],
                    "content": content[:6000],  # Plus de contenu
                    "metadata": {
                        "domain": "FISCAL",
                        "source_type": "DGI_CNSS",
                        "url": source["url"],
                    },
                })
                
                log.info("page_powerful_ok", label=source["label"], chars=len(content))

                # Exploration des liens pertinents (PUISSANCE AUGMENTÉE)
                html = result.html or ""
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    
                    # Mots-clés étendus
                    keywords = (
                        "fiscal", "impot", "tva", "cnss", "cotis", "declar", "budget", "finance", "loi",
                        "entreprise", "societe", "startup", "investissement", "creation", "immatriculation"
                    )
                    
                    links = []
                    for a in soup.select("a[href]"):
                        href = (a.get("href") or "").strip()
                        text = (a.get_text(" ", strip=True) or "").lower()
                        if not href:
                            continue
                        if href.startswith("/"):
                            root = source["url"].split("/", 3)
                            href = f"{root[0]}//{root[2]}{href}"
                        if not href.startswith("http"):
                            continue
                        haystack = f"{href.lower()} {text}"
                        if any(k in haystack for k in keywords):
                            links.append(href)
                        if len(links) >= 15:  # Plus de liens
                            break
                    
                    # Scraper les liens trouvés
                    for link_url in links[:10]:  # Limité à 10 pour éviter la surcharge
                        try:
                            await asyncio.sleep(random.uniform(1.5, 2.5))
                            link_result = await crawler.arun(link_url, config=run_cfg)
                            
                            if link_result.success:
                                link_content = link_result.markdown.raw_markdown if link_result.markdown else ""
                                if not link_content:
                                    link_content = link_result.cleaned_html or ""
                                
                                if len(link_content) > 200:
                                    chunks.append({
                                        "source": link_url,
                                        "source_label": f"Lien connexe — {source['label']}",
                                        "content": link_content[:5000],
                                        "metadata": {
                                            "domain": "FISCAL",
                                            "source_type": "DGI_CNSS_LINK",
                                            "url": link_url,
                                        },
                                    })
                                    log.info("link_powerful_ok", chars=len(link_content))
                        except Exception as e:
                            log.warning("link_error", url=link_url, error=str(e)[:80])

            except Exception as e:
                log.warning("fetch_error_powerful", url=source["url"], error=str(e)[:100])

    log.info("dgi_cnss_done_powerful", total=len(chunks))
    return chunks


def get_all_data() -> dict:
    return {}


def calculate_employer_cost(gross_salary_tnd: float) -> dict:
    """Helper de compatibilité utilisé par l'API."""
    cnss_pat = 0.1657
    cnss_emp = 0.0918
    tfp = 0.01
    foprolos = 0.01
    gross = float(gross_salary_tnd or 0)

    return {
        "gross_salary_tnd": gross,
        "cnss_employee_tnd": round(gross * cnss_emp, 2),
        "cnss_employer_tnd": round(gross * cnss_pat, 2),
        "tfp_tnd": round(gross * tfp, 2),
        "foprolos_tnd": round(gross * foprolos, 2),
        "employer_total_tnd": round(gross * (1 + cnss_pat + tfp + foprolos), 2),
    }
