"""
pipeline/vectorizer.py — BenchmarkVectorizer.

Modele par defaut : intfloat/e5-base-v2
    - Meilleur score local sur ce projet (Top1/MRR)
    - Bon compromis precision/robustesse

Installation :
        pip install sentence-transformers
        # Le modele se telecharge automatiquement au premier lancement

Moved from pipeline/vectorizer.py → agents/finance/tools/vectorizer.py
(pipeline/ directory was removed; this file now lives next to its only
consumer, fetch_benchmarks.py)
"""

import logging
import math
import os
from typing import List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

from scraping.schemas import CompanyBenchmark

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "intfloat/e5-base-v2"
)


def _is_e5_model(model_name: str) -> bool:
    return "e5" in model_name.lower()


def _norm_pct(val: Optional[float], already_pct_threshold: float = 2.0) -> Optional[str]:
    """
    Normalise décimal ou pourcentage → string lisible.
    0.72  → "72.0%"
    2.0   → "200.0%"  (growth_rate_yoy)
    72.0  → "72.0%"   (déjà en %)
    """
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if val <= already_pct_threshold:
        return f"{val * 100:.1f}%"
    return f"{val:.1f}%"


def _fmt_arr(val: Optional[float]) -> Optional[str]:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    if val >= 1_000_000:
        return f"${val / 1_000_000:.1f}M ARR"
    if val > 0:
        return f"${val / 1_000:.0f}k ARR"
    return None


def _valid(val) -> bool:
    """Retourne False si val est None ou NaN."""
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return True


class BenchmarkVectorizer:

    def __init__(self):
        path = os.getenv("CHROMA_PATH", "./chroma_db")
        self._is_e5 = _is_e5_model(EMBEDDING_MODEL)
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(
            name="financial_benchmarks",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)

    # ── Sérialisation ────────────────────────────────────────────────────────

    def to_text(self, b: CompanyBenchmark) -> str:
        """
        Texte en langage naturel financier — optimisé pour FinLang embeddings.
        Tous les NaN sont filtrés avant d'être ajoutés.
        """
        parts = [
            f"{b.stage} stage {b.sector} company",
            f"based in {b.geography}",
        ]

        arr_str = _fmt_arr(b.arr)
        if arr_str:
            parts.append(arr_str)

        growth = _norm_pct(b.growth_rate_yoy, already_pct_threshold=2.0)
        if growth:
            parts.append(f"growing at {growth} year over year")

        margin = _norm_pct(b.gross_margin, already_pct_threshold=2.0)
        if margin:
            parts.append(f"gross margin of {margin}")

        if _valid(b.ltv_cac_ratio):
            parts.append(f"LTV to CAC ratio of {b.ltv_cac_ratio:.1f}x")

        churn = _norm_pct(b.churn_rate_monthly, already_pct_threshold=0.5)
        if churn:
            parts.append(f"monthly churn rate of {churn}")

        nrr = _norm_pct(b.net_revenue_retention, already_pct_threshold=2.0)
        if nrr:
            parts.append(f"net revenue retention of {nrr}")

        if _valid(b.cac_payback_months):
            parts.append(f"CAC payback period of {b.cac_payback_months:.0f} months")

        if _valid(b.burn_rate):
            parts.append(f"monthly burn rate of ${b.burn_rate / 1_000:.0f}k")

        if _valid(b.ev_revenue_multiple):
            parts.append(f"EV to revenue multiple of {b.ev_revenue_multiple:.1f}x")

        return ". ".join(parts) + "."

    # ── Stockage ─────────────────────────────────────────────────────────────

    def store(self, benchmarks: List[CompanyBenchmark]):
        if not benchmarks:
            logger.warning("Nothing to store")
            return

        texts = [self.to_text(b) for b in benchmarks]
        embed_texts = [f"passage: {t}" for t in texts] if self._is_e5 else texts
        embeddings = self.model.encode(embed_texts, show_progress_bar=True).tolist()
        ids        = [f"{b.company_name}_{b.year}_{b.source}" for b in benchmarks]
        metadatas  = [
            {
                "sector":     b.sector,
                "stage":      b.stage,
                "source":     b.source,
                "confidence": b.confidence_score,
                "year":       b.year,
            }
            for b in benchmarks
        ]

        self.collection.upsert(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info(f"Stored {len(benchmarks)} benchmarks in ChromaDB")

    # ── Requête ──────────────────────────────────────────────────────────────

    def query(self, profile: str, stage: str, n: int = 5) -> dict:
        """Requête filtrée par stage — retourne le format Chroma brut."""
        qtext = f"query: {profile}" if self._is_e5 else profile
        embedding = self.model.encode([qtext]).tolist()
        return self.collection.query(
            query_embeddings=embedding,
            n_results=n,
            where={"stage": stage},
            include=["documents", "metadatas", "distances"],
        )

    def query_top(self, profile: str, stage: str, n: int = 3) -> List[dict]:
        """
        Retourne une liste de dicts prête pour C3 RAG.
        Triée par similarité DESC puis confidence DESC.

        Format retourné :
            [{
                "doc":        str,
                "similarity": float,
                "stage":      str,
                "source":     str,
                "confidence": float,
                "year":       int,
            }]
        """
        raw       = self.query(profile=profile, stage=stage, n=n)
        docs      = raw.get("documents", [[]])[0]
        distances = raw.get("distances",  [[]])[0]
        metas     = raw.get("metadatas",  [[]])[0]

        results = []
        for doc, dist, meta in zip(docs, distances, metas):
            results.append({
                "doc":        doc,
                "similarity": round(1 - dist, 3),
                "stage":      meta.get("stage",      "?"),
                "source":     meta.get("source",     "?"),
                "confidence": meta.get("confidence", 0.0),
                "year":       meta.get("year",       "?"),
            })

        results.sort(key=lambda x: (x["similarity"], x["confidence"]), reverse=True)
        return results

    # ── Debug ────────────────────────────────────────────────────────────────

    def inspect(self, limit: int = 5) -> None:
        """Affiche un résumé du contenu de Chroma."""
        count  = self.collection.count()
        sample = self.collection.get(
            limit=limit,
            include=["documents", "metadatas"],
        )
        print(f"\n{'='*55}")
        print(f"  Chroma — {count} documents | showing {limit}")
        print(f"{'='*55}")
        for i, (doc, meta) in enumerate(
            zip(sample["documents"], sample["metadatas"]), 1
        ):
            print(f"\n[{i}] {meta}")
            print(f"    {doc[:180]}")
        print()
