"""
Scraper Droit des Sociétés — création d'entreprises en Tunisie.
Sources standard : RNE, BCT, APII, startup.gov.tn, legislation-securite.tn
Source principale startups : F6S (session persistante pour contourner Cloudflare)
"""

import asyncio
import random
import urllib3
import structlog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = structlog.get_logger("droit_societes")

# ── Sources standard ───────────────────────────────────────────────────────────
SOURCES = [
    {"url": "https://www.registre-entreprises.tn",                               "label": "RNE — Registre National des Entreprises"},
    {"url": "https://www.bct.gov.tn/bct/siteprod/page.jsp?id=68",                "label": "BCT — Financement startups"},
    {"url": "https://www.bct.gov.tn/",                                            "label": "BCT — Banque Centrale de Tunisie"},
    {"url": "https://www.apii.tn/",                                               "label": "APII — Agence Promotion Industrie Innovation"},
    {"url": "https://www.apii.tn/fr/services",                                    "label": "APII — Services aux entreprises"},
    {"url": "https://startup.gov.tn/",                                            "label": "Startup Act — Portail officiel"},
    {"url": "https://www.tunisieinnovation.tn/",                                  "label": "Tunisie Innovation"},
    {"url": "https://legislation-securite.tn/?s=soci%C3%A9t%C3%A9+commerciale",  "label": "JORT — Code Sociétés Commerciales"},
    {"url": "https://legislation-securite.tn/?s=startup",                         "label": "JORT — Startup Act"},
    {"url": "https://legislation-securite.tn/?s=SARL",                            "label": "JORT — SARL"},
    {"url": "https://legislation-securite.tn/?s=capital+risque",                  "label": "JORT — Capital risque"},
    {"url": "https://legislation-securite.tn/?s=investissement",                  "label": "JORT — Investissement"},
    {"url": "https://legislation-securite.tn/?s=creation+entreprise",             "label": "JORT — Création entreprise"},
]

# ── F6S : pages à scraper après avoir passé le check Cloudflare ───────────────
F6S_PAGES = [
    {"url": "https://www.f6s.com/companies/startups/tunisia/go",       "label": "F6S — Startups tunisiennes (page 1)"},
    {"url": "https://www.f6s.com/companies/startups/tunisia/go?page=2","label": "F6S — Startups tunisiennes (page 2)"},
    {"url": "https://www.f6s.com/companies/startups/tunisia/go?page=3","label": "F6S — Startups tunisiennes (page 3)"},
    {"url": "https://www.f6s.com/companies/startups/tunisia/go?page=4","label": "F6S — Startups tunisiennes (page 4)"},
    {"url": "https://www.f6s.com/companies/startups/tunisia/go?page=5","label": "F6S — Startups tunisiennes (page 5)"},
    {"url": "https://www.f6s.com/companies?country=tunisia",           "label": "F6S — Entreprises tunisiennes"},
    {"url": "https://www.f6s.com/startups?country=tunisia",            "label": "F6S — Toutes startups Tunisie"},
]


def _make_std_config():
    from crawl4ai import BrowserConfig, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser = BrowserConfig(
        browser_type="chromium", headless=True, verbose=False,
        ignore_https_errors=True,
        headers={"Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8",
                 "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
        extra_args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded", page_timeout=30000,
        delay_before_return_html=2.0, remove_overlay_elements=True,
        excluded_tags=["nav", "footer", "header", "script", "style", "aside"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.4, threshold_type="fixed"),
        ),
    )
    return browser, run_cfg


def _make_f6s_config():
    """
    Config F6S anti-Cloudflare.
    Stratégie : session persistante avec use_managed_browser=True.
    Le navigateur garde les cookies Cloudflare entre les requêtes.
    magic=True + simulate_user=True imitent un comportement humain.
    """
    from crawl4ai import BrowserConfig, CrawlerRunConfig
    from crawl4ai.content_filter_strategy import PruningContentFilter
    from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

    browser = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=False,
        ignore_https_errors=True,
        use_managed_browser=True,   # session persistante = cookies Cloudflare conservés
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
        extra_args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
        ],
    )

    # Config warm-up : première visite pour passer Cloudflare
    warmup_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=45000,
        delay_before_return_html=8.0,   # laisse Cloudflare valider
        magic=True,
        simulate_user=True,
        override_navigator=True,
        remove_overlay_elements=True,
        excluded_tags=["script", "style"],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.2, threshold_type="fixed"),
        ),
    )

    # Config pages Tunisia : après warm-up, Cloudflare est passé
    page_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=45000,
        delay_before_return_html=6.0,
        magic=True,
        simulate_user=True,
        override_navigator=True,
        remove_overlay_elements=True,
        excluded_tags=["script", "style"],
        # JS scroll pour déclencher le lazy-loading des cards React
        js_code=[
            "await new Promise(r => setTimeout(r, 2000));",
            "window.scrollTo(0, document.body.scrollHeight / 3);",
            "await new Promise(r => setTimeout(r, 1500));",
            "window.scrollTo(0, document.body.scrollHeight * 2 / 3);",
            "await new Promise(r => setTimeout(r, 1500));",
            "window.scrollTo(0, document.body.scrollHeight);",
            "await new Promise(r => setTimeout(r, 2000));",
        ],
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.2, threshold_type="fixed"),
        ),
    )
    return browser, warmup_cfg, page_cfg


