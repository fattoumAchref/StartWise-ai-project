import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from scraping.saas_benchmarks import SaaSBenchmarkScraper
from scraping.yahoo_finance import YahooFinanceScraper
from scraping.news_scraper import NewsScraper
from scraping.market_data import MarketDataScraper
from scraping.schemas import CompanyBenchmark
from pipeline.cleaner import DataCleaner
from pipeline.vectorizer import BenchmarkVectorizer
from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.INFO)


def _to_json_ready(value):
    """Convert datetimes recursively for JSON serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _to_json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_ready(v) for v in value]
    return value


def _save_json_file(file_name: str, payload: dict) -> None:
    """Persist one JSON artifact under data/ directory."""
    out_path = Path("data") / file_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(_to_json_ready(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logging.info(f"JSON saved -> {out_path}")


def _save_split_results(yahoo_data, news_data, market_data) -> None:
    """Persist scraping outputs into separate JSON files (cache remains separate)."""
    now = datetime.now().isoformat()

    _save_json_file(
        "yahoo_finance_results.json",
        {
            "scraped_at": now,
            "count": len(yahoo_data),
            "yahoo_benchmarks": [b.model_dump() for b in yahoo_data],
        },
    )

    _save_json_file(
        "news_results.json",
        {
            "scraped_at": now,
            "count": len(news_data),
            "news": [item.__dict__ for item in news_data],
        },
    )

    _save_json_file(
        "market_results.json",
        {
            "scraped_at": now,
            "count": len(market_data),
            "market": [item.__dict__ for item in market_data],
        },
    )

async def main():
    print("\n=== SCRAPING PIPELINE START ===\n")
    clean_objects = []
    vectorizer = None

    # 1. Benchmarks SaaS (Tavily + cache 7 jours)
    print("1. Scraping SaaS benchmarks...")
    static = SaaSBenchmarkScraper()
    try:
        static_data = await static.as_benchmarks()
        print(f"   → {len(static_data)} benchmarks fetched")
    except Exception as e:
        logging.error(f"SaaS benchmark scraping failed: {e}")
        static_data = []
    finally:
        await static.close()

    # 2. Yahoo Finance
    print("2. Scraping Yahoo Finance...")
    try:
        yahoo = YahooFinanceScraper()
        yahoo_data = await yahoo.scrape_all()
        print(f"   → {len(yahoo_data)} tickers scraped")
    except Exception as e:
        logging.error(f"Yahoo Finance failed: {e}")
        yahoo_data = []

    # 3. News
    print("3. Fetching news...")
    try:
        news = NewsScraper()
        news_data = news.scrape_all_sectors()
        print(f"   → {len(news_data)} articles")
    except Exception as e:
        logging.error(f"News scraping failed: {e}")
        news_data = []

    # 4. Market data
    print("4. Fetching market data...")
    try:
        market = MarketDataScraper()
        market_data = await market.get_all()
        print(f"   → {len(market_data)} market metrics")
    except Exception as e:
        logging.error(f"Market data failed: {e}")
        market_data = []

    # 5. Clean
    print("\n5. Cleaning data...")
    try:
        all_benchmarks = static_data + yahoo_data
        cleaner = DataCleaner()
        clean_dicts = cleaner.clean([b.model_dump() for b in all_benchmarks])
        print(f"   → {len(clean_dicts)} clean records")
    except Exception as e:
        logging.error(f"Cleaning failed: {e}")
        clean_dicts = []

    # 5b. Save split scraping outputs in JSON for inspection
    try:
        _save_split_results(yahoo_data, news_data, market_data)
    except Exception as e:
        logging.error(f"Could not save split scraping JSON files: {e}")

    # 6. Reconversion dicts → CompanyBenchmark puis vectorisation
    # 6. Vectorize benchmarks
    print("6. Storing benchmarks in ChromaDB...")
    try:
        vectorizer = BenchmarkVectorizer()
        clean_objects = [
            d if isinstance(d, CompanyBenchmark) else CompanyBenchmark(**d)
            for d in clean_dicts
        ]
        print(f"   → {len(clean_objects)} valid CompanyBenchmark objects")
        vectorizer.store(clean_objects)
        print(f"   → Stored in ChromaDB ✓")
    except Exception as e:
        logging.error(f"Vectorization failed: {e}")

        # 7. News summary
    if news_data:
        print(f"\n7. News ready (not vectorized): {len(news_data)} articles")
        for item in news_data[:3]:
            pub = item.published.strftime("%Y-%m-%d") if item.published else "unknown date"
            print(f"   • [{item.sector}] {item.title[:70]} ({pub})")

    # 8. Market data summary
    if market_data:
        print(f"\n8. Market rates fetched: {len(market_data)}")
        for m in market_data:
            print(f"   • {m.metric}: {m.value:.4f}")

    # 9. Test RAG query
    print("\n9. Test RAG query...")
    if vectorizer is None:
        logging.warning("RAG query skipped: vectorizer not initialized")
    else:
        try:
            results = vectorizer.query(
                profile="Series A SaaS B2B Europe ARR 2M growth 150%",
                stage="Series A",
                n=3,
            )
            docs = results.get("documents", [[]])[0]
            print(f"   → {len(docs)} similar benchmarks found")
            for doc in docs:
                print(f"   • {doc[:100]}...")
        except Exception as e:
            logging.error(f"RAG query failed: {e}")

    print("\n=== PIPELINE COMPLETE ===")
    print(f"   {len(clean_objects)} benchmarks in ChromaDB")
    print(f"   {len(news_data)} news articles ready")
    print(f"   {len(market_data)} market metrics ready")


if __name__ == "__main__":
    import sys as _sys

    _orig_unraisable = _sys.unraisablehook
    def _quiet_unraisable(unr):
        msg = str(unr.exc_value)
        if isinstance(unr.exc_value, (RuntimeError, ValueError)) and "closed" in msg.lower():
            return
        _orig_unraisable(unr)
    _sys.unraisablehook = _quiet_unraisable

    asyncio.run(main())