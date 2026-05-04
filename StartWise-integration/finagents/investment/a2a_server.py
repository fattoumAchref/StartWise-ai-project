"""
agents/investment/a2a_server.py
================================
A2A-compliant HTTP gateway for the Investment Agent.

Exposes the Google/IBM A2A Protocol endpoints so the Finance Agent can
delegate investment analysis via HTTP JSON-RPC instead of the Redis bus:

  GET  /.well-known/agent.json   → Agent Card (discovery)
  POST /                         → JSON-RPC 2.0 (tasks/send, tasks/get, tasks/cancel)
  GET  /health                   → health check

- tasks/send  → publishes financial_analysis to the Redis bus (non-blocking)
              → returns a "working" task immediately
- InvestmentBusAdapter runs in-process (lifespan) and consumes Redis inbox
- tasks/get   → returns current task state (polling-friendly)

Run standalone:
  uvicorn agents.investment.a2a_server:app --port 8002 --reload
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)

# ── Terminal logging setup ────────────────────────────────────────────────────
_root = logging.getLogger()
if not _root.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", "%H:%M:%S"))
    _root.addHandler(_h)
    _root.setLevel(logging.INFO)
for _ns in ("finagents", "a2a_bus"):
    logging.getLogger(_ns).setLevel(logging.DEBUG)

_SEP = "═" * 68


def _inv_emit(label: str, **fields) -> None:
    """Print a clearly visible Investment Agent thought block."""
    print(f"\n{_SEP}", flush=True)
    print(f"[InvestmentAgent]  {label}", flush=True)
    for k, v in fields.items():
        print(f"  {k:<26} {v}", flush=True)
    print(_SEP, flush=True)


# ── In-process task store ──────────────────────────────────────────────────────

_tasks: Dict[str, Dict] = {}   # task_id → task dict


def _new_task(task_id: str, state: str = "submitted") -> Dict:
    return {
        "id": task_id,
        "status": {"state": state},
        "artifacts": [],
        "history": [],
        "metadata": {},
    }


def update_task_state(task_id: str, state: str, artifacts: Optional[list] = None) -> None:
    """
    Update the in-memory task state.
    Called either directly (same process) via the /internal/tasks endpoint,
    or indirectly by the bus adapter (separate process) via HTTP POST.
    """
    task = _tasks.get(task_id)
    if task is None:
        logger.debug("[InvA2AServer] update_task_state: unknown task %s", task_id)
        return
    task["status"]["state"] = state
    if artifacts:
        task["artifacts"] = artifacts
    logger.info("[InvA2AServer] task %s → %s", task_id, state)


# ── Bus publish (HTTP /publish + optional Redis LPUSH fallback) ──────────────
#
# tasks/send LPUSHes via the bus server.  The embedded InvestmentBusAdapter
# (FastAPI lifespan) BRPOPs the same inbox in this process.  Set
# INVESTMENT_EMBED_BUS_ADAPTER=0 if another process already runs the adapter
# (e.g. duplicate Django + standalone 8002 — avoid two BRPOP consumers).

import httpx as _httpx
import redis as _redis

_BUS_URL   = os.getenv("A2A_BUS_URL", "http://localhost:8765")
_REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
_REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))


def _publish_to_bus(msg: dict) -> bool:
    """
    Push a message to the A2A bus.
    Returns True if delivered, False on total failure.
    """
    try:
        r = _httpx.post(
            f"{_BUS_URL}/publish",
            json={"message": msg},
            timeout=5.0,
        )
        r.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("[InvA2AServer] bus HTTP failed, trying Redis direct: %s", exc)

    # Redis fallback
    try:
        r_client = _redis.Redis(
            host=_REDIS_HOST, port=_REDIS_PORT, db=0, decode_responses=True
        )
        for recipient in msg.get("to", []):
            r_client.lpush(f"a2a:{recipient}:inbox", json.dumps(msg, ensure_ascii=False))
        return True
    except Exception as exc:
        logger.error("[InvA2AServer] Redis fallback also failed: %s", exc)
        return False


# ── Agent Card ────────────────────────────────────────────────────────────────

_BASE_URL = os.getenv("INVESTMENT_AGENT_URL", "http://localhost:8002")

_AGENT_CARD = {
    "name":        "StartWise Investment Agent",
    "description": (
        "Autonomous investment analysis agent. Receives structured financial "
        "data from the finance agent, evaluates red flags, runs investment "
        "analysis, and returns a funding recommendation with confidence score."
    ),
    "url":     _BASE_URL + "/",
    "version": "1.0.0",
    "capabilities": {
        "streaming":              True,
        "pushNotifications":      False,
        "stateTransitionHistory": True,
    },
    "skills": [
        {
            "id":          "investment-analysis",
            "name":        "Investment Analysis",
            "description": (
                "Multi-round investment analysis: red-flag detection, "
                "clarification request, funding recommendation with dilution "
                "and valuation estimates."
            ),
            "tags":         ["investment", "funding", "valuation", "startup"],
            "inputModes":  ["application/json"],
            "outputModes": ["application/json"],
        }
    ],
    "defaultInputModes":  ["application/json"],
    "defaultOutputModes": ["application/json"],
    # A2A spec requires authentication field so clients know the security requirements.
    "authentication": {"schemes": [{"type": "none"}]},
}

# ── FastAPI app ───────────────────────────────────────────────────────────────

_embedded_adapter = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _embedded_adapter
    _embedded_adapter = None
    if os.getenv("INVESTMENT_EMBED_BUS_ADAPTER", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        try:
            from finagents.investment.bus_adapter import get_investment_bus_adapter

            _embedded_adapter = get_investment_bus_adapter()
            logger.info(
                "[InvA2AServer] InvestmentBusAdapter embedded (inbox consumer started)",
            )
        except Exception as exc:
            logger.exception(
                "[InvA2AServer] could not start embedded InvestmentBusAdapter: %s",
                exc,
            )
    else:
        logger.info("[InvA2AServer] embedded InvestmentBusAdapter disabled (env)")

    yield

    if _embedded_adapter is not None:
        try:
            _embedded_adapter.stop()
        except Exception as exc:
            logger.debug("[InvA2AServer] adapter stop: %s", exc)
        _embedded_adapter = None


app = FastAPI(
    title="StartWise Investment Agent",
    description="A2A-compliant investment analysis agent",
    version="1.0.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/.well-known/agent.json", tags=["A2A"])
async def agent_card():
    return JSONResponse(content=_AGENT_CARD)


@app.post("/internal/tasks/{task_id}/state/{state}", include_in_schema=False)
async def set_task_state_internal(task_id: str, state: str):
    """
    Internal endpoint called by the bus adapter (run_mocks process) to update
    the task state stored in this server's in-memory task store.

    This bridges the cross-process gap: the bus adapter runs in the run_mocks
    process and cannot directly modify _tasks (a different memory space).
    """
    update_task_state(task_id, state)
    return {"ok": True, "task_id": task_id, "state": state}


@app.get("/health", tags=["ops"])
async def health():
    bus_ok = False
    try:
        r = _httpx.get(f"{_BUS_URL}/health", timeout=2.0)
        bus_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "agent":    "investment",
        "protocol": "A2A/1.0",
        "bus_server": "reachable" if bus_ok else "unreachable",
    }


@app.post("/", tags=["A2A"])
async def jsonrpc(request: Request):
    try:
        body = await request.json()
    except Exception:
        return _err(None, -32700, "Parse error")

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tasks/send":
        return _tasks_send(req_id, params)
    if method == "tasks/get":
        return _tasks_get(req_id, params)
    if method == "tasks/cancel":
        return _tasks_cancel(req_id, params)
    if method == "tasks/sendSubscribe":
        return _tasks_send_subscribe(req_id, params)

    return _err(req_id, -32601, "Method not found")


# ── Method handlers ───────────────────────────────────────────────────────────

def _tasks_send(req_id: Any, params: Dict) -> JSONResponse:
    """
    Receive a financial_analysis task from the finance agent.
    Publishes it to the Redis bus and returns a 'working' task immediately.
    The investment agent processes it asynchronously.
    """
    task_id = params.get("id") or str(uuid.uuid4())
    msg     = params.get("message", {})

    # Extract financial data from the A2A message parts
    financial_data: Dict = {}
    for part in msg.get("parts", []):
        if part.get("type") == "data":
            financial_data = part.get("data", {})
            break
        if part.get("type") == "text":
            # Try to parse JSON from text part
            try:
                financial_data = json.loads(part.get("text", "{}"))
            except Exception:
                pass

    # Build the Redis bus message
    bus_msg = {
        "message_id": str(uuid.uuid4()),
        "type":       "financial_analysis",
        "from":       "finance_agent",
        "to":         ["investment_agent"],
        "context":    {
            "project_id": task_id,
            "session_id": params.get("sessionId", ""),
            "a2a_task_id": task_id,
        },
        "payload": {"data": financial_data},
        "confidence": 0.0,
        "metadata":   {"a2a_task_id": task_id},
    }

    # Store task: submitted → working (per A2A spec lifecycle)
    task = _new_task(task_id, "submitted")
    _tasks[task_id] = task
    task["status"]["state"] = "working"

    kpis = financial_data.get("kpis") or {}
    recipients = bus_msg.get("to", [])
    _inv_emit(
        "TASK RECEIVED — forwarding to bus",
        task_id=task_id,
        msg_type=bus_msg.get("type", "?"),
        from_agent=bus_msg.get("from", "?"),
        recipients=recipients,
        kpis_keys=list(kpis.keys())[:6] if kpis else "—",
    )

    # Publish to the investment agent via the bus server (non-blocking)
    delivered = _publish_to_bus(bus_msg)
    if delivered:
        _inv_emit("→ BUS PUBLISH OK", task_id=task_id, bus_url=_BUS_URL)
        logger.info("[InvA2AServer] task %s → bus (financial_analysis)", task_id)
    else:
        _inv_emit("✗ BUS PUBLISH FAILED", task_id=task_id, bus_url=_BUS_URL)
        logger.error("[InvA2AServer] could not deliver task %s to bus", task_id)
        task["status"]["state"] = "failed"

    return _ok(req_id, task)


def _tasks_get(req_id: Any, params: Dict) -> JSONResponse:
    task_id = params.get("id")
    if not task_id:
        return _err(req_id, -32602, "Missing id")
    task = _tasks.get(task_id)
    if not task:
        return _err(req_id, -32001, "Task not found")
    return _ok(req_id, task)


def _tasks_cancel(req_id: Any, params: Dict) -> JSONResponse:
    task_id = params.get("id")
    if not task_id:
        return _err(req_id, -32602, "Missing id")
    task = _tasks.get(task_id)
    if not task:
        return _err(req_id, -32001, "Task not found")
    if task["status"]["state"] in ("completed", "failed", "canceled"):
        return _err(req_id, -32002, "Task not cancelable")
    task["status"]["state"] = "canceled"
    return _ok(req_id, task)


# ── Method: tasks/sendSubscribe ───────────────────────────────────────────────

def _tasks_send_subscribe(req_id: Any, params: Dict):
    """
    tasks/sendSubscribe

    Same as tasks/send but streams each state transition as an SSE event:
      submitted → working → [polling] → completed | failed

    Each SSE event is a JSON-RPC 2.0 result object.
    The final event carries "final": true.

    Because the investment agent processes via the Redis bus asynchronously,
    this method publishes the task and then polls the in-memory task store
    until the bus adapter updates the state to a terminal value.
    """
    task_id = params.get("id") or str(uuid.uuid4())
    msg     = params.get("message", {})

    financial_data: Dict = {}
    for part in msg.get("parts", []):
        if part.get("type") == "data":
            financial_data = part.get("data", {})
            break
        if part.get("type") == "text":
            try:
                financial_data = json.loads(part.get("text", "{}"))
            except Exception:
                pass

    bus_msg = {
        "message_id": str(uuid.uuid4()),
        "type":       "financial_analysis",
        "from":       "finance_agent",
        "to":         ["investment_agent"],
        "context":    {
            "project_id":  task_id,
            "session_id":  params.get("sessionId", ""),
            "a2a_task_id": task_id,
        },
        "payload":    {"data": financial_data},
        "confidence": 0.0,
        "metadata":   {"a2a_task_id": task_id},
    }

    task = _new_task(task_id, "submitted")
    _tasks[task_id] = task

    async def stream():
        yield _sse(req_id, {"id": task_id, "status": {"state": "submitted"}})

        task["status"]["state"] = "working"
        yield _sse(req_id, {"id": task_id, "status": {"state": "working"}})

        delivered = _publish_to_bus(bus_msg)
        if not delivered:
            logger.error("[InvA2AServer] SSE bus publish failed for task %s", task_id)
            task["status"]["state"] = "failed"
            yield _sse(req_id, {"id": task_id, "status": {"state": "failed"}, "final": True})
            return

        # Poll until the bus adapter updates task state to a terminal value
        poll_interval = 1.0   # seconds between checks
        max_wait      = 120.0 # 2-minute timeout
        elapsed       = 0.0
        terminal      = {"completed", "failed", "canceled"}

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            state = _tasks.get(task_id, {}).get("status", {}).get("state", "working")
            if state in terminal:
                break

        final_task = _tasks.get(task_id, task)
        yield _sse(req_id, {
            "id":      task_id,
            "status":  final_task.get("status", {"state": "failed"}),
            "final":   True,
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


def _sse(req_id: Any, data: Dict) -> str:
    """Encode one SSE event as a JSON-RPC 2.0 result."""
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": req_id, "result": data},
        ensure_ascii=False,
    )
    return f"data: {payload}\n\n"


# ── Utility functions ─────────────────────────────────────────────────────────

def _ok(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, code: int, message: str) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id":      req_id,
        "error":   {"code": code, "message": message},
    })
