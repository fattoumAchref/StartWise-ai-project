"""
agents/finance/a2a_server.py
============================
True A2A-compliant HTTP server for the Finance Agent.

Implements the Google/IBM A2A Protocol specification:

  GET  /.well-known/agent.json   → Agent Card  (discovery endpoint)
  POST /                         → JSON-RPC 2.0 dispatcher

Supported JSON-RPC methods:
  tasks/send           Create a new task, or continue an 'input-required' one
  tasks/get            Retrieve task status, history, and artifacts
  tasks/cancel         Cancel a running or pending task
  tasks/sendSubscribe  Send task + stream state transitions via SSE

Run standalone:
  uvicorn agents.finance.a2a_server:app --port 8001 --reload

Any A2A-compatible agent or orchestrator can discover and call this agent
by fetching its Agent Card, then using the JSON-RPC endpoint above.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agents.finance.a2a_models import (
    A2A_TASK_NOT_CANCELABLE,
    A2A_TASK_NOT_FOUND,
    JSONRPC_INTERNAL_ERROR,
    JSONRPC_INVALID_PARAMS,
    JSONRPC_METHOD_NOT_FOUND,
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    DataPart,
    JSONRPCError,
    Message,
    Task,
    TaskStatus,
    TextPart,
    part_from_dict,
)
from agents.finance.agent import FinanceAgent

logger = logging.getLogger(__name__)

# ── Agent Card ────────────────────────────────────────────────────────────────
# Published at GET /.well-known/agent.json — any A2A client uses this for
# discovery: who is this agent, what can it do, how to talk to it.

_BASE_URL = os.getenv("FINANCE_AGENT_URL", "http://localhost:8001")

_AGENT_CARD = AgentCard(
    name="StartWise Finance Agent",
    description=(
        "Autonomous financial analysis agent for early-stage startups. "
        "Parses founder input (text or PDF), validates data quality, calculates "
        "KPIs and runway, runs Monte Carlo survival simulations, compares against "
        "sector benchmarks, and delegates investment analysis to the investment "
        "agent via the A2A protocol."
    ),
    url=_BASE_URL + "/",
    version="2.0.0",
    capabilities=AgentCapabilities(
        streaming=True,
        pushNotifications=False,
        stateTransitionHistory=True,
    ),
    skills=[
        AgentSkill(
            id="financial-analysis",
            name="Startup Financial Analysis",
            description=(
                "Full financial analysis: burn rate, runway, LTV/CAC, gross margin, "
                "Monte Carlo 12-month survival probability, pessimiste/réaliste/optimiste "
                "scenario projections, sector benchmark comparison, and investment "
                "recommendation delegation to the investment agent."
            ),
            tags=["finance", "startup", "kpi", "monte-carlo", "benchmarks", "runway"],
            examples=[
                "Mon burn rate est 15 000 TND/mois, j'ai 90 000 TND en caisse et 8 000 TND de MRR.",
                "SaaS startup, ARR 500k TND, churn 5%, je cherche à lever une seed round.",
                "Fintech B2B, revenu 12 000 TND/mois, dépenses 25 000 TND, 3 mois de runway.",
            ],
            inputModes=["text/plain", "application/pdf"],
            outputModes=["application/json", "text/plain"],
        ),
    ],
    defaultInputModes=["text/plain"],
    defaultOutputModes=["application/json"],
).to_dict()


# ── Task Store ────────────────────────────────────────────────────────────────

class _TaskStore:
    """
    Thread-safe task store.
    Primary storage: in-memory dict (fast, always available).
    Secondary storage: Redis (optional — enables task lookup across processes).
    """

    _TTL = 3600  # seconds

    def __init__(self) -> None:
        self._mem: Dict[str, Task] = {}
        self._redis: Optional[redis.Redis] = None
        try:
            r = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
                decode_responses=True,
            )
            r.ping()
            self._redis = r
            logger.info("[TaskStore] Redis connected")
        except Exception:
            logger.warning("[TaskStore] Redis unavailable — in-memory only")

    def save(self, task: Task) -> None:
        self._mem[task.id] = task
        if self._redis:
            try:
                self._redis.setex(
                    f"a2a:finance:task:{task.id}",
                    self._TTL,
                    json.dumps(task.to_dict(), ensure_ascii=False),
                )
            except Exception as exc:
                logger.debug("[TaskStore] Redis save failed (non-fatal): %s", exc)

    def get(self, task_id: str) -> Optional[Task]:
        return self._mem.get(task_id)

    def delete(self, task_id: str) -> None:
        self._mem.pop(task_id, None)
        if self._redis:
            try:
                self._redis.delete(f"a2a:finance:task:{task_id}")
            except Exception:
                pass


# ── Singletons ────────────────────────────────────────────────────────────────

_store = _TaskStore()
_agent = FinanceAgent()

# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="StartWise Finance Agent",
    description="A2A-compliant autonomous finance agent — Google/IBM A2A Protocol",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Agent Card discovery endpoint ─────────────────────────────────────────────

@app.get("/.well-known/agent.json", tags=["A2A"])
async def agent_card():
    """
    A2A Agent Card.
    Any A2A-compatible client or orchestrator fetches this first to discover
    what the agent can do and how to talk to it.
    """
    return JSONResponse(content=_AGENT_CARD)


# ── JSON-RPC 2.0 endpoint ─────────────────────────────────────────────────────

@app.post("/", tags=["A2A"])
async def jsonrpc_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 dispatcher.

    Routes incoming requests to the appropriate task handler based on 'method'.
    All requests and responses follow JSON-RPC 2.0 format:

      Request : {"jsonrpc":"2.0","id":"...","method":"tasks/send","params":{...}}
      Response: {"jsonrpc":"2.0","id":"...","result":{...}}   (or "error" on failure)
    """
    try:
        body = await request.json()
    except Exception:
        return _err(None, JSONRPC_INTERNAL_ERROR)

    req_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tasks/send":
        return await _tasks_send(req_id, params)
    if method == "tasks/get":
        return _tasks_get(req_id, params)
    if method == "tasks/cancel":
        return _tasks_cancel(req_id, params)
    if method == "tasks/sendSubscribe":
        return await _tasks_send_subscribe(req_id, params)

    return _err(req_id, JSONRPC_METHOD_NOT_FOUND)


