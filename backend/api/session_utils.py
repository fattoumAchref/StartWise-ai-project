"""
api/session_utils.py
====================
Redis-backed session state (pickle) + Django singletons.

Why pickle?  Python dataclasses (FinancialContext, KPIResult …) cannot be
serialised to JSON without information loss.  Pickle round-trips them perfectly.
"""
from __future__ import annotations

import logging
import os
import pickle
from typing import Any, Dict

import redis as _redis

logger = logging.getLogger(__name__)

_r = _redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=False,
)
_SESSION_TTL = 86400  # 24 h

# ── Singletons ─────────────────────────────────────────────────────────────

_COMM_AGENT = None
_FINANCE_AGENT = None
_A2A_CLASSES: dict = {}


def startup_singletons() -> None:
    global _COMM_AGENT, _FINANCE_AGENT, _A2A_CLASSES
    try:
        from agents.finance.comm_agent import get_finance_comm_agent
        _COMM_AGENT = get_finance_comm_agent()
        logger.info("[Django] FinanceCommAgent started")
    except Exception as e:
        logger.warning("[Django] FinanceCommAgent unavailable: %s", e)

    try:
        from agents.finance.agent import FinanceAgent
        from agents.finance.a2a_models import Task, TaskStatus, Message, TextPart
        _FINANCE_AGENT = FinanceAgent()
        _A2A_CLASSES = {
            "Task": Task,
            "TaskStatus": TaskStatus,
            "Message": Message,
            "TextPart": TextPart,
        }
        logger.info("[Django] FinanceAgent started")
    except Exception as e:
        logger.warning("[Django] FinanceAgent unavailable: %s", e)


def get_comm_agent():
    return _COMM_AGENT


def get_finance_agent():
    return _FINANCE_AGENT


def get_a2a_classes() -> dict:
    return _A2A_CLASSES


# ── Session helpers ─────────────────────────────────────────────────────────

def _key(session_id: str) -> str:
    return f"django:app_state:{session_id}"


def _default_state() -> Dict[str, Any]:
    return {
        "messages": [],
        "financial_context": None,
        "analysis": {},
        "validation_result": None,
        "last_bench": None,
        "last_bench_extra": {},
        "pending_bench": None,
        "shown_sections": set(),
        "whatif_mode": False,
        "conversations": [],
        "agent_task": None,
        "agent_clarification_rounds": 0,
        "_agent_task_id": None,
        "_agent_fresh": False,
        "a2a_publish_time": None,
        "awaiting_clarification": False,
    }


def get_state(session_id: str) -> Dict[str, Any]:
    raw = _r.get(_key(session_id))
    if raw:
        try:
            return pickle.loads(raw)
        except Exception:
            pass
    return _default_state()


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    _r.setex(_key(session_id), _SESSION_TTL, pickle.dumps(state))


def delete_state(session_id: str) -> None:
    _r.delete(_key(session_id))