async def scrape_all() -> list[dict]:
    from crawl4ai import AsyncWebCrawler
    from bs4 import BeautifulSoup

    chunks = []
    std_browser, std_run = _make_std_config()

    # ── 1. Sources standard ───────────────────────────────────────────────────
    async with AsyncWebCrawler(config=std_browser) as crawler:
        for i, source in enumerate(SOURCES):
            try:
                await asyncio.sleep(random.uniform(2.0, 3.5))
                log.info("fetching", url=source["url"], idx=i+1, total=len(SOURCES))
                result = await crawler.arun(source["url"], config=std_run)
                if not result.success:
                    log.warning("failed", url=source["url"], error=result.error_message)
                    continue
                content = _get_content(result)
                if len(content) < 150:
                    continue
                chunks.append({
                    "source": source["url"],
                    "source_label": source["label"],
                    "content": content[:7000],
                    "metadata": {"domain": "LEGAL", "source_type": "DROIT_SOCIETES", "url": source["url"]},
                })
                log.info("ok", label=source["label"], chars=len(content))

                # Exploration liens
                if result.html:
                    soup = BeautifulSoup(result.html, "lxml")
                    keywords = ("creation", "societe", "sarl", "suarl", "startup", "statut",
                                "forme", "juridique", "capital", "associe", "enregistrement",
                                "immatricul", "investissement", "entreprise")
                    for link_url in _extract_links(soup, source["url"], keywords)[:10]:
                        try:
                            await asyncio.sleep(random.uniform(1.5, 2.5))
                            lr = await crawler.arun(link_url, config=std_run)
                            if lr.success:
                                lc = _get_content(lr)
                                if len(lc) > 200:
                                    chunks.append({
                                        "source": link_url,
                                        "source_label": f"Lien — {source['label']}",
                                        "content": lc[:6000],
                                        "metadata": {"domain": "LEGAL", "source_type": "DROIT_SOCIETES_LINK", "url": link_url},
                                    })
                        except Exception as e:
                            log.warning("link_error", url=link_url, error=str(e)[:80])
            except Exception as e:
                log.warning("fetch_error", url=source["url"], error=str(e)[:100])

    # ── 2. F6S — session persistante anti-Cloudflare ─────────────────────────
    f6s_chunks = await _scrape_f6s()
    chunks.extend(f6s_chunks)

    log.info("droit_societes_done", total=len(chunks))
    return chunks


