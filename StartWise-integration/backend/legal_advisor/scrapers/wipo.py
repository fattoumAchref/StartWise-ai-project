"""
Scraper WIPO + Sources Tunisiennes — marques et entreprises CONSOLIDÉ.
Un seul scraper pour toutes les sources de marques et entreprises.
"""

import re
import asyncio
import random
from typing import Optional
import urllib3
import structlog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("wipo_consolidated")

# Sources consolidées - WIPO + Sources tunisiennes
WIPO_URLS = [
    "https://branddb.wipo.int/fr/quicksearch?q=TN&rows=50",
    "https://branddb.wipo.int/en/quicksearch?q=Tunisia&rows=50", 
    "https://branddb.wipo.int/fr/IPO-TN/",
    "https://branddb.wipo.int/en/IPO-TN/",
]

F6S_URLS = [
    "https://www.f6s.com/discover/companies?country=tunisia",
    "https://www.f6s.com/tunisia",
    "https://www.f6s.com/search?q=tunisia",
]

TUNISIAN_SOURCES = [
    {"url": "https://startup.gov.tn/fr/database", "label": "STARTUP.GOV.TN — Base officielle startups labellisées", "domain": "ENTREPRISES"},
    {"url": "https://www.innorpi.tn/fr/la-protection-des-marques-de-fabrique-de-commerce-et-de-services", "label": "INNORPI — Protection des marques", "domain": "MARQUES"},
    {"url": "https://www.registre-entreprises.tn", "label": "RNE — Registre National des Entreprises", "domain": "ENTREPRISES"},
    {"url": "https://www.bct.gov.tn/bct/siteprod/page.jsp?id=68", "label": "BCT — Financement startups", "domain": "ENTREPRISES"},
    {"url": "https://www.bct.gov.tn/", "label": "BCT — Banque Centrale de Tunisie", "domain": "ENTREPRISES"},
    {"url": "https://legislation-securite.tn/?s=marque", "label": "JORT — Législation marques", "domain": "MARQUES"},
    {"url": "https://legislation-securite.tn/?s=propriete+intellectuelle", "label": "JORT — Propriété intellectuelle", "domain": "MARQUES"},
    {"url": "https://www.ccitunis.org.tn/", "label": "CCIT — Chambre Commerce Tunis", "domain": "ENTREPRISES"},
    {"url": "https://www.conect.org.tn/", "label": "CONECT — Confédération Entreprises Citoyennes", "domain": "ENTREPRISES"},
    {"url": "https://www.wikistartup.tn/", "label": "WikiStartup — Écosystème startup Tunisie", "domain": "ENTREPRISES"},
]


def _make_stealth_config():
    """Configuration crawl4ai furtive pour contourner les protections anti-bot."""
    from crawl4ai import BrowserConfig, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=False,
        ignore_https_errors=True,
        use_managed_browser=True,
        headers={
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
        ],
    )

    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=30000,
        delay_before_return_html=3.0,
        magic=True,
        simulate_user=True,
        override_navigator=True,
        remove_overlay_elements=True,
        excluded_tags=["nav", "footer", "header", "script", "style", "aside"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.3, threshold_type="fixed"),
        ),
    )
    return browser, run_cfg


