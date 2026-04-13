from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any

import httpx

from .schemas import AuditAttachment


logger = logging.getLogger(__name__)


TEXT_MIME_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/typescript",
    "text/csv",
    "text/html",
    "text/markdown",
    "text/plain",
    "text/xml",
}


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        self.upload_base_url = os.getenv(
            "GEMINI_UPLOAD_BASE_URL",
            "https://generativelanguage.googleapis.com",
        ).rstrip("/")
        self.generation_model = os.getenv(
            "PRODUCT_AUDIT_GEMINI_MODEL",
            "gemini-2.5-flash-lite",
        ).strip()
        self.embedding_model = os.getenv(
            "GEMINI_EMBEDDING_MODEL",
            "gemini-embedding-001",
        ).strip()
        self.output_dimensionality = _optional_int(
            os.getenv("GEMINI_EMBEDDING_DIMENSION")
        )
        self.timeout_seconds = float(os.getenv("PRODUCT_AUDIT_TIMEOUT_SECONDS", "90"))
        self.file_poll_seconds = float(os.getenv("GEMINI_FILE_POLL_SECONDS", "2"))
        self.file_poll_attempts = int(os.getenv("GEMINI_FILE_POLL_ATTEMPTS", "20"))

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_report(
        self,
        prompt: str,
        attachments: list[AuditAttachment] | None = None,
    ) -> str:
        self._assert_configured()
        parts: list[dict[str, Any]] = [{"text": prompt}]
        for item in attachments or []:
            if item.extracted_text:
                parts.append(
                    {
                        "text": (
                            f"Extracted attachment context ({item.name}):\n"
                            f"{item.extracted_text[:12000]}"
                        )
                    }
                )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "temperature": 0.25,
            },
        }

        data = self._post(
            f"/models/{self.generation_model}:generateContent",
            json=payload,
        )
        text = self._extract_generated_text(data)
        if not text:
            raise RuntimeError("Gemini returned an empty report")
        return text.strip()

    def extract_attachment_text(
        self,
        attachment: AuditAttachment,
        startup_context: str = "",
    ) -> str:
        if attachment.extracted_text:
            return attachment.extracted_text

        if attachment.text:
            return attachment.text

        if attachment.base64_data and self._is_text_mime(attachment.content_type):
            decoded = self._decode_bytes(attachment.base64_data).decode("utf-8", errors="ignore").strip()
            if decoded:
                return decoded

        if not attachment.base64_data:
            return attachment.summary_text or ""

        prompt = self._attachment_extraction_prompt(attachment, startup_context)
        media_part = self._build_media_part(attachment)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}, media_part],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            },
        }

        data = self._post(
            f"/models/{self.generation_model}:generateContent",
            json=payload,
        )
        text = self._extract_generated_text(data)
        return text.strip()

    def embed_texts(
        self,
        texts: list[str],
        titles: list[str] | None = None,
    ) -> list[list[float]]:
        cleaned = [text.strip() for text in texts if text and text.strip()]
        if not cleaned:
            return []
        self._assert_configured()

        vectors: list[list[float]] = []
        for index, text in enumerate(cleaned):
            body: dict[str, Any] = {
                "content": {"parts": [{"text": text[:20000]}]},
                "taskType": "RETRIEVAL_DOCUMENT",
            }
            title = titles[index].strip() if titles and index < len(titles) and titles[index] else ""
            if title:
                body["title"] = title[:512]
            if self.output_dimensionality:
                body["outputDimensionality"] = self.output_dimensionality

            data = self._post(
                f"/models/{self.embedding_model}:embedContent",
                json=body,
            )
            vector = self._extract_single_embedding(data)
            if vector:
                vectors.append(vector)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        cleaned = (text or "").strip()
        if not cleaned:
            return []
        self._assert_configured()
        body: dict[str, Any] = {
            "content": {"parts": [{"text": cleaned[:20000]}]},
            "taskType": "RETRIEVAL_QUERY",
        }
        if self.output_dimensionality:
            body["outputDimensionality"] = self.output_dimensionality

        data = self._post(
            f"/models/{self.embedding_model}:embedContent",
            json=body,
        )
        return self._extract_single_embedding(data)

    def _build_media_part(self, attachment: AuditAttachment) -> dict[str, Any]:
        mime_type = (attachment.content_type or "application/octet-stream").strip()
        payload = attachment.base64_data or ""
        if not payload:
            raise RuntimeError("Attachment has no binary payload")

        data_bytes = self._decode_bytes(payload)
        if self._should_use_file_api(mime_type, len(data_bytes)):
            uploaded = self._upload_file(
                display_name=attachment.name,
                mime_type=mime_type,
                data_bytes=data_bytes,
            )
            return {
                "file_data": {
                    "mime_type": mime_type,
                    "file_uri": uploaded["uri"],
                }
            }

        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": self._strip_data_url_prefix(payload),
            }
        }

    def _upload_file(
        self,
        display_name: str,
        mime_type: str,
        data_bytes: bytes,
    ) -> dict[str, str]:
        start_url = f"{self.upload_base_url}/upload/v1beta/files"
        headers = {
            **self._auth_headers(),
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(data_bytes)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = client.post(
                    start_url,
                    headers=headers,
                    json={"file": {"display_name": display_name[:128]}},
                )
                response.raise_for_status()
                upload_url = response.headers.get("x-goog-upload-url")
                if not upload_url:
                    raise RuntimeError("Gemini upload did not return an upload URL")

                upload_response = client.post(
                    upload_url,
                    headers={
                        "Content-Length": str(len(data_bytes)),
                        "X-Goog-Upload-Offset": "0",
                        "X-Goog-Upload-Command": "upload, finalize",
                    },
                    content=data_bytes,
                )
                upload_response.raise_for_status()
                payload = upload_response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini file upload timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(
                f"Gemini file upload failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini file upload failed") from exc

        file_info = payload.get("file") or {}
        file_name = str(file_info.get("name") or "").strip()
        file_uri = str(file_info.get("uri") or "").strip()
        if not file_name or not file_uri:
            raise RuntimeError("Gemini file upload returned incomplete metadata")

        return self._wait_for_file(file_name=file_name, fallback_uri=file_uri)

    def _wait_for_file(self, file_name: str, fallback_uri: str) -> dict[str, str]:
        file_info = {"name": file_name, "uri": fallback_uri}
        for _ in range(max(1, self.file_poll_attempts)):
            payload = self._get(f"/files/{file_name}")
            file_resource = payload.get("file") if isinstance(payload, dict) else None
            if isinstance(file_resource, dict):
                file_info["name"] = str(file_resource.get("name") or file_name)
                file_info["uri"] = str(file_resource.get("uri") or fallback_uri)
                state = str(file_resource.get("state") or "").upper()
                if state in {"ACTIVE", "SUCCEEDED", "READY", ""}:
                    return file_info
                if state in {"FAILED", "ERROR"}:
                    raise RuntimeError("Gemini file processing failed")
            time.sleep(self.file_poll_seconds)
        return file_info

    def _post(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = client.post(
                    url,
                    headers=self._json_headers(),
                    json=json,
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini request timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(
                f"Gemini request failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini request failed") from exc

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = client.get(url, headers=self._auth_headers())
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"Gemini request timed out after {self.timeout_seconds}s") from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(
                f"Gemini request failed with HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Gemini request failed") from exc

    def _extract_generated_text(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    return text
        return ""

    def _extract_single_embedding(self, payload: dict[str, Any]) -> list[float]:
        for key in ("embedding", "result"):
            vector = self._coerce_embedding(payload.get(key))
            if vector:
                return vector
        return self._coerce_embedding(payload)

    def _coerce_embedding(self, payload: Any) -> list[float]:
        if isinstance(payload, dict):
            values = payload.get("values")
            if isinstance(values, list):
                return [float(item) for item in values]
            nested = payload.get("embedding")
            if nested is not None:
                return self._coerce_embedding(nested)
        return []

    def _attachment_extraction_prompt(
        self,
        attachment: AuditAttachment,
        startup_context: str,
    ) -> str:
        return (
            "You are extracting retrieval-ready product knowledge from an uploaded startup artifact.\n"
            "The output will be embedded and stored in a vector database for later product audits.\n"
            "Be concrete and factual. Preserve visible wording when possible.\n"
            "Do not invent missing details.\n\n"
            "Return markdown with these sections:\n"
            "## Artifact Summary\n"
            "## Visible Text\n"
            "## Product Claims\n"
            "## UX or UI Signals\n"
            "## Trust Signals\n"
            "## Pricing or CTA Details\n"
            "## Risks or Gaps\n"
            "## Retrieval Summary\n\n"
            f"Startup context:\n{startup_context or 'Not provided'}\n\n"
            f"Attachment name: {attachment.name}\n"
            f"Attachment MIME type: {attachment.content_type}\n"
        )

    def _is_text_mime(self, mime_type: str) -> bool:
        cleaned = (mime_type or "").strip().lower()
        return cleaned.startswith("text/") or cleaned in TEXT_MIME_TYPES

    def _should_use_file_api(self, mime_type: str, num_bytes: int) -> bool:
        cleaned = (mime_type or "").strip().lower()
        return cleaned == "application/pdf" or num_bytes > 4_000_000

    def _decode_bytes(self, payload: str) -> bytes:
        try:
            return base64.b64decode(self._strip_data_url_prefix(payload), validate=False)
        except Exception as exc:
            raise RuntimeError("Failed to decode attachment base64 payload") from exc

    def _strip_data_url_prefix(self, value: str) -> str:
        cleaned = (value or "").strip()
        if "," in cleaned and cleaned.lower().startswith("data:"):
            return cleaned.split(",", 1)[1].strip()
        return cleaned

    def _json_headers(self) -> dict[str, str]:
        return {
            **self._auth_headers(),
            "Content-Type": "application/json",
        }

    def _auth_headers(self) -> dict[str, str]:
        self._assert_configured()
        return {"x-goog-api-key": self.api_key}

    def _assert_configured(self) -> None:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")


def _optional_int(value: str | None) -> int | None:
    try:
        cleaned = str(value or "").strip()
        return int(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None
