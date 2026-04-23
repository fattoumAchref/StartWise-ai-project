"""
a2a_bus/bus_client.py
=====================
Client HTTP du bus A2A — utilisé par les agents pour publier et consommer des messages.

Usage (depuis finance_agent) :
    from a2a_bus.bus_client import A2ABusClient
    from models.data_models import A2AMessage

    client = A2ABusClient("finance_agent")
    result = client.publish(a2a_msg)          # publier vers les destinataires
    msgs   = client.get_inbox()               # lire son inbox
    client.ack(message_id)                    # acquitter un message traité

Le client sérialise automatiquement A2AMessage (from_agent → from).
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Any, Dict, List, Optional

import httpx

from models.data_models import A2AMessage

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BUS_URL     = os.getenv("A2A_BUS_URL", "http://localhost:8765")
BUS_TIMEOUT = float(os.getenv("A2A_BUS_TIMEOUT", "10"))


# ─────────────────────────────────────────────────────────────────────────────
# SÉRIALISATION
# ─────────────────────────────────────────────────────────────────────────────
def a2a_to_dict(msg: A2AMessage) -> Dict[str, Any]:
    """
    Convertit un A2AMessage dataclass en dict JSON-ready.
    Renomme from_agent → from (conforme au format standard A2A).
    """
    d = dataclasses.asdict(msg)
    d["from"] = d.pop("from_agent")
    return d


def dict_to_a2a(d: Dict[str, Any]) -> A2AMessage:
    """
    Reconstruit un A2AMessage depuis un dict JSON.
    Renomme from → from_agent.
    """
    d = dict(d)
    if "from" in d:
        d["from_agent"] = d.pop("from")
    # Champs optionnels avec valeurs par défaut
    d.setdefault("type", "unknown")
    d.setdefault("from_agent", "unknown")
    d.setdefault("to", [])
    d.setdefault("timestamp", "")
    d.setdefault("context", {})
    d.setdefault("payload", {})
    d.setdefault("confidence", 0.0)
    d.setdefault("metadata", {})
    return A2AMessage(**{k: v for k, v in d.items() if k in A2AMessage.__dataclass_fields__})


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────────────────────────────────────
class A2ABusClient:
    """
    Client synchrone pour le bus A2A.
    Chaque agent instancie son propre client avec son agent_id.
    """

    def __init__(self, agent_id: str, bus_url: str = BUS_URL):
        self.agent_id = agent_id
        self.bus_url  = bus_url.rstrip("/")

    # ── Publication ───────────────────────────────────────────────────────────

    def publish(self, msg: A2AMessage) -> Dict[str, Any]:
        """
        Publie un A2AMessage vers tous ses destinataires via le bus.
        Retourne la réponse du bus : { status, message_id, routed_to, timestamp }.
        """
        payload = a2a_to_dict(msg)
        resp = httpx.post(
            f"{self.bus_url}/publish",
            json={"message": payload},
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def publish_raw(self, msg_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publie un message déjà sous forme de dict (pour les mock agents).
        """
        resp = httpx.post(
            f"{self.bus_url}/publish",
            json={"message": msg_dict},
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Consommation ──────────────────────────────────────────────────────────

    def get_inbox(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retourne les messages en attente dans l'inbox de cet agent (non-destructif).
        """
        resp = httpx.get(
            f"{self.bus_url}/inbox/{self.agent_id}",
            params={"limit": limit},
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("messages", [])

    def pop(self) -> Optional[Dict[str, Any]]:
        """
        Lit ET supprime le prochain message de l'inbox (FIFO).
        Retourne None si l'inbox est vide.
        """
        resp = httpx.post(
            f"{self.bus_url}/inbox/{self.agent_id}/pop",
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("message")

    def ack(self, message_id: str) -> None:
        """
        Acquitte (supprime) un message spécifique de l'inbox.
        """
        resp = httpx.post(
            f"{self.bus_url}/inbox/{self.agent_id}/ack/{message_id}",
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()

    def clear_inbox(self) -> None:
        """Vide l'inbox (utile pour les tests)."""
        resp = httpx.delete(
            f"{self.bus_url}/inbox/{self.agent_id}",
            timeout=BUS_TIMEOUT,
        )
        resp.raise_for_status()

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def health(self) -> bool:
        """Vérifie que le bus est accessible."""
        try:
            resp = httpx.get(f"{self.bus_url}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du bus."""
        resp = httpx.get(f"{self.bus_url}/stats", timeout=BUS_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
