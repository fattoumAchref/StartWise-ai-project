"""
a2a_bus/comm_agent.py
=====================
Classe de base générique du sous-agent de communication A2A.
Réutilisable par tous les agents du système multi-agent.

Cycle :
  1. SUBSCRIBE  — BRPOP bloquant sur Redis (zéro polling)
  2. PROCESS    — à surcharger par chaque agent (logique métier)
  3. PUBLISH    — envoie un message sur le bus si nécessaire

Chaque agent hérite de CommAgent et surcharge uniquement _process().

Exemple :
    class FinanceCommAgent(CommAgent):
        AGENT_ID = "finance_agent"
        def _process(self, msg):
            if msg["type"] == "investment_scoring":
                ...
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import redis

logger = logging.getLogger(__name__)

REDIS_HOST    = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT    = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB      = int(os.getenv("REDIS_DB", "0"))
BUS_URL       = os.getenv("A2A_BUS_URL", "http://localhost:8765")
BRPOP_TIMEOUT = 5   # secondes avant re-check du signal d'arrêt


class CommAgent(threading.Thread):
    """
    Sous-agent de communication générique.
    Tourne en thread daemon — s'arrête avec le process principal.

    Attributs à définir dans la sous-classe :
        AGENT_ID : str   — identifiant unique de l'agent sur le bus
    """

    AGENT_ID: str = "agent"
    daemon = True

    def __init__(self, bus_url: str = BUS_URL):
        super().__init__(name=f"CommAgent-{self.AGENT_ID}")
        self.bus_url   = bus_url.rstrip("/")
        self._stop_ev  = threading.Event()
        self._redis    = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True,
        )

    # ── Propriétés Redis ──────────────────────────────────────────────────────

    @property
    def _inbox_key(self) -> str:
        return f"a2a:{self.AGENT_ID}:inbox"

    @property
    def _state_key(self) -> str:
        return f"a2a:{self.AGENT_ID}:state"

    @property
    def _history_key(self) -> str:
        return f"a2a:{self.AGENT_ID}:history"

    # ── Cycle principal ───────────────────────────────────────────────────────

    def run(self) -> None:
        logger.info("[%s] comm_agent démarré — écoute %s", self.AGENT_ID, self._inbox_key)
        while not self._stop_ev.is_set():
            try:
                # BRPOP bloque jusqu'à BRPOP_TIMEOUT secondes sans polling
                result = self._redis.brpop(self._inbox_key, timeout=BRPOP_TIMEOUT)
                if result is None:
                    continue  # timeout → re-check stop signal

                _, raw = result
                msg = json.loads(raw)
                self._log_received(msg)
                self._process(msg)

            except redis.exceptions.ConnectionError as e:
                logger.error("[%s] Redis déconnecté : %s", self.AGENT_ID, e)
                self._stop_ev.wait(3)
            except Exception as e:
                logger.exception("[%s] erreur inattendue : %s", self.AGENT_ID, e)

        logger.info("[%s] comm_agent arrêté", self.AGENT_ID)

    def stop(self) -> None:
        """Arrête le thread proprement."""
        self._stop_ev.set()

    # ── À surcharger ──────────────────────────────────────────────────────────

    def _process(self, msg: Dict[str, Any]) -> None:
        """
        Logique de traitement du message reçu.
        Doit être surchargée par chaque agent.
        Par défaut : ignore le message (log uniquement).
        """
        logger.debug(
            "[%s] message ignoré (pas de _process défini) : type=%s",
            self.AGENT_ID, msg.get("type"),
        )

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, msg_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publie un message sur le bus A2A.
        Tente d'abord le bus HTTP, puis fallback direct Redis si indisponible.
        """
        if not msg_dict.get("message_id"):
            import uuid
            msg_dict["message_id"] = str(uuid.uuid4())
        if not msg_dict.get("timestamp"):
            msg_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
        if not msg_dict.get("from"):
            msg_dict["from"] = self.AGENT_ID

        # Try HTTP bus server first
        try:
            resp = httpx.post(
                f"{self.bus_url}/publish",
                json={"message": msg_dict},
                timeout=5,
            )
            resp.raise_for_status()
            self._log_conversation(msg_dict, direction="sent")
            return resp.json()
        except Exception as e:
            logger.warning("[%s] bus HTTP indisponible (%s) — fallback Redis direct", self.AGENT_ID, e)

        # Fallback: push directly to each recipient's Redis inbox
        recipients = msg_dict.get("to", [])
        if not recipients:
            logger.error("[%s] publish fallback: no recipients in 'to'", self.AGENT_ID)
            return {"status": "error", "detail": "no recipients"}

        raw = json.dumps(msg_dict, ensure_ascii=False)
        for recipient in recipients:
            key = f"a2a:{recipient}:inbox"
            self._redis.lpush(key, raw)
            logger.info("[%s] fallback LPUSH → %s", self.AGENT_ID, key)

        self._log_conversation(msg_dict, direction="sent")
        return {"status": "ok", "fallback": "redis_direct"}

    # ── État partagé Redis ────────────────────────────────────────────────────

    def set_state(self, fields: Dict[str, str]) -> None:
        """Écrit des champs dans le hash Redis d'état de cet agent."""
        fields["last_updated"] = datetime.now(timezone.utc).isoformat()
        pipe = self._redis.pipeline()
        for field, value in fields.items():
            pipe.hset(self._state_key, field, value)
        pipe.execute()

    def get_state(self) -> Dict[str, Any]:
        """Retourne l'état courant (lu par Streamlit, React, Django...)."""
        return self._redis.hgetall(self._state_key) or {}

    def clear_state(self) -> None:
        """Remet l'état à zéro."""
        self._redis.delete(self._state_key, self._history_key)

    # ── Historique ────────────────────────────────────────────────────────────

    def _log_received(self, msg: Dict[str, Any], max_entries: int = 50) -> None:
        """Ajoute un résumé du message reçu à l'historique Redis."""
        summary = {
            "message_id": msg.get("message_id", "?"),
            "type":       msg.get("type", "?"),
            "from":       msg.get("from") or msg.get("from_agent", "?"),
            "timestamp":  msg.get("timestamp", ""),
            "confidence": msg.get("confidence", 0),
        }
        self._redis.lpush(self._history_key, json.dumps(summary, ensure_ascii=False))
        self._redis.ltrim(self._history_key, 0, max_entries - 1)
        # also log to shared conversation log
        self._log_conversation(msg, direction="received")

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retourne l'historique des messages reçus par cet agent."""
        raw = self._redis.lrange(self._history_key, 0, limit - 1)
        result = []
        for r in raw:
            try:
                result.append(json.loads(r))
            except Exception:
                pass
        return result

    # ── Conversation log (sent + received, chronological) ────────────────────

    _CONV_KEY = "a2a:conversation:log"
    _CONV_MAX = 100

    def _log_conversation(self, msg: Dict[str, Any], direction: str) -> None:
        """Appends an entry (sent or received) to the shared conversation log."""
        entry = {
            "direction":  direction,           # "sent" | "received"
            "from":       msg.get("from") or self.AGENT_ID,
            "to":         msg.get("to", []),
            "type":       msg.get("type", "?"),
            "message_id": msg.get("message_id", "?"),
            "timestamp":  msg.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "confidence": msg.get("confidence", 0),
        }
        self._redis.lpush(self._CONV_KEY, json.dumps(entry, ensure_ascii=False))
        self._redis.ltrim(self._CONV_KEY, 0, self._CONV_MAX - 1)

    @classmethod
    def get_conversation_log(cls, redis_client=None, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the shared conversation log (newest first)."""
        import os as _os
        r = redis_client or __import__("redis").Redis(
            host=_os.getenv("REDIS_HOST", "localhost"),
            port=int(_os.getenv("REDIS_PORT", "6379")),
            db=int(_os.getenv("REDIS_DB", "0")),
            decode_responses=True,
        )
        raw = r.lrange(cls._CONV_KEY, 0, limit - 1)
        result = []
        for item in raw:
            try:
                result.append(json.loads(item))
            except Exception:
                pass
        return result  # newest first

    @classmethod
    def clear_conversation_log(cls, redis_client=None) -> None:
        import os as _os
        r = redis_client or __import__("redis").Redis(
            host=_os.getenv("REDIS_HOST", "localhost"),
            port=int(_os.getenv("REDIS_PORT", "6379")),
            db=int(_os.getenv("REDIS_DB", "0")),
            decode_responses=True,
        )
        r.delete(cls._CONV_KEY)
