"""
Vector Store — ChromaDB persistant (remplace Qdrant).
Stockage local dans ./chroma_db, aucun serveur requis.
"""

import asyncio
import uuid
import chromadb
from chromadb.config import Settings as ChromaSettings
from config import cfg
import structlog

log = structlog.get_logger(__name__)

# Noms des collections (identiques aux constantes config)
COLLECTIONS = [
    cfg.col_legal,
    cfg.col_trademarks,
    cfg.col_clauses,
    cfg.col_decisions,
    cfg.col_tax,
    cfg.col_licenses,
]


class VectorStore:
    """Client ChromaDB centralisé — persistant sur disque."""

    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=cfg.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collections: dict[str, chromadb.Collection] = {}

    def setup(self):
        """Crée toutes les collections si elles n'existent pas (sync)."""
        for name in COLLECTIONS:
            col = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
            self._collections[name] = col
            log.info("collection_ready", name=name)

    async def async_setup(self):
        """Version async du setup — wrappée pour être appelable depuis async code."""
        await asyncio.to_thread(self.setup)

    def _get_col(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    # ── Upsert ───────────────────────────────────────────────────────────────

    def _upsert_sync(self, collection: str, points: list[dict]):
        """
        Insère ou met à jour des points.
        Chaque point : {"id": str, "vector": list[float], "payload": dict}
        """
        col = self._get_col(collection)
        ids        = [str(p.get("id") or uuid.uuid4()) for p in points]
        embeddings = [p["vector"] for p in points]
        metadatas  = [p.get("payload", {}) for p in points]
        documents  = [p.get("payload", {}).get("content", "") for p in points]

        col.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    async def upsert(self, collection: str, points: list[dict]):
        await asyncio.to_thread(self._upsert_sync, collection, points)

    # ── Search ───────────────────────────────────────────────────────────────

    def _search_sync(
        self,
        collection: str,
        vector: list[float],
        top_k: int,
        filters: dict | None,
    ) -> list[dict]:
        col = self._get_col(collection)
        where = self._build_where(filters) if filters else None

        kwargs: dict = dict(
            query_embeddings=[vector],
            n_results=min(top_k, max(col.count(), 1)),
            include=["metadatas", "distances", "documents"],
        )
        if where:
            kwargs["where"] = where

        try:
            res = col.query(**kwargs)
        except Exception as e:
            log.warning("chroma_search_error", error=str(e), collection=collection)
            return []

        results = []
        for i, doc_id in enumerate(res["ids"][0]):
            meta = res["metadatas"][0][i] if res["metadatas"] else {}
            dist = res["distances"][0][i] if res["distances"] else 1.0
            # ChromaDB retourne une distance cosine [0,2] — on la convertit en similarité
            score = 1.0 - (dist / 2.0)
            results.append({
                "id": doc_id,
                "score": score,
                "payload": meta,
            })

        return results

    async def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[dict]:
        return await asyncio.to_thread(
            self._search_sync, collection, vector, top_k, filters
        )

    async def search_multi(self, requests: list[dict]) -> list[list[dict]]:
        """Recherche vectorielle multi-collection en parallèle."""
        tasks = [
            self.search(
                r["collection"], r["vector"], r.get("top_k", 20), r.get("filters")
            )
            for r in requests
        ]
        return await asyncio.gather(*tasks)

    # ── Filtres ──────────────────────────────────────────────────────────────

    def _build_where(self, filters: dict) -> dict | None:
        """Convertit {field: value} en syntaxe ChromaDB where."""
        conditions = []
        for field, value in filters.items():
            if isinstance(value, dict):
                # Range : {"gte": val} ou {"lte": val}
                sub = {}
                if "gte" in value:
                    sub["$gte"] = value["gte"]
                if "lte" in value:
                    sub["$lte"] = value["lte"]
                if sub:
                    conditions.append({field: sub})
            elif isinstance(value, list):
                conditions.append({field: {"$in": value}})
            elif isinstance(value, bool):
                conditions.append({field: {"$eq": value}})
            else:
                conditions.append({field: {"$eq": value}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ── Utils ─────────────────────────────────────────────────────────────────

    async def delete_collection(self, collection: str):
        await asyncio.to_thread(self._client.delete_collection, collection)
        self._collections.pop(collection, None)

    async def get_collection_info(self, collection: str) -> dict:
        def _info():
            col = self._get_col(collection)
            return {"name": collection, "vectors_count": col.count()}
        return await asyncio.to_thread(_info)


# Singleton partagé
vector_store = VectorStore()
