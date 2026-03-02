import json
import uuid
from dataclasses import dataclass
from typing import Iterator

import httpx


@dataclass
class A2AClient:
    """
    Lightweight JSON-RPC + SSE client for ADK A2A-compatible agent endpoints.
    """

    endpoint: str
    timeout_seconds: float = 60.0

    def call_sync(self, prompt: str, context: dict | None = None) -> str:
        payload = self._build_rpc_payload(prompt=prompt, mode="sync", context=context or {})
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, json=payload)
        response.raise_for_status()
        return self._extract_response_text(response.json())

    def stream(self, prompt: str, context: dict | None = None) -> Iterator[str]:
        payload = self._build_rpc_payload(prompt=prompt, mode="sse", context=context or {})
        headers = {"Accept": "text/event-stream"}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            with client.stream("POST", self.endpoint, json=payload, headers=headers) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw_data = line[5:].strip()
                    if not raw_data or raw_data == "[DONE]":
                        continue
                    text = self._extract_stream_text(raw_data)
                    if text:
                        yield text

    def _build_rpc_payload(self, prompt: str, mode: str, context: dict) -> dict:
        request_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        context_id = str(
            context.get("session_id")
            or context.get("context_id")
            or request_id
        )
        method = "message/stream" if mode == "sse" else "message/send"

        params: dict = {
            "message": {
                "kind": "message",
                "messageId": message_id,
                "role": "user",
                "contextId": context_id,
                "parts": [{"kind": "text", "text": prompt}],
            },
            "configuration": {
                "acceptedOutputModes": ["text"],
                "blocking": mode != "sse",
            },
        }
        if context:
            params["metadata"] = context

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

    def _extract_response_text(self, payload: dict) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message", "Unknown A2A JSON-RPC error")
            code = error.get("code")
            self._raise_if_quota_or_rate_limit(str(message))
            raise RuntimeError(f"A2A error code={code}: {message}")

        result = payload.get("result", payload)
        texts = self._extract_text_parts(result)
        if texts:
            joined = "\n".join(texts)
            self._raise_if_quota_or_rate_limit(joined)
            return joined
        return json.dumps(result, ensure_ascii=True)

    def _extract_stream_text(self, raw_data: str) -> str:
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            return raw_data
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            if isinstance(payload.get("error"), dict):
                return ""
            result = payload.get("result", payload)
            texts = self._extract_text_parts(result)
            if texts:
                joined = "\n".join(texts)
                self._raise_if_quota_or_rate_limit(joined)
                return joined
        return ""

    def _extract_text_parts(self, value: object) -> list[str]:
        texts: list[str] = []

        def walk(node: object) -> None:
            if isinstance(node, str):
                cleaned = node.strip()
                if cleaned:
                    texts.append(cleaned)
                return

            if isinstance(node, list):
                for item in node:
                    walk(item)
                return

            if not isinstance(node, dict):
                return

            if node.get("kind") == "text":
                text_value = node.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    texts.append(text_value.strip())
                return

            direct_text = node.get("text")
            if isinstance(direct_text, str) and direct_text.strip():
                texts.append(direct_text.strip())

            for key in (
                "parts",
                "message",
                "status",
                "artifact",
                "artifacts",
                "result",
                "content",
                "output",
                "delta",
                "data",
            ):
                if key in node:
                    walk(node[key])

        walk(value)

        deduped: list[str] = []
        for text in texts:
            if text not in deduped:
                deduped.append(text)
        return deduped

    def _raise_if_quota_or_rate_limit(self, text: str) -> None:
        lower = text.lower()
        markers = (
            "resource_exhausted",
            "quota exceeded",
            "rate-limits",
            "rate limit",
            "error code 429",
            "429 resource_exhausted",
            "generativelanguage.googleapis.com",
        )
        if any(marker in lower for marker in markers):
            raise RuntimeError("Gemini quota/rate limit reached")
