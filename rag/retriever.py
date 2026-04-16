"""
Retriever — exécute les sous-requêtes vectorielles en parallèle.
"""

import asyncio
from dataclasses import dataclass
from embeddings import embedding_service
from vector_store import vector_store
from rag.reformulator import SubQuery


@dataclass
class RetrievedChunk:
    content: str
    metadata: dict
    score: float
    collection: str
    source_label: str  # Référence citée dans la réponse finale


class Retriever:
    async def retrieve(self, sub_queries: list[SubQuery], top_k: int = 20) -> list[RetrievedChunk]:
        """
        Exécute toutes les sous-requêtes en parallèle et agrège les résultats.
        """
        tasks = [self._search_one(sq, top_k) for sq in sub_queries]
        results_per_query = await asyncio.gather(*tasks, return_exceptions=True)

        chunks = []
        for results in results_per_query:
            if isinstance(results, Exception):
                continue
            chunks.extend(results)

        # Déduplication par ID Qdrant
        seen = set()
        unique = []
        for c in chunks:
            key = c.metadata.get("id") or c.content[:100]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    async def _search_one(self, sq: SubQuery, top_k: int) -> list[RetrievedChunk]:
        """Recherche vectorielle pour une sous-requête."""
        vector = await embedding_service.embed_query(sq.text)

        # Filtres adaptés selon la collection
        filters = self._prepare_filters(sq.collection, sq.filters)

        raw_results = await vector_store.search(
            collection=sq.collection,
            vector=vector,
            top_k=top_k,
            filters=filters,
        )

        return [
            RetrievedChunk(
                content=r["payload"].get("content", ""),
                metadata=r["payload"],
                score=r["score"],
                collection=sq.collection,
                source_label=self._build_source_label(r["payload"], sq.collection),
            )
            for r in raw_results
        ]

    def _prepare_filters(self, collection: str, user_filters: dict) -> dict:
        """Prépare les filtres Qdrant — ajoute des filtres par défaut selon la collection."""
        filters = dict(user_filters)

        # Forcer le statut EN_VIGUEUR pour les textes législatifs
        if collection == "legal_articles" and "status" not in filters:
            filters["status"] = "EN_VIGUEUR"

        # Exclure les marques expirées par défaut
        if collection == "trademarks" and "status" not in filters:
            filters["status"] = "ACTIF"

        return filters

    def _build_source_label(self, payload: dict, collection: str) -> str:
        """Construit la référence citée dans la réponse (ex: 'Art. 23 CSC, Loi 2000-93')."""
        if collection == "legal_articles":
            return (
                f"{payload.get('article_number', '')} "
                f"— {payload.get('title_fr', '')} "
                f"({payload.get('jort_number', '')})"
            ).strip(" —")

        if collection == "trademarks":
            return f"Marque '{payload.get('name_exact', '')}' — INNORPI N°{payload.get('registration_number', '')}"

        if collection == "court_decisions":
            return f"{payload.get('court', '')} — N°{payload.get('decision_number', '')} du {payload.get('decision_date', '')}"

        if collection == "tax_regulations":
            return f"DGI — {payload.get('tax_type', '')} {payload.get('rate', '')}% (depuis {payload.get('effective_from', '')})"

        if collection == "software_licenses":
            return f"Licence {payload.get('spdx_id', '')} — {payload.get('full_name', '')}"

        return payload.get("source_label", "Source interne")
