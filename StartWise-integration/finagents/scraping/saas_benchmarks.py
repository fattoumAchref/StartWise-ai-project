"""
SaaSBenchmarkScraper — Agent web search (Tavily) + LLM extraction pipeline.

Pipeline :
  1. TavilySearchAgent interroge le web avec des requêtes ciblées par stage
     (Seed, Series A, Series B, Series C, Public) — résultats réels et datés.
  2. Le texte retourné est envoyé à Gemini pour extraction structurée en JSON
     ({stage: {metric: value}}).
  3. Cache disque 7 jours.
  4. Aucun fallback : si la collecte échoue, résultat vide.

Variables d'environnement :
  TAVILY_API_KEY   → https://app.tavily.com         FREE 1000 req/mois
    ESPRIT_API_KEY   → clé API établissement
    ESPRIT_BASE_URL  → https://tokenfactory.esprit.tn/api
    ESPRIT_MODEL     → ex: hosted_vllm/Llama-3.1-70B-Instruct
    ESPRIT_VERIFY_SSL → true/false (false si certificat interne)
"""
#benchmarks 
from __future__ import annotations

import asyncio
import json
import logging
import os
import textwrap
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .benchmark_schemas import CompanyBenchmark

logger = logging.getLogger(__name__)

MetricMap = Dict[str, float]       # {metric_name: value}
StageData = Dict[str, MetricMap]   # {stage: {metric: value}}

# Requêtes Tavily — 2 requêtes ciblées par stage
SEARCH_QUERIES: Dict[str, List[str]] = {
    "Seed": [
        "SaaS Seed stage benchmarks 2025 gross margin ARR growth rate burn rate",
        "early stage SaaS startup median metrics 2025 Seed funding benchmarks",
    ],
    "Series A": [
        "SaaS Series A benchmarks 2025 gross margin NRR net revenue retention churn LTV CAC payback",
        "Series A SaaS company median metrics 2025 ARR revenue growth benchmarks",
    ],
    "Series B": [
        "SaaS Series B benchmarks 2025 net revenue retention gross margin growth ARR",
        "Series B SaaS metrics benchmarks 2025 CAC payback LTV churn rate",
    ],
    "Series C": [
        "SaaS Series C benchmarks 2025 ARR growth NRR gross margin metrics",
        "Series C SaaS company performance benchmarks 2025 EV revenue multiple",
    ],
    "Public": [
        "public SaaS company benchmarks 2025 EV revenue multiple NRR gross margin median",
        "SaaS public company metrics 2025 median benchmarks revenue growth churn",
    ],
}

# Prompts LLM
_LLM_SYSTEM = textwrap.dedent("""\
    You are a financial data extraction assistant specialised in SaaS benchmarks.

    IMPORTANT RULES:
    - Return ONLY a valid JSON object, no prose, no markdown, no code fences.
    - Keys at the top level must be stage names from:
        ["Seed", "Series A", "Series B", "Series C", "Public"]
    - Only include stages explicitly mentioned in the text.
    - Each stage maps to an object of metric_name → numeric_value.
    - Allowed metric names (use exactly these snake_case keys):
        growth_rate_yoy        (decimal fraction, e.g. 1.50 = 150% YoY growth)
        gross_margin           (decimal fraction, e.g. 0.72 = 72%)
        net_revenue_retention  (decimal fraction, e.g. 1.15 = 115% NRR)
        churn_rate_monthly     (decimal fraction, e.g. 0.025 = 2.5%)
        ltv_cac_ratio          (plain ratio, e.g. 3.2)
        cac_payback_months     (integer months, e.g. 14)
        arr                    (absolute USD value, e.g. 3000000)
        ev_revenue_multiple    (plain multiple, e.g. 8.0)
        burn_rate              (monthly USD burn, e.g. 80000)
    - Convert percentages to decimals (72% → 0.72).
    - If a value is ambiguous or not present, omit it — never guess.
    - If no benchmark data is found at all, return: {}
""")

_LLM_WEB_TMPL = textwrap.dedent("""\
    Extract SaaS benchmark metrics from these web search results.
    Focus on stage: {stage}
    Return a JSON object where keys are stage names and values are metric dicts.

    SEARCH RESULTS (truncated to 10000 chars):
    {text}
""")