async def scrape_all() -> list[dict]:
    """Scrape TOUTES les sources - WIPO, F6S et sources tunisiennes."""
    from crawl4ai import AsyncWebCrawler
    from bs4 import BeautifulSoup

    chunks = []
    browser_cfg, run_cfg = _make_stealth_config()

    # Toutes les URLs à scraper
    all_urls = []
    
    # WIPO URLs
    for url in WIPO_URLS:
        all_urls.append({"url": url, "type": "WIPO", "domain": "MARQUES"})
    
    # F6S URLs  
    for url in F6S_URLS:
        all_urls.append({"url": url, "type": "F6S", "domain": "ENTREPRISES"})
    
    # Sources tunisiennes
    for source in TUNISIAN_SOURCES:
        all_urls.append({"url": source["url"], "type": "TUNISIAN", "domain": source["domain"], "label": source["label"]})

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        # Warm-up pour établir les sessions
        try:
            log.info("warmup_sessions")
            await crawler.arun("https://branddb.wipo.int", config=run_cfg)
            await asyncio.sleep(2)
            await crawler.arun("https://www.f6s.com", config=run_cfg)
            await asyncio.sleep(2)
        except Exception as e:
            log.warning("warmup_failed", error=str(e)[:100])

        for i, item in enumerate(all_urls):
            try:
                await asyncio.sleep(random.uniform(2.0, 4.0))
                log.info("fetching_consolidated", url=item["url"], page=i+1, total=len(all_urls), type=item["type"])
                
                result = await crawler.arun(item["url"], config=run_cfg)
                
                if not result.success:
                    log.warning("crawl_failed", url=item["url"], error=result.error_message)
                    continue

                content = result.markdown.raw_markdown if result.markdown else ""
                if not content:
                    content = result.cleaned_html or ""

                if _is_blocked(content):
                    log.warning("blocked", url=item["url"])
                    continue

                if len(content) < 200:
                    log.warning("minimal_content", url=item["url"], chars=len(content))
                    continue

                # Déterminer le label
                if item["type"] == "TUNISIAN":
                    label = item["label"]
                else:
                    label = f"{item['type']} — {'Marques' if item['domain'] == 'MARQUES' else 'Entreprises'} tunisiennes"

                # Chunk principal
                chunks.append({
                    "source": item["url"],
                    "source_label": label,
                    "content": content[:8000],
                    "metadata": {
                        "domain": item["domain"],
                        "source_type": item["type"],
                        "url": item["url"],
                    },
                })

                # Extraction d'éléments spécifiques pour WIPO, F6S et STARTUP.GOV.TN
                if item["type"] in ["WIPO", "F6S"] and result.html:
                    soup = BeautifulSoup(result.html, "lxml")
                    
                    if item["type"] == "WIPO":
                        items = _extract_wipo_trademarks(soup)
                        for trademark in items:
                            chunks.append({
                                "source": item["url"],
                                "source_label": f"WIPO — Marque {trademark.get('name', 'tunisienne')}",
                                "content": _format_trademark_content(trademark),
                                "metadata": {
                                    "domain": "MARQUES",
                                    "source_type": "WIPO",
                                    "url": item["url"],
                                    "trademark_name": trademark.get('name', ''),
                                },
                            })
                    
                    elif item["type"] == "F6S":
                        items = _extract_f6s_companies(soup)
                        for company in items:
                            chunks.append({
                                "source": item["url"],
                                "source_label": f"F6S — Entreprise {company.get('name', 'tunisienne')}",
                                "content": _format_company_content(company),
                                "metadata": {
                                    "domain": "ENTREPRISES",
                                    "source_type": "F6S",
                                    "url": item["url"],
                                    "company_name": company.get('name', ''),
                                },
                            })

                # Extraction spéciale pour startup.gov.tn
                if item["type"] == "TUNISIAN" and "startup.gov.tn" in item["url"] and result.html:
                    soup = BeautifulSoup(result.html, "lxml")
                    startups = _extract_startup_gov_companies(soup)
                    for startup in startups:
                        chunks.append({
                            "source": item["url"],
                            "source_label": f"STARTUP.GOV.TN — {startup.get('name', 'Startup labellisée')}",
                            "content": _format_startup_gov_content(startup),
                            "metadata": {
                                "domain": "ENTREPRISES",
                                "source_type": "STARTUP_ACT",
                                "url": item["url"],
                                "startup_name": startup.get('name', ''),
                                "startup_status": "LABELLISÉE",
                            },
                        })

                log.info("page_consolidated_ok", type=item["type"], chars=len(content))

            except Exception as e:
                log.error("fetch_error_consolidated", url=item["url"], error=str(e)[:150])

    log.info("consolidated_scraping_done", total=len(chunks))
    return chunks


