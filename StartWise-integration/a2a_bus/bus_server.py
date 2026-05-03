"""
a2a_bus/bus_server.py
=====================
Serveur HTTP du bus A2A — Redis-backed.

Chaque agent a une inbox Redis (liste) :  <agent_id>:inbox
Les messages publiés sont pushés dans la liste de chaque destinataire.

Endpoints :
  POST /publish                         → publier un message vers ses destinataires
  GET  /inbox/{agent_id}               → lire les messages en attente (non-destructif)
  POST /inbox/{agent_id}/pop           → lire ET supprimer le prochain message
  POST /inbox/{agent_id}/ack/{msg_id}  → supprimer un message spécifique par ID
  GET  /agents                         → liste des agents qui ont des messages
  GET  /stats                          → statistiques du bus
  GET  /health                         → santé du serveur

Lancer :
  uvicorn a2a_bus.bus_server:app --port 8765 --reload
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB   = int(os.getenv("REDIS_DB", "0"))
INBOX_TTL  = int(os.getenv("A2A_INBOX_TTL", "3600"))   # secondes avant expiry
BUS_LOG_KEY = "a2a:bus:log"                              # historique global
BUS_LOG_MAX = 500                                        # max entrées log

# ─────────────────────────────────────────────────────────────────────────────
# REDIS CONNECTION
# ─────────────────────────────────────────────────────────────────────────────
def _get_redis() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
        decode_responses=True,
    )

def _inbox_key(agent_id: str) -> str:
    return f"a2a:{agent_id}:inbox"

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="StartWise A2A Message Bus",
    description="Bus de messages inter-agents — Redis-backed",
    version="1.0.0",
)


# ─── Modèles Pydantic ────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    message: Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Vérifie que le bus et Redis sont opérationnels."""
    try:
        r = _get_redis()
        r.ping()
        return {
            "status": "ok",
            "redis": f"{REDIS_HOST}:{REDIS_PORT}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(503, f"Redis unavailable: {e}")


@app.post("/publish")
def publish(req: PublishRequest):
    """
    Publie un message vers tous les destinataires listés dans 'to'.
    Le message est pushé dans la Redis list <agent_id>:inbox de chacun.
    """
    msg = dict(req.message)

    # Champs obligatoires
    if not msg.get("message_id"):
        msg["message_id"] = str(uuid.uuid4())
    if not msg.get("timestamp"):
        msg["timestamp"] = datetime.now(timezone.utc).isoformat()

    recipients: List[str] = msg.get("to", [])
    if not recipients:
        raise HTTPException(400, "'to' field is empty — message has no recipients")

    from_agent = msg.get("from") or msg.get("from_agent", "unknown")
    msg_json = json.dumps(msg, ensure_ascii=False)

    r = _get_redis()
    pipe = r.pipeline()

    # Push dans l'inbox de chaque destinataire
    for agent_id in recipients:
        key = _inbox_key(agent_id)
        pipe.lpush(key, msg_json)
        pipe.expire(key, INBOX_TTL)

    # Log global (pour debug/monitoring)
    log_entry = json.dumps({
        "event":      "publish",
        "message_id": msg["message_id"],
        "from":       from_agent,
        "to":         recipients,
        "type":       msg.get("type", "unknown"),
        "priority":   msg.get("metadata", {}).get("priority", "?"),
        "timestamp":  msg["timestamp"],
    })
    pipe.lpush(BUS_LOG_KEY, log_entry)
    pipe.ltrim(BUS_LOG_KEY, 0, BUS_LOG_MAX - 1)

    pipe.execute()

    return {
        "status":     "delivered",
        "message_id": msg["message_id"],
        "from":       from_agent,
        "routed_to":  recipients,
        "timestamp":  msg["timestamp"],
    }


@app.get("/inbox/{agent_id}")
def get_inbox(agent_id: str, limit: int = 20):
    """
    Retourne les messages en attente pour agent_id (non-destructif).
    Les messages restent dans la queue jusqu'à pop/ack.
    """
    r = _get_redis()
    key = _inbox_key(agent_id)
    raw_msgs = r.lrange(key, 0, limit - 1)
    messages = []
    for raw in raw_msgs:
        try:
            messages.append(json.loads(raw))
        except Exception:
            pass
    return {
        "agent_id": agent_id,
        "count":    len(messages),
        "messages": messages,
    }


@app.post("/inbox/{agent_id}/pop")
def pop_message(agent_id: str):
    """
    Lit ET supprime le prochain message de l'inbox (FIFO).
    Retourne null si l'inbox est vide.
    """
    r = _get_redis()
    raw = r.rpop(_inbox_key(agent_id))
    if raw is None:
        return {"agent_id": agent_id, "message": None}
    try:
        return {"agent_id": agent_id, "message": json.loads(raw)}
    except Exception:
        return {"agent_id": agent_id, "message": raw}


@app.post("/inbox/{agent_id}/ack/{message_id}")
def ack_message(agent_id: str, message_id: str):
    """
    Supprime un message spécifique de l'inbox (par message_id).
    Utilisé après traitement pour acquitter un message sans consommer les autres.
    """
    r = _get_redis()
    key = _inbox_key(agent_id)
    raw_msgs = r.lrange(key, 0, -1)

    removed = 0
    for raw in raw_msgs:
        try:
            msg = json.loads(raw)
            if msg.get("message_id") == message_id:
                r.lrem(key, 1, raw)
                removed += 1
        except Exception:
            pass

    if removed == 0:
        raise HTTPException(404, f"Message {message_id} not found in {agent_id}'s inbox")

    return {"status": "acked", "message_id": message_id, "agent_id": agent_id}


@app.get("/agents")
def list_agents():
    """Liste tous les agents qui ont actuellement des messages en attente."""
    r = _get_redis()
    keys = r.keys("a2a:*:inbox")
    agents = []
    for key in keys:
        agent_id = key.split(":")[1]
        count = r.llen(key)
        agents.append({"agent_id": agent_id, "pending_messages": count})
    return {"agents": agents}


@app.get("/stats")
def stats():
    """Statistiques globales du bus."""
    r = _get_redis()
    keys = r.keys("a2a:*:inbox")
    inbox_stats = {}
    total = 0
    for key in keys:
        agent_id = key.split(":")[1]
        count = r.llen(key)
        inbox_stats[agent_id] = count
        total += count

    log_count = r.llen(BUS_LOG_KEY)
    return {
        "inboxes":       inbox_stats,
        "total_pending": total,
        "log_entries":   log_count,
        "redis":         f"{REDIS_HOST}:{REDIS_PORT}",
    }


@app.get("/log")
def get_log(limit: int = 20):
    """Historique des derniers messages publiés sur le bus."""
    r = _get_redis()
    raw_entries = r.lrange(BUS_LOG_KEY, 0, limit - 1)
    entries = []
    for raw in raw_entries:
        try:
            entries.append(json.loads(raw))
        except Exception:
            pass
    return {"count": len(entries), "log": entries}


@app.delete("/inbox/{agent_id}")
def clear_inbox(agent_id: str):
    """Vide l'inbox d'un agent (utile pour les tests)."""
    r = _get_redis()
    r.delete(_inbox_key(agent_id))
    return {"status": "cleared", "agent_id": agent_id}