# One LLM call at a time — semaphore + retry on 429
_llm_semaphore: Optional[asyncio.Semaphore] = None
_llm_last_call: float = 0.0
_LLM_MIN_INTERVAL: float = 5.0   # max 12 req/min < 15 RPM


def _get_llm_semaphore() -> asyncio.Semaphore:
    """Lazily create the semaphore inside the running event loop."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(1)
    return _llm_semaphore


class LLMExtractor:
    """Extraction LLM via endpoint OpenAI-compatible (Esprit)."""

    def __init__(self) -> None:
        self._provider: Optional[str] = None
        self._call_fn = None
        self._model: str = ""
        self._setup()

    def _setup(self) -> None:
        api_key = os.getenv("ESPRIT_API_KEY")
        if not api_key:
            logger.warning(
                "ESPRIT_API_KEY absent — LLM désactivé."
            )
            return
        base_url = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api").rstrip("/")
        model_name = os.getenv("ESPRIT_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct")
        verify_ssl = os.getenv("ESPRIT_VERIFY_SSL", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }

        async def _esprit(messages):
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0,
                "response_format": {"type": "json_object"},
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=90, verify=verify_ssl) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

        self._call_fn = _esprit
        self._provider = "esprit"
        self._model = model_name
        logger.info(
            f"LLMExtractor → Esprit endpoint ({model_name}) | "
            f"verify_ssl={verify_ssl}"
        )

    @property
    def available(self) -> bool:
        return self._call_fn is not None

    async def _call(self, messages: list) -> str:
        """Sérialise les appels LLM et retente sur 429."""
        import time
        global _llm_last_call
        async with _get_llm_semaphore():
            # Enforce minimum interval between calls
            elapsed = time.monotonic() - _llm_last_call
            if elapsed < _LLM_MIN_INTERVAL:
                await asyncio.sleep(_LLM_MIN_INTERVAL - elapsed)
            for attempt in range(6):
                try:
                    raw = await self._call_fn(messages)
                    _llm_last_call = time.monotonic()
                    return raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        wait = min(10 * (attempt + 1), 60)
                        logger.warning(
                            f"[LLM] Rate limited (429) — attente {wait}s "
                            f"(essai {attempt + 1}/6)"
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise
            raise RuntimeError("LLM rate limit exceeded after 6 retries")

    async def extract_from_text(self, text: str, stage: str) -> StageData:
        """Extrait les métriques depuis le texte Tavily."""
        messages = [
            {"role": "system", "content": _LLM_SYSTEM},
            {"role": "user",   "content": _LLM_WEB_TMPL.format(
                stage=stage, text=text[:10_000]
            )},
        ]
        try:
            raw  = await self._call(messages)
            data: StageData = json.loads(raw)
            count = sum(len(v) for v in data.values())
            logger.info(f"[Tavily→LLM][{stage}] {count} métriques extraites")
            return data
        except Exception as e:
            logger.error(f"[Tavily→LLM][{stage}] Extraction failed: {e}")
            return {}


class TavilySearchAgent:
    """Agent de recherche web via l'API Tavily."""

    def __init__(self, api_key: str, llm: LLMExtractor) -> None:
        from tavily import TavilyClient
        self._client = TavilyClient(api_key=api_key)
        self._llm    = llm

    async def _search(self, query: str) -> str:
        try:
            response = await asyncio.to_thread(
                self._client.search,
                query,
                search_depth="advanced",
                max_results=5,
                include_raw_content=False,
            )
            results = response.get("results", [])
            parts = []
            for r in results:
                title   = r.get("title", "")
                url     = r.get("url", "")
                content = r.get("content", "")
                parts.append(f"[{title}] ({url})\n{content}")
            text = "\n\n---\n\n".join(parts)
            logger.info(
                f"[Tavily] '{query[:55]}…' → {len(results)} résultats, {len(text)} chars"
            )
            return text
        except Exception as e:
            logger.error(f"[Tavily] Recherche échouée : {e}")
            return ""

    async def search_stage(self, stage: str) -> StageData:
        queries = SEARCH_QUERIES.get(stage, [])
        texts   = await asyncio.gather(*[self._search(q) for q in queries])
        combined = "\n\n===\n\n".join(t for t in texts if t)

        if not combined:
            logger.warning(f"[Tavily][{stage}] Aucun contenu retourné")
            return {}

        return await self._llm.extract_from_text(combined, stage)

    async def search_all_stages(self) -> StageData:
        merged: StageData = {}
        for stage in SEARCH_QUERIES.keys():
            logger.info(f"[Tavily] Searching stage: {stage}")
            data = await self.search_stage(stage)
            for s, metrics in data.items():
                merged.setdefault(s, {}).update(metrics)
            await asyncio.sleep(15)  # 15s entre chaque stage → reste sous les 15 RPM
        return merged