def _is_blocked(content: str) -> bool:
    """Détecte si on est bloqué par des protections anti-bot."""
    low = content.lower()
    blocked_indicators = [
        "cloudflare", "we think you might be a bot", "checking your browser",
        "just a moment", "enable javascript and cookies", "security check",
        "ddos protection", "access denied", "403 forbidden", "captcha",
    ]
    return any(indicator in low for indicator in blocked_indicators)


def _extract_wipo_trademarks(soup) -> list[dict]:
    """Extrait les marques depuis le HTML WIPO."""
    trademarks = []
    selectors = [
        ".trademark-result", ".brand-result", ".search-result",
        ".result-item", ".trademark-item", ".brand-item",
        "tr.result-row", "div.result", ".trademark-entry",
    ]
    
    for selector in selectors:
        items = soup.select(selector)
        for item in items[:10]:
            try:
                text = item.get_text(separator=" ", strip=True)
                if len(text) < 10:
                    continue
                    
                name = ""
                name_elem = item.select_one(".trademark-name, .brand-name, .name, h3, h2, strong")
                if name_elem:
                    name = name_elem.get_text(strip=True)
                
                if not name:
                    words = text.split()
                    for word in words:
                        if len(word) > 2 and word.isalpha():
                            name = word
                            break
                
                if name and len(name) > 2:
                    trademarks.append({
                        "name": name,
                        "description": text[:300],
                        "source": "WIPO Global Brand Database",
                    })
                    
            except Exception:
                continue
        
        if trademarks:
            break
    
    return trademarks[:20]


def _extract_f6s_companies(soup) -> list[dict]:
    """Extrait les entreprises depuis le HTML F6S."""
    companies = []
    selectors = [
        ".company-card", ".startup-card", ".company-item", ".startup-item",
        ".profile-card", ".company-profile", ".startup-profile",
        "[class*='company']", "[class*='startup']", "[class*='profile']",
    ]
    
    for selector in selectors:
        items = soup.select(selector)
        for item in items[:10]:
            try:
                text = item.get_text(separator=" ", strip=True)
                if len(text) < 10:
                    continue
                    
                name = ""
                name_elem = item.select_one(".company-name, .startup-name, .profile-name, .name, h3, h2, h1, strong")
                if name_elem:
                    name = name_elem.get_text(strip=True)
                
                if not name:
                    link = item.select_one("a[href*='/company/'], a[href*='/startup/']")
                    if link:
                        name = link.get_text(strip=True)
                
                if name and len(name) > 2:
                    companies.append({
                        "name": name,
                        "description": text[:300],
                        "source": "F6S Startup Platform",
                    })
                    
            except Exception:
                continue
        
        if companies:
            break
    
    return companies[:20]


def _format_trademark_content(item: dict) -> str:
    """Formate le contenu d'une marque."""
    return f"""MARQUE TUNISIENNE : {item.get('name', 'Non spécifié')}

Source : {item.get('source', 'WIPO Global Brand Database')}
Description : {item.get('description', 'Marque enregistrée dans la base WIPO')}

Cette marque fait partie des marques enregistrées accessibles via la base de données mondiale des marques WIPO.

Pour vérifier le statut exact et les détails complets de cette marque :
1. Consulter directement la base WIPO Global Brand Database
2. Vérifier auprès de l'INNORPI pour le statut en Tunisie
3. Consulter un mandataire agréé en propriété industrielle

Statut : Marque référencée dans les bases internationales"""


