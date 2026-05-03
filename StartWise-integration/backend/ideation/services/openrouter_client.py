from __future__ import annotations

import json
import logging
from typing import Iterator

import httpx

logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 90.0,
        temperature: float = 0.25,
        top_p: float = 0.95,
        max_tokens: int | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call_sync(self, prompt: str, context: dict | None = None) -> str:
        payload = self._build_payload(prompt=prompt, stream=False, context=context)
        try:
            timeout = httpx.Timeout(self.timeout_seconds)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(self.endpoint, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                f"OpenRouter request timed out after {self.timeout_seconds}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:400]
            logger.error(
                "OpenRouter returned HTTP %s: %s",
                exc.response.status_code,
                body,
            )
            raise RuntimeError("OpenRouter request failed") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("OpenRouter request failed") from exc

        return self._parse_response(data)

    def stream(self, prompt: str, context: dict | None = None) -> Iterator[str]:
        payload = self._build_payload(prompt=prompt, stream=True, context=context)
        timeout = httpx.Timeout(self.timeout_seconds)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", self.endpoint, headers=self._headers(), json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    raw = line.strip()
                    if not raw:
                        continue
                    if raw == "[DONE]":
                        break
                    if raw.startswith("data:"):
                        encoded = raw[5:].strip()
                        if not encoded:
                            continue
                        try:
                            chunk = json.loads(encoded)
                        except json.JSONDecodeError:
                            continue
                        text = self._extract_stream_text(chunk)
                        if text:
                            yield text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://startwise.ai",
            "X-Title": "Startwise",
        }

    def _build_payload(
        self, prompt: str, stream: bool, context: dict | None
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        if context:
            payload["metadata"] = context
        return payload

    def _parse_response(self, payload: dict) -> str:
        data = self._extract_choice_content(payload)
        if data:
            return data
        return ""

    def _extract_stream_text(self, payload: dict) -> str:
        if error := payload.get("error"):
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"OpenRouter error: {message}")
        return self._extract_choice_content(payload)

    def _extract_choice_content(self, payload: dict) -> str:
        choices = payload.get("choices") or []
        for choice in choices:
            if delta := choice.get("delta"):
                text = delta.get("content")
                if isinstance(text, str) and text.strip():
                    return text
            message = choice.get("message")
            if isinstance(message, dict):
                text = message.get("content")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return ""
