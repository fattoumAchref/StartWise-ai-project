"""

Dynamic agent registry — discovers available peer agents from
environment variables and their A2A Agent Cards.

"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Built-in agents — always present, URLs overridable via env vars.
_BUILTIN: List[Dict] = [
    {
        "id":           "risk_agent",
        "url":          os.getenv("RISK_AGENT_URL", "http://localhost:8003"),
        "bus_fallback": True,
    }
]


class AgentRegistry:
    """
    Discovers and caches peer agents available to the risk agent.

    Public API:
        get_all()           → list of registered agents (id, url, bus_fallback, role)
        fetch_cards()       → dict {agent_id: AgentCard dict} from /.well-known/agent.json
        get_card(id)        → single card or None
        invalidate_cache()  → force re-fetch of all Agent Cards on next fetch_cards() call
    """

    def __init__(self) -> None:
        self._agents: List[Dict] = self._discover()
        self._cards:  Dict[str, Dict] = {}

    # ── Discovery ─────────────────────────────────────────────────────────────

    def _discover(self) -> List[Dict]:
        """
        Merge built-in agents with any *_AGENT_URL env vars.

        Pattern:  LEGAL_AGENT_URL      →  agent id "legal_agent"
                  COMPLIANCE_AGENT_URL →  agent id "compliance_agent"

        Built-in agents whose URL is overridden via env var keep all their
        other fields (bus_fallback, role) intact.
        """
        agents = [dict(a) for a in _BUILTIN]
        known  = {a["id"] for a in agents}

        for key, val in os.environ.items():
            if not key.endswith("_AGENT_URL") or not val:
                continue

            # LEGAL_AGENT_URL → "legal_agent"
            raw_id   = key[: -len("_URL")].lower()           # e.g. "legal_agent"
            agent_id = raw_id if raw_id.endswith("_agent") else raw_id + "_agent"

            if agent_id in known:
                # Override URL for a built-in agent
                for a in agents:
                    if a["id"] == agent_id:
                        a["url"] = val
            else:
                agents.append({
                    "id":           agent_id,
                    "url":          val,
                    "bus_fallback": False
                })
                known.add(agent_id)
                logger.info(
                    "[AgentRegistry] discovered agent from env: %s @ %s", agent_id, val
                )

        return agents

    # ── Agent Card fetching ───────────────────────────────────────────────────

    def fetch_cards(self) -> Dict[str, Dict]:
        """
        Fetch /.well-known/agent.json from every registered agent.
        Agents that are offline are silently skipped (card stays absent).
        Results are cached — call again to re-fetch after a new agent comes online.
        """
        for agent in self._agents:
            agent_id = agent["id"]
            if agent_id in self._cards:
                continue
            url = agent["url"].rstrip("/") + "/.well-known/agent.json"
            try:
                r = httpx.get(url, timeout=3.0, verify=False)
                if r.status_code == 200:
                    self._cards[agent_id] = r.json()
                    logger.info(
                        "[AgentRegistry] Agent Card fetched: %s → '%s'",
                        agent_id,
                        self._cards[agent_id].get("name", "?"),
                    )
            except Exception as exc:
                logger.debug(
                    "[AgentRegistry] could not fetch card for %s: %s", agent_id, exc
                )
        return self._cards

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_all(self) -> List[Dict]:
        """Return all registered agents (built-in + discovered via env)."""
        return list(self._agents)

    def get_card(self, agent_id: str) -> Optional[Dict]:
        """Return the cached Agent Card for a given agent id, or None."""
        return self._cards.get(agent_id)

    def invalidate_cache(self) -> None:
        """Force re-fetch of all Agent Cards on next fetch_cards() call."""
        self._cards.clear()
        self._agents = self._discover()


# ── Singleton ─────────────────────────────────────────────────────────────────

_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Return the process-wide AgentRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry