"""
agent/tools/fetch_benchmarks.py — Couche RAG pour les benchmarks sectoriels.

Pipeline :
  1. Construire un profil texte depuis FinancialContext
  2. Interroger ChromaDB via BenchmarkVectorizer.query_top()
  3. Si similarité max < SIMILARITY_THRESHOLD (ou collection vide)
     → actualiser depuis Tavily, vectoriser, re-requête
  4. Extraire les médianes numériques depuis les docs (regex — pas de LLM)
  5. Retourner BenchmarkResult

Entrée  : FinancialContext
Sortie  : BenchmarkResult
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import re
import statistics
from typing import Optional

from finagents.models.data_models import BenchmarkResult, FinancialContext, Phase

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

SIMILARITY_THRESHOLD = 0.45   # en dessous → rafraîchir depuis Tavily
TOP_K = 5                     # nombre de docs Chroma à récupérer

# Cache process-level : évite de re-scraper Tavily pour un stage déjà rafraîchi
# Persiste entre les reruns Streamlit (module chargé une seule fois par worker)
_refreshed_stages: set[str] = set()


# ── Mapping Phase → stage Chroma ──────────────────────────────────────────────

def _infer_stage(ctx: "FinancialContext") -> str:
    """
    Détermine le stage Chroma depuis le contexte complet.

    Le Phase enum ne distingue pas Series A / B / C, donc on utilise
    l'ARR annuel (monthly_revenue × 12) comme critère principal.
    Seuils en DT (devise locale du projet) :

        ARR < 300 000 DT   →  Seed
        ARR < 3 000 000 DT →  Series A
        ARR < 15 000 000 DT→  Series B
        ARR ≥ 15 000 000 DT→  Series C

    Si monthly_revenue est absent, on retombe sur la phase hint :
        SEED / SEED_RAISING → Seed
        TRACTION / FUNDRAISING → Series A (a minima de la traction)
    """
    if ctx.monthly_revenue and ctx.monthly_revenue > 0:
        arr = ctx.monthly_revenue * 12
        if arr < 300_000:
            return "Seed"
        if arr < 3_000_000:
            return "Series A"
        if arr < 15_000_000:
            return "Series B"
        return "Series C"

    # Fallback sur la phase si pas de revenue
    phase_val = ctx.phase_hint.value if isinstance(ctx.phase_hint, Phase) else str(ctx.phase_hint).lower()
    if phase_val in ("traction", "fundraising"):
        return "Series A"
    return "Seed"


# ── Construction du profil de requête ─────────────────────────────────────────

def _build_profile(ctx: FinancialContext) -> str:
    """
    Construit un texte en langage naturel financier à partir du
    FinancialContext, utilisé comme vecteur de requête dans Chroma.
    Format cohérent avec BenchmarkVectorizer.to_text().
    """
    stage = _infer_stage(ctx)
    sector = ctx.secteur if ctx.secteur and ctx.secteur != "unknown" else "SaaS"
    geo = ctx.pays if ctx.pays else "TN"

    parts = [f"{stage} stage {sector} startup based in {geo}"]

    if ctx.monthly_revenue and ctx.monthly_revenue > 0:
        arr = ctx.monthly_revenue * 12
        if arr >= 1_000_000:
            parts.append(f"${arr / 1_000_000:.1f}M ARR")
        else:
            parts.append(f"${arr / 1_000:.0f}k ARR")

    if ctx.churn_rate is not None:
        parts.append(f"monthly churn rate of {ctx.churn_rate * 100:.1f}%")

    if ctx.n_clients and ctx.prix_client:
        ltv_rough = ctx.prix_client / ctx.churn_rate if ctx.churn_rate else None
        if ltv_rough:
            ratio = ltv_rough / (ctx.marketing_budget / ctx.new_clients_month
                                 if ctx.marketing_budget and ctx.new_clients_month
                                 else ltv_rough / 3)
            parts.append(f"LTV to CAC ratio of {ratio:.1f}x")

    if ctx.burn_rate and ctx.burn_rate > 0:
        parts.append(f"monthly burn rate of ${ctx.burn_rate / 1_000:.0f}k")

    return ". ".join(parts) + "."


# ── Parsing des métriques depuis les docs Chroma ──────────────────────────────

_RE_GROSS_MARGIN    = re.compile(r"gross margin of ([\d.]+)%")
_RE_CHURN           = re.compile(r"monthly churn rate of ([\d.]+)%")
_RE_EV_MULTIPLE     = re.compile(r"EV to revenue multiple of ([\d.]+)x")
_RE_LTV_CAC         = re.compile(r"LTV to CAC ratio of ([\d.]+)x")
_RE_CAC_PAYBACK     = re.compile(r"CAC payback period of ([\d.]+) months")


def _parse_doc(doc: str) -> dict[str, Optional[float]]:
    """
    Extrait les métriques numériques d'un document Chroma (format to_text()).
    Les valeurs % sont normalisées en décimaux (72% → 0.72).
    """
    def _pct(m) -> Optional[float]:
        return float(m.group(1)) / 100.0 if m else None

    def _raw(m) -> Optional[float]:
        return float(m.group(1)) if m else None

    return {
        "gross_margin":       _pct(_RE_GROSS_MARGIN.search(doc)),
        "churn_rate_monthly": _pct(_RE_CHURN.search(doc)),
        "ev_revenue_multiple": _raw(_RE_EV_MULTIPLE.search(doc)),
        "ltv_cac_ratio":      _raw(_RE_LTV_CAC.search(doc)),
        "cac_payback_months": _raw(_RE_CAC_PAYBACK.search(doc)),
    }


def _median(values: list[Optional[float]]) -> Optional[float]:
    """Médiane des valeurs non-None."""
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    return round(statistics.median(valid), 4)


def _aggregate(parsed_docs: list[dict]) -> dict[str, Optional[float]]:
    """
    Agrège les métriques de plusieurs docs en médianes.
    """
    keys = ["gross_margin", "churn_rate_monthly", "ev_revenue_multiple",
            "ltv_cac_ratio", "cac_payback_months"]
    return {k: _median([d.get(k) for d in parsed_docs]) for k in keys}


# ── Refresh Tavily → Chroma ───────────────────────────────────────────────────

def _run_async(coro):
    """
    Lance une coroutine depuis un contexte synchrone (compatible Streamlit).
    Crée toujours un nouveau thread avec son propre event loop.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _refresh_from_tavily(stage: str) -> bool:
    """
    Déclenche le scraper Tavily + Yahoo Finance pour le stage donné,
    vectorise les résultats dans Chroma.
    Retourne True si au moins un benchmark a été stocké.

    Sources :
      - SaaSBenchmarkScraper (Tavily) → tous les stages
      - YahooFinanceScraper           → stage Public/Series C (données cotées réelles)
    """
    try:
        from finagents.finance.tools.benchmark_vectorizer import BenchmarkVectorizer
        from finagents.scraping.saas_benchmarks import SaaSBenchmarkScraper

        all_benchmarks = []

        # ── Source 1 : Tavily ──────────────────────────────────────────────────
        scraper = SaaSBenchmarkScraper()
        tavily_benchmarks = _run_async(scraper.as_benchmarks())
        if tavily_benchmarks:
            all_benchmarks.extend(tavily_benchmarks)
            logger.info(f"[RAG] Tavily → {len(tavily_benchmarks)} benchmarks")
        else:
            logger.warning("[RAG] Tavily : aucun benchmark récupéré")

        # ── Source 2 : Yahoo Finance (Public + Series C uniquement) ───────────
        if stage in ("Public", "Series C"):
            try:
                from finagents.scraping.yahoo_finance import YahooFinanceScraper
                yahoo_benchmarks = _run_async(YahooFinanceScraper().scrape_all())
                if yahoo_benchmarks:
                    all_benchmarks.extend(yahoo_benchmarks)
                    logger.info(f"[RAG] Yahoo Finance → {len(yahoo_benchmarks)} benchmarks cotés")
            except Exception as yf_exc:
                logger.warning(f"[RAG] Yahoo Finance ignoré : {yf_exc}")

        if not all_benchmarks:
            logger.warning("[RAG] Aucune source n'a retourné de benchmarks")
            return False

        # Filtrer sur le stage demandé
        stage_benchmarks = [b for b in all_benchmarks if b.stage == stage]
        if not stage_benchmarks:
            stage_benchmarks = all_benchmarks  # stocker tout si le stage exact est absent

        vec = BenchmarkVectorizer()
        vec.store(stage_benchmarks)
        logger.info(f"[RAG] {len(stage_benchmarks)} benchmarks stockés (stage={stage})")
        return True

    except Exception as exc:
        logger.error(f"[RAG] Refresh échoué : {exc}")
        return False


# ── Requête Chroma ─────────────────────────────────────────────────────────────

def _query_chroma(profile: str, stage: str, n: int = TOP_K) -> list[dict]:
    """
    Interroge Chroma et retourne les top-k résultats.
    Retourne [] si la collection est vide ou si la requête échoue.
    """
    try:
        from finagents.finance.tools.benchmark_vectorizer import BenchmarkVectorizer
        vec = BenchmarkVectorizer()

        if vec.collection.count() == 0:
            logger.info("[RAG] Chroma vide — refresh nécessaire")
            return []

        results = vec.query_top(profile=profile, stage=stage, n=n)
        return results

    except Exception as exc:
        logger.warning(f"[RAG] Chroma query échouée : {exc}")
        return []


# ── Fonction principale ────────────────────────────────────────────────────────

def fetch_benchmarks(ctx: FinancialContext) -> BenchmarkResult:
    """
    Récupère les benchmarks sectoriels les plus proches du profil du fondateur.

    Étapes :
      1. Construire le profil texte depuis FinancialContext
      2. Interroger ChromaDB
      3. Si similarité insuffisante → refresh Tavily → re-requête
      4. Extraire et agréger les médianes depuis les docs
      5. Retourner BenchmarkResult

    Retourne un BenchmarkResult vide (source="unavailable") en cas d'échec.
    """
    stage = _infer_stage(ctx)
    profile = _build_profile(ctx)

    logger.info(f"[RAG] Profil construit — stage={stage}")
    logger.debug(f"[RAG] Profil : {profile}")

    # ── Étape 1 : requête initiale Chroma ─────────────────────────────────────
    results = _query_chroma(profile, stage)

    best_similarity = max((r["similarity"] for r in results), default=0.0)
    logger.info(f"[RAG] Chroma → {len(results)} docs, similarité max={best_similarity:.3f}")

    fetched_live = False   # True = Tavily appelé en direct dans cette invocation

    # ── Étape 2 : refresh si nécessaire (une seule fois par stage par session) ──
    if best_similarity < SIMILARITY_THRESHOLD and stage not in _refreshed_stages:
        logger.info(
            f"[RAG] Similarité {best_similarity:.3f} < seuil {SIMILARITY_THRESHOLD} "
            f"→ refresh Tavily pour stage={stage}"
        )
        refreshed = _refresh_from_tavily(stage)
        if refreshed:
            # Only mark as "done" when Tavily actually returned data.
            # If it failed (missing key, network error) we leave the stage
            # out of _refreshed_stages so the next request will retry.
            _refreshed_stages.add(stage)
            fetched_live = True
            results = _query_chroma(profile, stage)
            best_similarity = max((r["similarity"] for r in results), default=0.0)
            logger.info(
                f"[RAG] Après refresh → {len(results)} docs, "
                f"similarité max={best_similarity:.3f}"
            )
        else:
            logger.warning(
                f"[RAG] Refresh Tavily échoué pour stage={stage} — "
                "vérifiez TAVILY_API_KEY dans .env (clé gratuite sur app.tavily.com)"
            )
    elif best_similarity < SIMILARITY_THRESHOLD and stage in _refreshed_stages:
        logger.info(f"[RAG] Stage={stage} déjà rafraîchi avec succès cette session — Tavily ignoré")

    # ── Étape 3 : aucun résultat exploitable ──────────────────────────────────
    if not results:
        logger.warning("[RAG] Aucun benchmark disponible")
        return BenchmarkResult(
            source="unavailable",
            similarity_score=0.0,
        )

    # ── Étape 4 : extraction et agrégation des médianes ───────────────────────
    parsed = [_parse_doc(r["doc"]) for r in results]
    agg = _aggregate(parsed)

    origins = list({r["source"] for r in results if r.get("source") and r["source"] != "?"})
    origin_label = ", ".join(sorted(origins)) if origins else "web"
    # fetched_live = True  → Tavily vient d'être appelé, docs frais
    # fetched_live = False → données lues depuis ChromaDB (cache)
    source_label = f"Tavily live · {len(results)} doc(s)" if fetched_live else f"ChromaDB cache · {len(results)} doc(s) · origine : {origin_label}"

    logger.info(
        f"[RAG] Métriques agrégées : "
        f"churn={agg['churn_rate_monthly']}, "
        f"gross_margin={agg['gross_margin']}, "
        f"ev_multiple={agg['ev_revenue_multiple']}"
    )

    # Estimate TND-denominated CAC/LTV from scraped ratios + ctx pricing data.
    # Method: dimensionless ratios (payback months, LTV/CAC) × prix_client removes
    # the USD→TND conversion problem.
    # ⚠ LIMITATION: assumes benchmark was for a pricing tier similar to this startup.
    # If the benchmark used enterprise ($500/mo) pricing but this startup charges
    # SMB (50 DT/mo), the ratio collapses by ~10× in absolute terms. Use as order-
    # of-magnitude reference only, not as precise targets.
    cac_tnd = None
    ltv_tnd = None
    cac_ltv_estimated = False
    if ctx.prix_client and ctx.prix_client > 0:
        _payback = agg.get("cac_payback_months")
        _ratio   = agg.get("ltv_cac_ratio")
        _churn   = ctx.churn_rate
        if _payback and _payback > 0:
            cac_tnd = round(ctx.prix_client * _payback, 0)
            cac_ltv_estimated = True
        if _ratio and _ratio > 0 and cac_tnd:
            ltv_tnd = round(cac_tnd * _ratio, 0)
        elif _churn and _churn > 0:
            ltv_tnd = round(ctx.prix_client / _churn, 0)

    # Append estimation disclaimer to source label when currency conversion was applied
    if cac_ltv_estimated:
        source_label += (
            " · CAC/LTV estimés en DT (ratio dimensionless × prix_client — "
            "valable uniquement si segment de prix similaire au benchmark)"
        )

    return BenchmarkResult(
        cac_median=cac_tnd,
        ltv_median=ltv_tnd,
        churn_median=agg["churn_rate_monthly"],
        gross_margin_median=agg["gross_margin"],
        valorisation_multiple=agg["ev_revenue_multiple"],
        source=source_label,
        similarity_score=round(best_similarity, 3),
        documents_raw=[r["doc"] for r in results],
    )


# ── Test rapide ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from finagents.models.data_models import DataQuality

    sample = FinancialContext(
        burn_rate=40_000,
        cash_balance=120_000,
        monthly_revenue=25_000,
        n_clients=50,
        prix_client=500.0,
        churn_rate=0.05,
        secteur="SaaS",
        pays="TN",
        phase_hint=Phase.TRACTION,
        burn_quality=DataQuality.ESTIMATED,
        cash_quality=DataQuality.REAL,
        revenue_quality=DataQuality.ESTIMATED,
    )

    result = fetch_benchmarks(sample)
    print("\n── BenchmarkResult ──────────────────────────────")
    print(f"  source              : {result.source}")
    print(f"  similarity_score    : {result.similarity_score}")
    print(f"  churn_median        : {result.churn_median}")
    print(f"  gross_margin_median : {result.gross_margin_median}")
    print(f"  valorisation_x      : {result.valorisation_multiple}")
    print(f"  docs récupérés      : {len(result.documents_raw)}")
