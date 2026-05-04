"""
legal_advisor/bus_adapter.py
============================
A2A bus adapter for the Legal Advisor agent.

Role on the bus:
  - AGENT_ID = "legal_agent"
  - Receives financial_analysis from Finance → stores startup sector/context
    to enrich legal advice (e.g. sector-specific regulations, IP considerations).
  - Receives risk.assessment, investment.recommendation, marketing.analysis
    from peer agents → stores for cross-agent awareness.
  - publish_assessment() is called by views.py after a legal /ask response
    → broadcasts legal.assessment to all specialist agents.

The FinanceCommAgent (bus_publisher.py) automatically stores the published
message under legal_agent_* keys in the shared A2A state hash.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from a2a_bus.comm_agent import CommAgent

logger = logging.getLogger(__name__)

_SEP = "═" * 68

_BASE_URL = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api")
_API_KEY  = os.getenv("ESPRIT_API_KEY", "")
_MODEL    = os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"))

_ALL_AGENTS = ["finance_agent", "investment_agent", "risk_agent", "marketing_agent"]

# How many recent legal assessments to keep in state
_MAX_ASSESSMENTS = 5


def _emit(label: str, **fields) -> None:
    print(f"\n{_SEP}", flush=True)
    print(f"[LegalBusAdapter]  {label}", flush=True)
    for k, v in fields.items():
        print(f"  {k:<28} {v}", flush=True)
    print(_SEP, flush=True)


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: "LegalBusAdapter | None" = None
_lock = threading.Lock()


def get_legal_bus_adapter() -> "LegalBusAdapter":
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = LegalBusAdapter()
            _instance.start()
            logger.info("[LegalBusAdapter] started")
    return _instance


# ── Legal Bus Adapter ─────────────────────────────────────────────────────────

class LegalBusAdapter(CommAgent):
    """
    A2A bus participant for the Legal Advisor agent.
    Listens passively for context from other agents.
    Publishes legal assessments whenever a founder asks a legal question.
    """

    AGENT_ID = "legal_agent"

    _STARTUP_CTX_KEY = "a2a:legal_agent:startup_context"
    _STARTUP_CTX_TTL = 3600

    # All message types Legal recognises (n×n network)
    _KNOWN_TYPES = frozenset({
        "financial_analysis",
        "investment.recommendation",
        "risk.assessment",
        "risk.conflict_report",
        "marketing.analysis",
        "marketing.strategy_note",
        "marketing.investment_alignment",
    })

    # ── Engagement decision ───────────────────────────────────────────────────

    def _should_engage(self, msg: dict) -> bool:
        """
        Autonomous engagement decision (n×n protocol).

        Legal engages with every known agent message type.
        For financial_analysis it additionally checks for usable data.
        """
        msg_type = msg.get("type", "")
        if msg_type not in self._KNOWN_TYPES:
            return False
        if msg_type == "financial_analysis":
            data = msg.get("payload", {}).get("data", {})
            has_data = bool(
                data.get("secteur") or data.get("sector") or data.get("kpis")
            )
            if not has_data:
                logger.info("[LegalBusAdapter] skipping financial_analysis — no usable data")
                return False
        return True

    # ── Main dispatcher ───────────────────────────────────────────────────────

    def _process(self, msg: dict) -> None:
        msg_type = msg.get("type", "")
        sender   = msg.get("from", "?")

        if not self._should_engage(msg):
            logger.debug("[LegalBusAdapter] not engaging with type=%s", msg_type)
            return

        _emit(f"MSG RECEIVED — type={msg_type}", from_agent=sender,
              msg_id=msg.get("message_id", "?")[:16])

        if msg_type == "financial_analysis":
            self._handle_financial_context(msg)

        elif msg_type == "marketing.analysis":
            self._store_peer_analysis(msg, "marketing_agent")

        elif msg_type in ("marketing.strategy_note", "marketing.investment_alignment"):
            self._store_peer_analysis(msg, "marketing_agent")

        elif msg_type == "risk.assessment":
            self._store_peer_assessment(msg, "risk_agent")
            self._react_to_risk(msg)

        elif msg_type == "risk.conflict_report":
            self._store_conflict_report(msg)
            self._react_to_conflict(msg)

        elif msg_type == "investment.recommendation":
            self._store_peer_recommendation(msg, "investment_agent")
            self._react_to_investment(msg)

        else:
            logger.debug("[LegalBusAdapter] stored unknown type=%s", msg_type)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_financial_context(self, msg: dict) -> None:
        """Store financial context to enrich legal advice with sector/phase awareness."""
        data = msg.get("payload", {}).get("data", {})
        kpis = data.get("kpis") or {}

        ctx = {
            "sector":        data.get("secteur") or data.get("sector") or "tech",
            "phase":         data.get("phase") or "SEED",
            "pays":          data.get("pays") or "TN",
            "mrr":           kpis.get("mrr"),
            "runway_months": kpis.get("runway_months"),
        }
        try:
            self._redis.setex(
                self._STARTUP_CTX_KEY, self._STARTUP_CTX_TTL,
                json.dumps(ctx, ensure_ascii=False),
            )
            logger.info("[LegalBusAdapter] startup context stored (sector=%s)", ctx["sector"])
        except Exception as exc:
            logger.warning("[LegalBusAdapter] could not store startup context: %s", exc)

        self.set_state({
            "startup_sector": str(ctx["sector"]),
            "startup_phase":  str(ctx["phase"]),
            "startup_pays":   str(ctx["pays"]),
            "finance_ctx_ts": msg.get("timestamp", ""),
        })

    def _store_peer_analysis(self, msg: dict, sender_id: str) -> None:
        data    = msg.get("payload", {}).get("data", {})
        summary = data.get("summary") or msg.get("payload", {}).get("recommendation", "")[:200]
        score   = data.get("score") or msg.get("confidence", 0)
        self.set_state({
            f"{sender_id}_summary": str(summary)[:200],
            f"{sender_id}_score":   str(score),
            f"{sender_id}_ts":      msg.get("timestamp", ""),
        })

    def _store_peer_assessment(self, msg: dict, sender_id: str) -> None:
        data  = msg.get("payload", {}).get("data", {})
        level = (data.get("risk_level") or data.get("level") or "?")
        score = (data.get("risk_score") or data.get("score") or msg.get("confidence", 0))
        self.set_state({
            f"{sender_id}_level": str(level),
            f"{sender_id}_score": str(score),
            f"{sender_id}_ts":    msg.get("timestamp", ""),
        })

    def _store_peer_recommendation(self, msg: dict, sender_id: str) -> None:
        payload = msg.get("payload", {})
        rating  = payload.get("data", {}).get("rating") or "?"
        rec     = payload.get("recommendation", "")[:200]
        self.set_state({
            f"{sender_id}_rating": rating,
            f"{sender_id}_rec":    rec,
            f"{sender_id}_ts":     msg.get("timestamp", ""),
        })

    def _store_conflict_report(self, msg: dict) -> None:
        data = msg.get("payload", {}).get("data", {})
        self.set_state({
            "conflict_detected":  "true",
            "conflict_count":     str(data.get("conflict_count", 0)),
            "conflict_severity":  str(data.get("severity", "?")),
            "conflict_agents":    json.dumps(data.get("agents_compared", [])),
            "conflict_summary":   str(data.get("summary", ""))[:200],
            "conflict_ts":        msg.get("timestamp", ""),
        })
        logger.info(
            "[LegalBusAdapter] conflict report stored (severity=%s)",
            data.get("severity"),
        )

    # ── Reactive publishes (n×n engagement) ──────────────────────────────────

    def _react_to_risk(self, msg: dict) -> None:
        """
        When financial risk is HIGH/CRITICAL, Legal publishes a regulatory note
        so all agents know there may be legal exposure tied to the financial situation.
        """
        data  = msg.get("payload", {}).get("data", {})
        level = (data.get("risk_level") or "LOW").upper()
        if level not in ("HIGH", "CRITICAL"):
            return

        ctx    = self.get_startup_context() or {}
        sector = ctx.get("sector", "tech")
        pays   = ctx.get("pays", "TN")
        note   = (
            f"Given {level} financial risk in {sector} (jurisdiction: {pays}): "
            "verify contractual obligations are not in breach, review any financial "
            "covenants, and ensure force majeure or insolvency clauses are well-understood."
        )
        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "legal.regulatory_note",
            "from":       "legal_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    msg.get("context", {}),
            "payload": {
                "data": {
                    "risk_level":      level,
                    "regulatory_note": note,
                    "sector":          sector,
                    "pays":            pays,
                    "trigger":         "risk.assessment",
                },
                "recommendation": note,
            },
            "confidence": 0.70,
            "metadata": {
                "priority":          "medium",
                "requires_response": False,
                "tags":              ["legal", "regulatory", level.lower()],
            },
        })
        _emit("REGULATORY NOTE PUBLISHED", trigger="risk.assessment", level=level)
        logger.info("[LegalBusAdapter] regulatory_note published (risk=%s)", level)

    def _react_to_conflict(self, msg: dict) -> None:
        """
        When cross-agent conflicts are detected, Legal flags that contradictory
        signals may carry legal implications that need review.
        """
        data     = msg.get("payload", {}).get("data", {})
        severity = data.get("severity", "none")
        if severity in ("none", "low"):
            return

        count   = data.get("conflict_count", 0)
        summary = str(data.get("summary", ""))[:150]
        note    = (
            f"Cross-agent conflict detected (severity: {severity}, {count} conflict(s)). "
            "Contradictory recommendations may indicate contractual or compliance risks. "
            "Legal review is recommended before any binding decision is made. "
            f"Conflict summary: {summary}"
        )
        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "legal.conflict_review",
            "from":       "legal_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    msg.get("context", {}),
            "payload": {
                "data": {
                    "conflict_severity": severity,
                    "conflict_count":    count,
                    "legal_note":        note,
                },
                "recommendation": note,
            },
            "confidence": 0.65,
            "metadata": {
                "priority":          "medium",
                "requires_response": False,
                "tags":              ["legal", "conflict-review", severity],
            },
        })
        logger.info("[LegalBusAdapter] conflict_review note published (severity=%s)", severity)

    def _react_to_investment(self, msg: dict) -> None:
        """
        When investment signals BUY/STRONG_BUY, Legal publishes a note reminding
        that funding rounds require legal due diligence.
        """
        data   = msg.get("payload", {}).get("data", {})
        rating = str(data.get("rating") or data.get("investment_rating") or "").upper()
        if rating not in ("STRONG_BUY", "BUY"):
            return

        ctx    = self.get_startup_context() or {}
        sector = ctx.get("sector", "tech")
        pays   = ctx.get("pays", "TN")
        note   = (
            f"Investment rating {rating} for {sector} (jurisdiction: {pays}). "
            "Ensure the term sheet, shareholder agreement, and cap table are legally sound. "
            "Verify compliance with local securities regulation and anti-dilution provisions "
            "before closing the round."
        )
        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "legal.investment_note",
            "from":       "legal_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    msg.get("context", {}),
            "payload": {
                "data": {
                    "investment_rating": rating,
                    "legal_note":        note,
                    "sector":            sector,
                    "pays":              pays,
                },
                "recommendation": note,
            },
            "confidence": 0.70,
            "metadata": {
                "priority":          "medium",
                "requires_response": False,
                "tags":              ["legal", "investment-note", rating.lower()],
            },
        })
        logger.info("[LegalBusAdapter] investment_note published (rating=%s)", rating)

    # ── Publish ───────────────────────────────────────────────────────────────

    def get_startup_context(self) -> Optional[Dict]:
        """Return the latest startup context from Finance agent."""
        try:
            raw = self._redis.get(self._STARTUP_CTX_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def publish_assessment(
        self,
        answer:   str,
        question: str,
        sources:  List[str],
        intents:  Optional[set] = None,
        context:  Optional[Dict] = None,
    ) -> None:
        """
        Broadcast a completed legal assessment to all specialist agents.
        Called by the /ask view after a successful LLM response.
        """
        startup_ctx = self.get_startup_context() or {}
        sector  = startup_ctx.get("sector", "tech")
        phase   = startup_ctx.get("phase", "SEED")

        # Derive intent-based severity (informational vs compliance risk)
        has_compliance = bool(intents and any(
            i in intents for i in ("trademark", "legal", "tax")
        ))
        severity = "medium" if has_compliance else "low"
        level    = "MEDIUM" if has_compliance else "LOW"

        msg = {
            "message_id": str(uuid.uuid4()),
            "type":       "legal.assessment",
            "from":       "legal_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    context or {},
            "payload": {
                "data": {
                    "question":     question[:200],
                    "answer":       answer[:500],
                    "sources":      sources[:8],
                    "intents":      list(intents) if intents else [],
                    "sector":       sector,
                    "phase":        phase,
                    "risk_level":   level,
                    "risk_score":   0.4 if has_compliance else 0.2,
                    "severity":     severity,
                    "status":       "answered",
                    "details": [{
                        "severity":       severity,
                        "category":       "Juridique",
                        "title":          f"Avis juridique: {question[:60]}",
                        "description":    answer[:200],
                        "recommendation": "Consulter un avocat pour validation avant toute décision engageante.",
                    }],
                },
                "recommendation": answer[:300],
            },
            "confidence": 0.75,
            "metadata": {
                "priority":          "medium",
                "requires_response": False,
                "tags":              ["legal", "assessment", sector] + (list(intents)[:3] if intents else []),
            },
        }

        self.publish(msg)
        _emit(
            "LEGAL ASSESSMENT PUBLISHED",
            question=question[:60],
            sector=sector,
            level=level,
            recipients=_ALL_AGENTS,
        )
        logger.info("[LegalBusAdapter] legal.assessment published to all agents")