# ── Method: tasks/send ────────────────────────────────────────────────────────

async def _tasks_send(req_id: Any, params: Dict) -> JSONResponse:
    """
    tasks/send

    Two behaviours depending on whether the task already exists:

    a) New task (id not in store, or no id provided):
       Creates a Task, calls FinanceAgent.process_task().
       May return 'working' → 'completed' or 'working' → 'input-required'.

    b) Continuation (id exists AND state == 'input-required'):
       Appends the new user message (founder's clarification) and calls
       FinanceAgent.continue_task(). Resumes with full conversation history.
    """
    task_id    = params.get("id") or str(uuid.uuid4())
    msg_data   = params.get("message")
    session_id = params.get("sessionId")
    metadata   = params.get("metadata", {})

    if not msg_data:
        return _err(req_id, JSONRPC_INVALID_PARAMS)

    message  = _parse_message(msg_data)
    existing = _store.get(task_id)

    if existing and existing.status.state == "input-required":
        # Continue task: founder answered the agent's clarification question
        existing.add_message(message)
        result_task = _agent.continue_task(existing)
    else:
        # New task
        task = Task(
            id=task_id,
            status=TaskStatus(state="submitted"),
            messages=[message],
            sessionId=session_id,
            metadata=metadata,
        )
        result_task = _agent.process_task(task)

    _store.save(result_task)
    return _ok(req_id, result_task.to_dict())


# ── Method: tasks/get ─────────────────────────────────────────────────────────

