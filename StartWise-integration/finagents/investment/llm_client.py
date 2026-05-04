"""
OpenAI-compatible chat completions over HTTP — avoids langchain_* dependencies.
"""

from __future__ import annotations

import logging
from typing import Any, List

import httpx

from finagents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)


def chat_completion(
    messages: List[dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 400,
    timeout: float = 60.0,
) -> str:
    """POST /chat/completions; returns assistant text or empty string on failure."""
    url = BASE_URL.rstrip("/") + "/chat/completions"
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {TOKENFACTORY_API_KEY}"},
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
            verify=False,
        )
        r.raise_for_status()
        data = r.json()
        choices = data.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        return (msg.get("content") or "").strip()
    except Exception as exc:
        logger.warning("[investment.llm_client] chat failed: %s", exc)
        return ""