def _extract_startup_gov_companies(soup) -> list[dict]:
    """Extrait les startups depuis la base officielle startup.gov.tn."""
    startups = []
    
    # Sélecteurs possibles pour la base de données des startups
    selectors = [
        ".startup-item", ".company-item", ".startup-card", ".company-card",
        ".startup-entry", ".company-entry", ".startup-row", ".company-row",
        "tr.startup", "tr.company", ".database-item", ".list-item",
        "[class*='startup']", "[class*='company']", "[class*='database']",
        "table tr", ".table-row", ".data-row",
    ]
    
    for selector in selectors:
        items = soup.select(selector)
        for item in items[:50]:  # Plus d'éléments pour la base officielle
            try:
                text = item.get_text(separator=" ", strip=True)
                if len(text) < 5:
                    continue
                    
                name = ""
                # Chercher le nom dans différents éléments
                name_selectors = [
                    ".startup-name", ".company-name", ".name", ".title",
                    "h1", "h2", "h3", "h4", "strong", "b", ".label",
                    "td:first-child", ".first-column", ".name-column"
                ]
                
                for name_sel in name_selectors:
                    name_elem = item.select_one(name_sel)
                    if name_elem:
                        name = name_elem.get_text(strip=True)
                        if name and len(name) > 2:
                            break
                
                # Si pas de nom trouvé, essayer d'extraire depuis le texte
                if not name:
                    # Chercher des patterns de noms d'entreprise
                    words = text.split()
                    for i, word in enumerate(words):
                        if len(word) > 2 and word[0].isupper():
                            # Prendre jusqu'à 3 mots consécutifs commençant par une majuscule
                            name_parts = [word]
                            for j in range(i+1, min(i+3, len(words))):
                                if words[j][0].isupper() and len(words[j]) > 1:
                                    name_parts.append(words[j])
                                else:
                                    break
                            name = " ".join(name_parts)
                            break
                
                if name and len(name) > 2:
                    # Extraire des informations supplémentaires
                    sector = ""
                    status = "LABELLISÉE"
                    date = ""
                    
                    # Chercher le secteur
                    if "tech" in text.lower() or "technologie" in text.lower():
                        sector = "Technologie"
                    elif "fintech" in text.lower():
                        sector = "FinTech"
                    elif "e-commerce" in text.lower() or "commerce" in text.lower():
                        sector = "E-commerce"
                    elif "santé" in text.lower() or "health" in text.lower():
                        sector = "Santé"
                    elif "éducation" in text.lower() or "education" in text.lower():
                        sector = "Éducation"
                    
                    startups.append({
                        "name": name,
                        "sector": sector,
                        "status": status,
                        "description": text[:200],
                        "source": "Base officielle startup.gov.tn",
                    })
                    
            except Exception:
                continue
        
        if startups:
            break
    
    return startups[:30]  # Limiter à 30 startups


def _format_company_content(item: dict) -> str:
    """Formate le contenu d'une entreprise."""
    return f"""ENTREPRISE TUNISIENNE : {item.get('name', 'Non spécifié')}

Source : {item.get('source', 'F6S Startup Platform')}
Description : {item.get('description', 'Entreprise référencée sur la plateforme F6S')}

Cette entreprise fait partie de l'écosystème entrepreneurial tunisien référencé sur F6S.

Pour plus d'informations sur cette entreprise :
1. Consulter le profil complet sur F6S
2. Vérifier l'enregistrement au Registre National des Entreprises (RNE)
3. Contacter directement l'entreprise via ses canaux officiels

Statut : Entreprise active dans l'écosystème startup tunisien"""


def _format_startup_gov_content(item: dict) -> str:
    """Formate le contenu d'une startup officielle."""
    return f"""STARTUP TUNISIENNE LABELLISÉE : {item.get('name', 'Non spécifié')}

Statut : {item.get('status', 'LABELLISÉE STARTUP ACT')}
Secteur : {item.get('sector', 'Non spécifié')}
Source : {item.get('source', 'Base officielle startup.gov.tn')}

Description : {item.get('description', 'Startup labellisée dans le cadre du Startup Act tunisien')}

Cette startup fait partie de la base officielle des entreprises labellisées selon le Startup Act (Décret-loi 2018-20).

Avantages du label Startup Act :
- Exonération fiscale pendant 8 ans
- Exonération des cotisations patronales CNSS pendant 8 ans  
- Droit à l'échec (protection contre faillite personnelle)
- Congé pour création d'entreprise
- Procédures administratives simplifiées

Pour plus d'informations :
1. Consulter le profil complet sur startup.gov.tn
2. Vérifier les détails du label et des avantages
3. Contacter Smart Capital ou l'API pour accompagnement

Statut officiel : Startup labellisée par l'État tunisien"""