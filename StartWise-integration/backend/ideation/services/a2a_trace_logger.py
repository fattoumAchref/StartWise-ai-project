from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


_LOCK = Lock()
_LOG_DIR = Path(__file__).resolve().parents[1] / "output" / "logs"


def write_a2a_trace(
    *,
    session_id: str | None,
    agent_name: str,
    event: str,
    payload: dict[str, Any],
) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe_session_id = (session_id or "unknown-session").strip() or "unknown-session"
    file_path = _LOG_DIR / f"{safe_session_id}.jsonl"
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent_name,
        "event": event,
        "payload": payload,
    }
    with _LOCK:
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, default=str))
            handle.write("\n")
