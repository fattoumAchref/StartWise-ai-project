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

# Try to connect to Redis, fallback to in-memory dict if unavailable
_REDIS_AVAILABLE = False
_MEMORY_STORE: Dict[str, bytes] = {}

try:
    _r = _redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=0,
        decode_responses=False,
        socket_connect_timeout=2,
    )
    # Test connection
    _r.ping()
    _REDIS_AVAILABLE = True
    logger.info("[session] Redis connected successfully")
except Exception as e:
    logger.warning("[session] Redis unavailable (%s), using in-memory fallback", e)
    _r = None

_SESSION_TTL = 86400  # 24 h

# ── Singletons ─────────────────────────────────────────────────────────────

_COMM_AGENT = None
_FINANCE_AGENT = None
_A2A_CLASSES: dict = {}
_INVESTMENT_ADAPTER = None


def startup_singletons() -> None:
    global _COMM_AGENT, _FINANCE_AGENT, _A2A_CLASSES, _INVESTMENT_ADAPTER
    try:
        from finagents.finance.bus_publisher import get_finance_bus_publisher
        _COMM_AGENT = get_finance_bus_publisher()
        logger.info("[Django] FinanceCommAgent started")
    except Exception as e:
        logger.warning("[Django] FinanceCommAgent unavailable: %s", e)

    try:
        from finagents.finance.agent import FinanceAgent
        from finagents.finance.protocol_models import Task, TaskStatus, Message, TextPart
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

    try:
        from finagents.investment.bus_adapter import get_investment_bus_adapter
        _INVESTMENT_ADAPTER = get_investment_bus_adapter()
        logger.info("[Django] InvestmentBusAdapter started")
    except Exception as e:
        logger.warning("[Django] InvestmentBusAdapter unavailable: %s", e)


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
        "asked_questions": [],  # questions already sent to user — never repeat
    }


def get_state(session_id: str) -> Dict[str, Any]:
    if _REDIS_AVAILABLE:
        raw = _r.get(_key(session_id))
    else:
        raw = _MEMORY_STORE.get(_key(session_id))
    
    if raw:
        try:
            return pickle.loads(raw)
        except Exception as exc:
            # Pickle fails when dataclass schemas change between deployments.
            # Log clearly so it's diagnosable — callers receive a fresh default state.
            logger.warning(
                "[session] pickle restore failed for %s — schema may have changed. "
                "Starting fresh session. Error: %s",
                session_id, exc,
            )
    return _default_state()


def save_state(session_id: str, state: Dict[str, Any]) -> None:
    data = pickle.dumps(state)
    if _REDIS_AVAILABLE:
        _r.setex(_key(session_id), _SESSION_TTL, data)
    else:
        _MEMORY_STORE[_key(session_id)] = data


def delete_state(session_id: str) -> None:
    if _REDIS_AVAILABLE:
        _r.delete(_key(session_id))
    else:
        _MEMORY_STORE.pop(_key(session_id), None)
