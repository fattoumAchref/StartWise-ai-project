from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Iterator

import httpx

from .a2a_trace_logger import write_a2a_trace


class A2AStreamingUnsupportedError(RuntimeError):
    """Raised when a remote A2A agent does not support streaming requests."""


@dataclass
class A2AClient:
    agent_name: str
    endpoint: str
    timeout_seconds: float = 90.0
    streaming_enabled: bool = False
    _streaming_supported: bool = True

    def call_sync(self, prompt: str, context: dict | None = None) -> str:
        payload = self._build_rpc_payload(prompt=prompt, context=context, streaming=False)
        self._write_trace("request_sync", {"request": payload}, context=context)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.endpoint, json=payload)
            response.raise_for_status()
            response_payload = response.json()
        parsed = self._extract_response_text(response_payload)
        self._write_trace(
            "response_sync",
            {
                "response": response_payload,
                "parsed_text": parsed,
            },
            context=context,
        )
        return parsed

    def stream(self, prompt: str, context: dict | None = None) -> Iterator[str]:
        if not self.streaming_enabled or not self._streaming_supported:
            text = self.call_sync(prompt, context=context)
            if text:
                yield text
            return

        payload = self._build_rpc_payload(prompt=prompt, context=context, streaming=True)
        headers = {"Accept": "text/event-stream"}
        self._write_trace("request_stream", {"request": payload}, context=context)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                with client.stream(
                    "POST",
                    self.endpoint,
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        raw = line.strip()
                        if not raw:
                            continue
                        if raw == "[DONE]":
                            break
                        if raw.startswith("data:"):
                            chunk = raw[5:].strip()
                            if not chunk:
                                continue
                            text = self._extract_stream_text(chunk)
                            if text:
                                self._write_trace(
                                    "response_stream_chunk",
                                    {"chunk": chunk, "parsed_text": text},
                                    context=context,
                                )
                                yield text
        except A2AStreamingUnsupportedError:
            self._streaming_supported = False
            text = self.call_sync(prompt, context=context)
            if text:
                yield text

    def _build_rpc_payload(
        self, prompt: str, context: dict | None, streaming: bool
    ) -> dict:
        metadata = dict(context or {})
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/stream" if streaming else "message/send",
            "params": {
                "message": {
                    "messageId": str(uuid.uuid4()),
                    "role": "user",
                    "parts": [{"kind": "text", "text": prompt}],
                }
            },
        }
        if metadata:
            payload["params"]["metadata"] = metadata
        return payload

    def _extract_response_text(self, payload: dict) -> str:
        if error := payload.get("error"):
            message = error.get("message") if isinstance(error, dict) else str(error)
            self._raise_if_quota_or_rate_limit(message)
            code = error.get("code") if isinstance(error, dict) else None
            if code is not None:
                raise RuntimeError(f"A2A error code={code}: {message}")
            raise RuntimeError(message or "Unknown A2A JSON-RPC error")

        result = payload.get("result") or {}
        final_agent_text = self._extract_final_agent_text(result)
        if final_agent_text:
            return final_agent_text
        parts = self._extract_text_parts(result)
        if parts:
            return "\n".join(parts)
        return json.dumps(result)

    def _extract_stream_text(self, payload: str) -> str:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return ""

        if error := data.get("error"):
            message = error.get("message") if isinstance(error, dict) else str(error)
            if self._is_streaming_unsupported(message):
                raise A2AStreamingUnsupportedError(message)
            self._raise_if_quota_or_rate_limit(message)
            raise RuntimeError(message)

        result = data.get("result") or {}
        final_agent_text = self._extract_final_agent_text(result)
        if final_agent_text:
            return final_agent_text
        parts = self._extract_text_parts(result)
        if parts:
            return "\n".join(parts)
        return ""

    def _extract_text_parts(self, node: object) -> list[str]:
        results: list[str] = []
        if isinstance(node, str):
            stripped = node.strip()
            if stripped:
                results.append(stripped)
            return results
        if isinstance(node, dict):
            text_value = node.get("text")
            if isinstance(text_value, str) and text_value.strip():
                results.append(text_value.strip())
            for key, value in node.items():
                if key == "text":
                    continue
                results.extend(self._extract_text_parts(value))
            return results
        if isinstance(node, list):
            for item in node:
                results.extend(self._extract_text_parts(item))
        return results

    def _raise_if_quota_or_rate_limit(self, message: str | None) -> None:
        lowered = (message or "").lower()
        markers = ("rate limit", "quota", "resource_exhausted", "too many requests")
        if any(marker in lowered for marker in markers):
            raise RuntimeError("Model provider quota/rate limit reached")

    def _is_streaming_unsupported(self, message: str | None) -> bool:
        lowered = (message or "").lower()
        markers = (
            "streaming is not supported by the agent",
            "unsupported operation: streaming is not supported by the agent",
        )
        return any(marker in lowered for marker in markers)

    def _extract_final_agent_text(self, node: object) -> str:
        candidates: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                role = str(value.get("role") or "").strip().lower()
                parts_text = self._extract_parts_text(value.get("parts"))
                if role == "agent" and parts_text:
                    candidates.append(parts_text)

                message = value.get("message")
                if isinstance(message, dict):
                    message_role = str(message.get("role") or "").strip().lower()
                    message_text = self._extract_parts_text(message.get("parts"))
                    if message_role == "agent" and message_text:
                        candidates.append(message_text)

                for child in value.values():
                    walk(child)
                return

            if isinstance(value, list):
                for item in value:
                    walk(item)

        walk(node)
        for candidate in reversed(candidates):
            cleaned = candidate.strip()
            if cleaned:
                return cleaned
        return ""

    def _extract_parts_text(self, parts: object) -> str:
        collected: list[str] = []
        if not isinstance(parts, list):
            return ""
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                collected.append(text.strip())
        return "\n".join(collected).strip()

    def _write_trace(
        self,
        event: str,
        payload: dict,
        context: dict | None = None,
    ) -> None:
        session_id = None
        if context and isinstance(context, dict):
            session_id = str(context.get("session_id") or "").strip() or None
        write_a2a_trace(
            session_id=session_id,
            agent_name=self.agent_name,
            event=event,
            payload=payload,
        )
