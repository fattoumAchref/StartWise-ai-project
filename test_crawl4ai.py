"""Test rapide de crawl4ai"""
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

async def test():
    browser_cfg = BrowserConfig(
        browser_type="chromium",
        headless=True,
        verbose=True,
        ignore_https_errors=True,
    )
    
    run_cfg = CrawlerRunConfig(
        wait_until="domcontentloaded",
        page_timeout=30000,
        delay_before_return_html=2.0,
    )
    
    print("Démarrage du crawler...")
    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        print("Crawler initialisé, test sur example.com...")
        result = await crawler.arun("https://example.com", config=run_cfg)
        
        if result.success:
            print(f"✅ Succès ! Contenu récupéré : {len(result.html or '')} caractères")
            print(f"Markdown : {len(result.markdown or '')} caractères")
            return True
        else:
            print(f"❌ Échec : {result.error_message}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test())
    print(f"\nRésultat final : {'✅ crawl4ai fonctionne' if success else '❌ crawl4ai ne fonctionne pas'}")
