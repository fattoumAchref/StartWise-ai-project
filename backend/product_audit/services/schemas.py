from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditAttachment:
    name: str
    content_type: str = "text/plain"
    text: str | None = None
    summary_text: str | None = None
    base64_data: str | None = None
    source_url: str | None = None
    extracted_text: str | None = None
    extraction_status: str | None = None
    extraction_error: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditAttachment":
        return cls(
            name=str(payload.get("name") or "attachment").strip() or "attachment",
            content_type=str(payload.get("content_type") or "application/octet-stream").strip(),
            text=_clean_optional_text(payload.get("text")),
            summary_text=_clean_optional_text(payload.get("summary_text")),
            base64_data=_clean_optional_text(payload.get("base64_data")),
            source_url=_clean_optional_text(payload.get("source_url")),
            extracted_text=_clean_optional_text(payload.get("extracted_text")),
            extraction_status=_clean_optional_text(payload.get("extraction_status")),
            extraction_error=_clean_optional_text(payload.get("extraction_error")),
        )

    def retrieval_text(self) -> str:
        if self.extracted_text:
            return self.extracted_text
        if self.text:
            return self.text
        if self.summary_text:
            return self.summary_text
        return ""

    def llm_part(self) -> dict[str, Any] | None:
        if self.base64_data:
            return {
                "inline_data": {
                    "mime_type": self.content_type,
                    "data": _strip_data_url_prefix(self.base64_data),
                }
            }
        if self.text:
            return {"text": f"Attachment ({self.name}):\n{self.text}"}
        if self.summary_text:
            return {"text": f"Attachment summary ({self.name}):\n{self.summary_text}"}
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content_type": self.content_type,
            "text": self.text,
            "summary_text": self.summary_text,
            "source_url": self.source_url,
            "has_inline_data": bool(self.base64_data),
            "extracted_text": self.extracted_text,
            "extraction_status": self.extraction_status,
            "extraction_error": self.extraction_error,
        }


@dataclass
class AuditEvidence:
    id: str
    title: str
    content: str
    source_type: str
    url: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source_type": self.source_type,
            "url": self.url,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass
class AuditSessionState:
    session_id: str
    startup_name: str = ""
    product_description: str = ""
    website_url: str | None = None
    audit_goal: str = ""
    attachments: list[AuditAttachment] = field(default_factory=list)
    report: str | None = None
    indexed_documents: int = 0
    qdrant_collection: str | None = None
    retrieved_context: list[AuditEvidence] = field(default_factory=list)
    external_sources: list[AuditEvidence] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

    def touch(self) -> None:
        self.updated_at = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "startup_name": self.startup_name,
            "product_description": self.product_description,
            "website_url": self.website_url,
            "audit_goal": self.audit_goal,
            "attachments": [item.to_dict() for item in self.attachments],
            "report": self.report,
            "indexed_documents": self.indexed_documents,
            "qdrant_collection": self.qdrant_collection,
            "retrieved_context": [item.to_dict() for item in self.retrieved_context],
            "external_sources": [item.to_dict() for item in self.external_sources],
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _clean_optional_text(value: Any) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def _strip_data_url_prefix(value: str) -> str:
    cleaned = (value or "").strip()
    if "," in cleaned and cleaned.lower().startswith("data:"):
        return cleaned.split(",", 1)[1].strip()
    return cleaned
