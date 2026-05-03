"""
agents/risk/a2a_server.py
=========================
True A2A-compliant HTTP server for the Risk Agent.

Implements the Google/IBM A2A Protocol specification:

  GET  /.well-known/agent.json   → Agent Card
  POST /                         → JSON-RPC 2.0 dispatcher
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

from riskAgent.protocol_models import (
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
from riskAgent.risk_agent import RiskAgent

logger = logging.getLogger(__name__)

# ── Agent Card ────────────────────────────────────────────────────────────────

_BASE_URL = os.getenv("RISK_AGENT_URL", "http://localhost:8003")

_AGENT_CARD = AgentCard(
    name="StartWise Risk Agent",
    description=(
        "Autonomous risk analysis agent for startups. Identifies financial, "
        "operational, legal, and market risks based on founder input. "
        "Evaluates severity, likelihood, and impact, and generates mitigation "
        "strategies. Can collaborate with finance, legal, and compliance agents "
        "via the A2A protocol."
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
            id="risk-analysis",
            name="Startup Risk Analysis",
            description=(
                "Full risk assessment: identification of key risks (financial, "
                "market, operational, legal), qualitative and quantitative scoring "
                "(likelihood × impact), risk heatmap generation, and mitigation "
                "strategy recommendations."
            ),
            tags=["risk", "startup", "analysis", "mitigation", "compliance"],
            examples=[
                "Startup SaaS avec dépendance forte à un seul client.",
                "Marketplace avec problèmes de rétention utilisateurs.",
                "Fintech avec contraintes réglementaires élevées.",
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
    _TTL = 3600

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
                    f"a2a:risk:task:{task.id}",
                    self._TTL,
                    json.dumps(task.to_dict(), ensure_ascii=False),
                )
            except Exception:
                pass

    def get(self, task_id: str) -> Optional[Task]:
        return self._mem.get(task_id)

    def delete(self, task_id: str) -> None:
        self._mem.pop(task_id, None)
        if self._redis:
            try:
                self._redis.delete(f"a2a:risk:task:{task_id}")
            except Exception:
                pass


# ── Singletons ────────────────────────────────────────────────────────────────

_store = _TaskStore()
_agent = RiskAgent()

# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="StartWise Risk Agent",
    description="A2A-compliant autonomous risk agent",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Agent Card ────────────────────────────────────────────────────────────────

@app.get("/.well-known/agent.json", tags=["A2A"])
async def agent_card():
    return JSONResponse(content=_AGENT_CARD)


# ── JSON-RPC Dispatcher ───────────────────────────────────────────────────────

@app.post("/", tags=["A2A"])
async def jsonrpc_endpoint(request: Request):
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


# ── tasks/send ────────────────────────────────────────────────────────────────

async def _tasks_send(req_id: Any, params: Dict) -> JSONResponse:
    task_id = params.get("id") or str(uuid.uuid4())
    msg_data = params.get("message")

    if not msg_data:
        return _err(req_id, JSONRPC_INVALID_PARAMS)

    message = _parse_message(msg_data)
    existing = _store.get(task_id)

    if existing and existing.status.state == "input-required":
        existing.add_message(message)
        result_task = _agent.continue_task(existing)
    else:
        task = Task(
            id=task_id,
            status=TaskStatus(state="submitted"),
            messages=[message],
            sessionId=params.get("sessionId"),
            metadata=params.get("metadata", {}),
        )
        result_task = _agent.process_task(task)

    _store.save(result_task)
    return _ok(req_id, result_task.to_dict())


# ── tasks/get ─────────────────────────────────────────────────────────────────

def _tasks_get(req_id: Any, params: Dict) -> JSONResponse:
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


# ── tasks/cancel ──────────────────────────────────────────────────────────────

def _tasks_cancel(req_id: Any, params: Dict) -> JSONResponse:
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


# ── tasks/sendSubscribe ───────────────────────────────────────────────────────

async def _tasks_send_subscribe(req_id: Any, params: Dict):
    task_id = params.get("id") or str(uuid.uuid4())
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
    )

    async def stream():
        yield _sse(req_id, {"id": task_id, "status": TaskStatus(state="submitted").to_dict()})

        task.status = TaskStatus(state="working")
        yield _sse(req_id, {"id": task_id, "status": task.status.to_dict()})

        result_task = _agent.process_task(task)
        _store.save(result_task)

        for artifact in result_task.artifacts:
            yield _sse(req_id, {"id": task_id, "artifact": artifact.to_dict()})

        yield _sse(req_id, {
            "id": task_id,
            "status": result_task.status.to_dict(),
            "final": True,
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── Utils ─────────────────────────────────────────────────────────────────────

def _parse_message(raw: Dict) -> Message:
    parts = [part_from_dict(p) for p in raw.get("parts", [])]
    if not parts:
        parts = [TextPart(text=str(raw))]
    return Message(role=raw.get("role", "user"), parts=parts)


def _ok(req_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": result})


def _err(req_id: Any, error: JSONRPCError) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": req_id, "error": error.to_dict()})


def _sse(req_id: Any, data: Dict) -> str:
    payload = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": data})
    return f"data: {payload}\n\n"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    return {
        "status": "ok",
        "agent": "risk",
        "protocol": "A2A/2.0",
        "version": "2.0.0",
    }