def _tasks_get(req_id: Any, params: Dict) -> JSONResponse:
    """
    tasks/get

    Returns the current state of a task including its status, artifacts,
    and (optionally truncated) message history.

    Optional param: historyLength (int) — limits history entries returned.
    """
    task_id = params.get("id")
    if not task_id:
        return _err(req_id, JSONRPC_INVALID_PARAMS)

    task = _store.get(task_id)
    if not task:
        return _err(req_id, A2A_TASK_NOT_FOUND)

    d = task.to_dict()
    limit = params.get("historyLength")
    if limit is not None:
        d["history"] = d["history"][-int(limit):]

    return _ok(req_id, d)


# ── Method: tasks/cancel ──────────────────────────────────────────────────────

def _tasks_cancel(req_id: Any, params: Dict) -> JSONResponse:
    """
    tasks/cancel

    Cancels a task that is submitted, working, or input-required.
    Returns A2A_TASK_NOT_CANCELABLE if already in a terminal state.
    """
    task_id = params.get("id")
    if not task_id:
        return _err(req_id, JSONRPC_INVALID_PARAMS)

    task = _store.get(task_id)
    if not task:
        return _err(req_id, A2A_TASK_NOT_FOUND)

    if task.status.state in ("completed", "failed", "canceled"):
        return _err(req_id, A2A_TASK_NOT_CANCELABLE)

    task.status = TaskStatus(state="canceled")
    _store.save(task)
    logger.info("[A2AServer] task %s canceled", task_id)
    return _ok(req_id, task.to_dict())


# ── Method: tasks/sendSubscribe ───────────────────────────────────────────────

async def _tasks_send_subscribe(req_id: Any, params: Dict):
    """
    tasks/sendSubscribe

    Same as tasks/send but streams each state transition as an SSE event:
      submitted → working → [artifact events] → completed | input-required | failed

    Each SSE event is a JSON-RPC 2.0 result object.
    The final event has "final": true.
    """
    task_id  = params.get("id") or str(uuid.uuid4())
    msg_data = params.get("message")

    if not msg_data:
        async def _err_stream():
            yield _sse(req_id, {"error": JSONRPC_INVALID_PARAMS.to_dict()})
        return StreamingResponse(_err_stream(), media_type="text/event-stream")

    message = _parse_message(msg_data)
    task = Task(
        id=task_id,
        status=TaskStatus(state="submitted"),
        messages=[message],
        sessionId=params.get("sessionId"),
        metadata=params.get("metadata", {}),
    )

    async def stream():
        # 1. submitted
        yield _sse(req_id, {"id": task_id, "status": TaskStatus(state="submitted").to_dict()})

        # 2. working
        task.status = TaskStatus(state="working")
        yield _sse(req_id, {"id": task_id, "status": task.status.to_dict()})

        # 3. process (synchronous — agent runs here)
        result_task = _agent.process_task(task)
        _store.save(result_task)

        # 4. stream each artifact as it is produced
        for artifact in result_task.artifacts:
            yield _sse(req_id, {"id": task_id, "artifact": artifact.to_dict()})

        # 5. final status transition
        yield _sse(req_id, {
            "id": task_id,
            "status": result_task.status.to_dict(),
            "final": True,
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Utility functions ─────────────────────────────────────────────────────────

def _parse_message(raw: Dict) -> Message:
    """Convert a raw message dict (from JSON-RPC params) to a Message object."""
    parts = [part_from_dict(p) for p in raw.get("parts", [])]
    if not parts:
        # Graceful fallback: treat whole message as plain text
        parts = [TextPart(text=str(raw.get("text", raw)))]
    return Message(role=raw.get("role", "user"), parts=parts)


def _ok(req_id: Any, result: Any) -> JSONResponse:
    """Build a successful JSON-RPC 2.0 response."""
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, error: JSONRPCError) -> JSONResponse:
    """Build a JSON-RPC 2.0 error response (status 200 per spec)."""
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": error.to_dict()})


def _sse(req_id: Any, data: Dict) -> str:
    """Encode one SSE event as a JSON-RPC 2.0 result."""
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": req_id, "result": data},
        ensure_ascii=False,
    )
    return f"data: {payload}\n\n"


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    return {
        "status": "ok",
        "agent": "finance",
        "protocol": "A2A/2.0",
        "version": "2.0.0",
    }
