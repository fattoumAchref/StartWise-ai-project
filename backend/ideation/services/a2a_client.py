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
        # Payload shape is intentionally permissive to work with ADK A2A wrappers.
        return {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "execute",
            "params": {
                "execution_mode": mode,
                "input": {"text": prompt},
                "context": context,
            },
        }

    def _extract_response_text(self, payload: dict) -> str:
        # Handles several common result shapes.
        result = payload.get("result", payload)
        candidates = [
            result.get("output"),
            result.get("text"),
            result.get("message"),
            result.get("content"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, dict):
                nested = (
                    candidate.get("text")
                    or candidate.get("content")
                    or candidate.get("output")
                )
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
        return json.dumps(result, ensure_ascii=True)

    def _extract_stream_text(self, raw_data: str) -> str:
        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            return raw_data
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            for key in ("delta", "text", "output", "content", "message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
                if isinstance(value, dict):
                    nested = value.get("text") or value.get("content")
                    if isinstance(nested, str) and nested.strip():
                        return nested.strip()
        return ""
