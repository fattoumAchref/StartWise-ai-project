from __future__ import annotations

import hashlib
import os
import re
from typing import Any

import httpx

from .schemas import AuditEvidence


class QdrantClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("QDRANT_URL", "http://localhost:6333").rstrip("/")
        self.api_key = os.getenv("QDRANT_API_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30"))
        self.collection_base_name = os.getenv(
            "PRODUCT_AUDIT_QDRANT_COLLECTION",
            "product_audit",
        ).strip() or "product_audit"

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def collection_name_for_model(self, model_name: str) -> str:
        suffix = re.sub(r"[^a-zA-Z0-9]+", "_", model_name or "default").strip("_").lower()
        return f"{self.collection_base_name}_{suffix}"[:200]

    def ensure_collection(self, collection_name: str, vector_size: int) -> None:
        response = self._request("GET", f"/collections/{collection_name}", allow_404=True)
        if response and response.get("result"):
            return

        self._request(
            "PUT",
            f"/collections/{collection_name}",
            json={
                "vectors": {
                    "size": int(vector_size),
                    "distance": "Cosine",
                }
            },
        )

    def upsert(
        self,
        collection_name: str,
        session_id: str,
        items: list[AuditEvidence],
        vectors: list[list[float]],
    ) -> None:
        points = []
        for item, vector in zip(items, vectors):
            points.append(
                {
                    "id": self._point_id(session_id=session_id, evidence_id=item.id),
                    "vector": vector,
                    "payload": {
                        "session_id": session_id,
                        "title": item.title,
                        "content": item.content,
                        "source_type": item.source_type,
                        "url": item.url,
                        "metadata": item.metadata,
                    },
                }
            )
        if not points:
            return

        self._request(
            "PUT",
            f"/collections/{collection_name}/points",
            json={"points": points},
            params={"wait": "true"},
        )

    def search(
        self,
        collection_name: str,
        session_id: str,
        query_vector: list[float],
        limit: int = 6,
    ) -> list[AuditEvidence]:
        if not query_vector:
            return []

        body = self._request(
            "POST",
            f"/collections/{collection_name}/points/search",
            json={
                "vector": query_vector,
                "limit": max(1, min(limit, 12)),
                "with_payload": True,
                "filter": {
                    "must": [
                        {
                            "key": "session_id",
                            "match": {"value": session_id},
                        }
                    ]
                },
            },
        )

        results = body.get("result") or body.get("points") or []
        items: list[AuditEvidence] = []
        for index, row in enumerate(results):
            payload = row.get("payload") or {}
            items.append(
                AuditEvidence(
                    id=str(row.get("id") or f"result-{index}"),
                    title=str(payload.get("title") or f"Context {index + 1}"),
                    content=str(payload.get("content") or "").strip(),
                    source_type=str(payload.get("source_type") or "qdrant"),
                    url=str(payload.get("url") or "").strip() or None,
                    score=_coerce_score(row.get("score")),
                    metadata=payload.get("metadata") or {},
                )
            )
        return [item for item in items if item.content]

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        if self.api_key:
            headers["api-key"] = self.api_key

        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = client.request(method, url, headers=headers, json=json, params=params)
                if allow_404 and response.status_code == 404:
                    return {}
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Qdrant request timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:400]
            raise RuntimeError(
                f"Qdrant request failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Qdrant request failed") from exc

    def _point_id(self, session_id: str, evidence_id: str) -> str:
        raw = f"{session_id}:{evidence_id}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()


def _coerce_score(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