class SaaSBenchmarkScraper:
    """Benchmarks SaaS B2B via Tavily + LLM. Cache 7 jours."""

    CACHE_PATH: Path = Path("data/benchmarks_cache.json")
    CACHE_TTL:  timedelta = timedelta(days=7)

    def __init__(self) -> None:
        self._llm    = LLMExtractor()
        tavily_key   = os.getenv("TAVILY_API_KEY", "")
        self._tavily: Optional[TavilySearchAgent] = None
        if tavily_key:
            try:
                self._tavily = TavilySearchAgent(api_key=tavily_key, llm=self._llm)
                logger.info("TavilySearchAgent → prêt [FREE 1000 req/mois]")
            except Exception as e:
                logger.warning(f"Tavily init failed: {e}")
        else:
            logger.warning(
                "TAVILY_API_KEY absent — recherche web désactivée.\n"
                "  Clé gratuite sur https://app.tavily.com (1000 req/mois)"
            )

    async def close(self) -> None:
        """Compat API: rien à fermer dans ce scraper."""
        return None

    def _load_cache(self) -> Optional[StageData]:
        if not self.CACHE_PATH.exists():
            return None
        try:
            raw       = json.loads(self.CACHE_PATH.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(raw["cached_at"])
            if datetime.now() - cached_at < self.CACHE_TTL:
                data = raw.get("data", {})
                if data:
                    logger.info(f"Benchmarks depuis le cache ({cached_at.date()})")
                    return data
                logger.info("Cache vide détecté — nouvelle recherche forcée")
                return None
            logger.info("Cache expiré — re-recherche Tavily")
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        return None

    def _save_cache(self, data: StageData) -> None:
        if not data:
            logger.info("Aucune donnée benchmark à cacher — fichier cache non écrit")
            return
        try:
            self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.CACHE_PATH.write_text(
                json.dumps({"cached_at": datetime.now().isoformat(), "data": data},
                           indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"Benchmarks mis en cache → {self.CACHE_PATH}")
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

    async def _collect_all(self) -> StageData:
        if not self._tavily:
            logger.warning("Tavily absent — aucun benchmark collecté")
            return {}

        logger.info("Tavily : recherche web en cours")
        data = await self._tavily.search_all_stages()
        total = sum(len(v) for v in data.values())
        if total == 0:
            logger.warning("Tavily → aucune métrique collectée")
            return {}

        logger.info(f"Tavily → {total} métriques sur {len(data)} stages")
        return data

    async def fetch_data(self) -> StageData:
        """Force une nouvelle recherche (ignore le cache)."""
        data = await self._collect_all()
        self._save_cache(data)
        return data

    async def get_data(self) -> StageData:
        """Retourne le cache s'il est frais, sinon relance la recherche."""
        return self._load_cache() or await self.fetch_data()

    def get(self, stage: str, metric: str,
            data: Optional[StageData] = None) -> Optional[float]:
        """Lecture ponctuelle d'une métrique."""
        return (data or {}).get(stage, {}).get(metric)

    async def as_benchmarks(self) -> List[CompanyBenchmark]:
        data = await self.get_data()
        source_label = "tavily_websearch"
        confidence   = 0.90
        current_year = datetime.now().year
        result: List[CompanyBenchmark] = []

        for stage, metrics in data.items():
            try:
                b = CompanyBenchmark(
                    company_name=f"Median_{stage.replace(' ', '_')}",
                    sector="SaaS B2B",
                    stage=stage,
                    geography="US",
                    year=current_year,
                    source=source_label,
                    scraped_at=datetime.now(),
                    confidence_score=confidence,
                    **metrics,
                )
                result.append(b)
            except Exception as e:
                logger.warning(f"Stage '{stage}' ignoré : {e}")

        logger.info(f"→ {len(result)} benchmarks | source='{source_label}'")
        return result