async def _scrape_f6s() -> list[dict]:
    """
    Stratégie session persistante pour F6S :
    1. Warm-up sur f6s.com (homepage) → Cloudflare délivre le cookie cf_clearance
    2. Warm-up sur f6s.com/community/tunisia → habitue le navigateur au domaine
    3. Scraping des pages Tunisia avec la session qui a le cookie valide
    """
    from crawl4ai import AsyncWebCrawler

    chunks = []
    f6s_browser, warmup_cfg, page_cfg = _make_f6s_config()

    async with AsyncWebCrawler(config=f6s_browser) as crawler:

        # ── Étape 1 : Warm-up homepage ────────────────────────────────────────
        log.info("f6s_warmup_start")
        try:
            r = await crawler.arun("https://www.f6s.com", config=warmup_cfg)
            content = _get_content(r)
            if _is_blocked(content):
                log.warning("f6s_warmup_blocked_homepage")
            else:
                log.info("f6s_warmup_homepage_ok", chars=len(content))
        except Exception as e:
            log.warning("f6s_warmup_error", error=str(e)[:100])

        # Délai humain après le warm-up
        await asyncio.sleep(random.uniform(5.0, 8.0))

        # ── Étape 2 : Warm-up page intermédiaire ─────────────────────────────
        try:
            r = await crawler.arun("https://www.f6s.com/community/tunisia", config=warmup_cfg)
            content = _get_content(r)
            if not _is_blocked(content) and len(content) > 200:
                log.info("f6s_warmup_community_ok", chars=len(content))
                chunks.append({
                    "source": "https://www.f6s.com/community/tunisia",
                    "source_label": "F6S — Communauté startup Tunisie",
                    "content": content[:7000],
                    "metadata": {"domain": "ENTREPRISES", "source_type": "F6S", "url": "https://www.f6s.com/community/tunisia"},
                })
        except Exception as e:
            log.warning("f6s_warmup_community_error", error=str(e)[:80])

        await asyncio.sleep(random.uniform(4.0, 6.0))

        # ── Étape 3 : Scraping pages Tunisia ─────────────────────────────────
        for page in F6S_PAGES:
            try:
                await asyncio.sleep(random.uniform(4.0, 7.0))
                log.info("f6s_page", url=page["url"])

                result = await crawler.arun(page["url"], config=page_cfg)
                content = _get_content(result)

                if _is_blocked(content):
                    log.warning("f6s_still_blocked", url=page["url"])
                    continue

                if len(content) < 200:
                    log.warning("f6s_empty", url=page["url"], len=len(content))
                    continue

                # Extraction des noms de startups depuis le HTML
                startup_names = []
                if result.html:
                    startup_names = _extract_startup_names(result.html)

                if startup_names:
                    names_block = "STARTUPS TUNISIENNES SUR F6S :\n" + "\n".join(f"- {n}" for n in startup_names)
                    content = names_block + "\n\n" + content
                    log.info("f6s_names_found", count=len(startup_names), url=page["url"])
                else:
                    log.info("f6s_no_names_parsed", url=page["url"])

                chunks.append({
                    "source": page["url"],
                    "source_label": page["label"],
                    "content": content[:9000],
                    "metadata": {"domain": "ENTREPRISES", "source_type": "F6S", "url": page["url"]},
                })
                log.info("f6s_ok", label=page["label"], chars=len(content), names=len(startup_names))

            except Exception as e:
                log.warning("f6s_error", url=page["url"], error=str(e)[:100])

    log.info("f6s_done", total_chunks=len(chunks))
    return chunks


def _extract_startup_names(html: str) -> list[str]:
    """Extrait les noms de startups depuis le HTML F6S avec plusieurs sélecteurs."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Sélecteurs CSS potentiels pour les cards F6S
        selectors = [
            "h3.company-name", "h2.company-name", "div.company-name",
            "a.company-name", ".startup-name", ".profile-name",
            "h2.name", "h3.name", ".card-title", ".item-title",
            "[class*='companyName']", "[class*='company-name']",
            "[class*='startup-name']", "[class*='profileName']",
            "article h2", "article h3", ".result-item h3",
            ".company-card h3", ".startup-card h3",
        ]

        names = []
        for sel in selectors:
            found = [el.get_text(strip=True) for el in soup.select(sel)
                     if el.get_text(strip=True) and 2 < len(el.get_text(strip=True)) < 80]
            if found:
                names.extend(found)
                log.info("f6s_selector_matched", selector=sel, count=len(found))
                break  # premier sélecteur qui marche suffit

        # Fallback : chercher dans les balises <a> avec des patterns de profil
        if not names:
            for a in soup.select("a[href*='/company/'], a[href*='/startup/'], a[href*='/profile/']"):
                name = a.get_text(strip=True)
                if 2 < len(name) < 80 and not name.lower().startswith(("http", "see", "view", "follow")):
                    names.append(name)
            if names:
                log.info("f6s_fallback_links", count=len(names))

        # Déduplication
        seen, unique = set(), []
        for n in names:
            k = n.lower()
            if k not in seen:
                seen.add(k)
                unique.append(n)

        return unique[:100]

    except Exception as e:
        log.warning("f6s_parse_error", error=str(e)[:80])
        return []


def _is_blocked(content: str) -> bool:
    low = content.lower()
    return any(p in low for p in [
        "cloudflare", "we think you might be a bot", "checking your browser",
        "just a moment", "enable javascript and cookies",
        "security check", "ddos protection", "access denied",
        "403 forbidden", "please enable cookies",
    ])


def _get_content(result) -> str:
    content = ""
    if result.markdown:
        content = getattr(result.markdown, "raw_markdown", "") or str(result.markdown)
    if not content:
        content = result.cleaned_html or ""
    return content


def _extract_links(soup, base_url: str, keywords: tuple, limit: int = 20) -> list[str]:
    root = "/".join(base_url.split("/", 3)[:3])
    links, seen = [], set()
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        text = (a.get_text(" ", strip=True) or "").lower()
        if not href:
            continue
        if href.startswith("/"):
            href = f"{root}{href}"
        if not href.startswith("http") or href in seen:
            continue
        if any(k in f"{href.lower()} {text}" for k in keywords):
            links.append(href)
            seen.add(href)
        if len(links) >= limit:
            break
    return links
