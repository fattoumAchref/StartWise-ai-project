"""
agents/bus_adapter.py
=====================
A2A bus adapter for the Marketing agent cluster.

Role on the bus:
  - AGENT_ID = "marketing_agent"
  - Receives financial_analysis from Finance → stores financial context
    so marketing recommendations can be informed by the startup's finances.
  - Receives risk.assessment, investment.recommendation, legal.assessment
    from peer agents → stores for cross-agent awareness.
  - publish_analysis() is called by views.py after the LangGraph pipeline
    completes → broadcasts marketing.analysis to all specialist agents.

The FinanceCommAgent (bus_publisher.py) automatically stores the published
message under marketing_agent_* keys in the shared A2A state hash, making
it available to the frontend via GET /api/a2a/state.
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

# All specialist agents on the bus
_ALL_AGENTS = ["finance_agent", "investment_agent", "risk_agent", "legal_agent"]


def _call_llm(messages: list[dict], max_tokens: int = 300) -> str:
    if not _API_KEY:
        return ""
    try:
        r = httpx.post(
            _BASE_URL + "/chat/completions",
            headers={"Authorization": f"Bearer {_API_KEY}"},
            json={"model": _MODEL, "messages": messages,
                  "temperature": 0.2, "max_tokens": max_tokens},
            timeout=30.0, verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("[MarketingBusAdapter] LLM call failed: %s", exc)
        return ""


def _emit(label: str, **fields) -> None:
    print(f"\n{_SEP}", flush=True)
    print(f"[MarketingBusAdapter]  {label}", flush=True)
    for k, v in fields.items():
        print(f"  {k:<28} {v}", flush=True)
    print(_SEP, flush=True)


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: "MarketingBusAdapter | None" = None
_lock = threading.Lock()


def get_marketing_bus_adapter() -> "MarketingBusAdapter":
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = MarketingBusAdapter()
            _instance.start()
            logger.info("[MarketingBusAdapter] started")
    return _instance


# ── Marketing Bus Adapter ─────────────────────────────────────────────────────

class MarketingBusAdapter(CommAgent):
    """
    A2A bus participant for the Marketing agent.
    Listens passively for context from other agents.
    Publishes marketing analysis results when they are ready.
    """

    AGENT_ID = "marketing_agent"

    # Redis key to cache the latest financial context received from Finance
    _FIN_CTX_KEY = "a2a:marketing_agent:financial_context"
    _FIN_CTX_TTL = 3600

    # All message types this agent recognises from the n×n network
    _KNOWN_TYPES = frozenset({
        "financial_analysis",
        "investment.recommendation",
        "risk.assessment",
        "risk.conflict_report",
        "legal.assessment",
        "legal.regulatory_note",
        "legal.investment_note",
        "legal.conflict_review",
    })

    # ── Engagement decision ───────────────────────────────────────────────────

    def _should_engage(self, msg: dict) -> bool:
        """
        Autonomous engagement decision (n×n protocol).

        Marketing engages with every known agent message type.
        For financial_analysis it additionally checks that there is at least
        some usable data — sector, phase, or KPIs — before processing.
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
                logger.info("[MarketingBusAdapter] skipping financial_analysis — no usable data")
                return False
        return True

    # ── Main dispatcher ───────────────────────────────────────────────────────

    def _process(self, msg: dict) -> None:
        msg_type = msg.get("type", "")
        sender   = msg.get("from", "?")

        if not self._should_engage(msg):
            logger.debug("[MarketingBusAdapter] not engaging with type=%s", msg_type)
            return

        _emit(f"MSG RECEIVED — type={msg_type}", from_agent=sender,
              msg_id=msg.get("message_id", "?")[:16])

        if msg_type == "financial_analysis":
            self._handle_financial_context(msg)

        elif msg_type == "risk.assessment":
            self._store_peer_assessment(msg, "risk_agent")
            self._react_to_risk(msg)

        elif msg_type == "risk.conflict_report":
            self._store_conflict_report(msg)

        elif msg_type == "investment.recommendation":
            self._store_peer_recommendation(msg, "investment_agent")
            self._react_to_investment(msg)

        elif msg_type == "legal.assessment":
            self._store_peer_assessment(msg, "legal_agent")

        elif msg_type in ("legal.regulatory_note", "legal.investment_note",
                          "legal.conflict_review"):
            # Store legal notes as context enrichment — no further reaction needed
            self._store_peer_assessment(msg, "legal_agent")

        else:
            logger.debug("[MarketingBusAdapter] stored unknown type=%s", msg_type)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_financial_context(self, msg: dict) -> None:
        """Store financial KPIs received from Finance agent for context enrichment."""
        data = msg.get("payload", {}).get("data", {})
        kpis = data.get("kpis") or {}

        ctx = {
            "sector":        data.get("secteur") or data.get("sector") or "tech",
            "phase":         data.get("phase") or "SEED",
            "mrr":           kpis.get("mrr"),
            "runway_months": kpis.get("runway_months"),
            "burn_net":      kpis.get("burn_net"),
            "proba_survie":  (data.get("monte_carlo") or {}).get("proba_survie_12m"),
        }
        try:
            self._redis.setex(
                self._FIN_CTX_KEY, self._FIN_CTX_TTL,
                json.dumps(ctx, ensure_ascii=False),
            )
            logger.info("[MarketingBusAdapter] financial context stored (sector=%s)", ctx["sector"])
        except Exception as exc:
            logger.warning("[MarketingBusAdapter] could not store financial context: %s", exc)

        # Store in state for frontend visibility
        self.set_state({
            "financial_context_sector":  str(ctx["sector"]),
            "financial_context_phase":   str(ctx["phase"]),
            "financial_context_received": msg.get("timestamp", ""),
        })

    def _store_peer_assessment(self, msg: dict, sender_id: str) -> None:
        data = msg.get("payload", {}).get("data", {})
        level = (data.get("risk_level") or data.get("level") or data.get("status") or "?")
        score = (data.get("risk_score") or data.get("score") or msg.get("confidence", 0))
        self.set_state({
            f"{sender_id}_level":  str(level),
            f"{sender_id}_score":  str(score),
            f"{sender_id}_ts":     msg.get("timestamp", ""),
        })
        logger.info("[MarketingBusAdapter] stored %s assessment: level=%s", sender_id, level)

    def _store_peer_recommendation(self, msg: dict, sender_id: str) -> None:
        payload = msg.get("payload", {})
        rating  = payload.get("data", {}).get("rating") or payload.get("rating") or "?"
        rec     = payload.get("recommendation", "")[:200]
        self.set_state({
            f"{sender_id}_rating":  rating,
            f"{sender_id}_rec":     rec,
            f"{sender_id}_ts":      msg.get("timestamp", ""),
        })
        logger.info("[MarketingBusAdapter] stored %s recommendation: %s", sender_id, rating)

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
            "[MarketingBusAdapter] conflict report stored (severity=%s, count=%s)",
            data.get("severity"), data.get("conflict_count"),
        )

    # ── Reactive publishes (n×n engagement) ──────────────────────────────────

    def _react_to_risk(self, msg: dict) -> None:
        """
        When the risk agent signals HIGH or CRITICAL financial risk, Marketing
        publishes a strategy note so all agents know the marketing stance is
        adjusting toward conservative/retention-focused campaigns.
        """
        data  = msg.get("payload", {}).get("data", {})
        level = (data.get("risk_level") or "LOW").upper()
        if level not in ("HIGH", "CRITICAL"):
            return

        score   = float(data.get("risk_score") or 0)
        fin_ctx = self.get_financial_context() or {}
        sector  = fin_ctx.get("sector", "tech")
        note    = self._generate_risk_strategy_note(level, score, sector)
        if not note:
            return

        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "marketing.strategy_note",
            "from":       "marketing_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    msg.get("context", {}),
            "payload": {
                "data": {
                    "risk_level":    level,
                    "strategy_note": note,
                    "sector":        sector,
                    "trigger":       "risk.assessment",
                },
                "recommendation": note,
            },
            "confidence": 0.65,
            "metadata": {
                "priority":          "low",
                "requires_response": False,
                "tags":              ["marketing", "strategy-note", level.lower()],
            },
        })
        _emit("STRATEGY NOTE PUBLISHED", trigger="risk.assessment", level=level)
        logger.info("[MarketingBusAdapter] strategy_note published in response to %s risk", level)

    def _react_to_investment(self, msg: dict) -> None:
        """
        When investment signals BUY or STRONG_BUY, Marketing publishes an
        alignment note encouraging capitalising on the positive momentum.
        """
        data   = msg.get("payload", {}).get("data", {})
        rating = str(data.get("rating") or data.get("investment_rating") or "").upper()
        if rating not in ("STRONG_BUY", "BUY"):
            return

        fin_ctx = self.get_financial_context() or {}
        sector  = fin_ctx.get("sector", "tech")
        note    = (
            f"Investment signal {rating} for {sector} sector. "
            "Marketing should amplify the growth narrative, leverage investor "
            "validation in PR/content, and accelerate customer acquisition "
            "in the current momentum window."
        )
        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "marketing.investment_alignment",
            "from":       "marketing_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    msg.get("context", {}),
            "payload": {
                "data": {
                    "investment_rating": rating,
                    "alignment_note":    note,
                    "sector":            sector,
                },
                "recommendation": note,
            },
            "confidence": 0.60,
            "metadata": {
                "priority":          "low",
                "requires_response": False,
                "tags":              ["marketing", "investment-alignment", rating.lower()],
            },
        })
        logger.info("[MarketingBusAdapter] investment_alignment note published (rating=%s)", rating)

    def _generate_risk_strategy_note(self, level: str, score: float, sector: str) -> str:
        base = (
            f"Given {level} financial risk (score {score:.1f}/10) in {sector}: "
            "prioritise retention campaigns, cut experimental spend, focus on "
            "highest-ROI acquisition channels and reduce CAC immediately."
        )
        if not _API_KEY:
            return base
        raw = _call_llm([
            {"role": "system", "content":
             "You are a marketing strategist. In 2 sentences give a marketing "
             "recommendation given the financial risk level. Be specific and actionable."},
            {"role": "user", "content":
             f"Risk level: {level}, score: {score:.1f}/10, sector: {sector}"},
        ], max_tokens=100)
        return raw if raw else base

    # ── Publish ───────────────────────────────────────────────────────────────

    def get_financial_context(self) -> Optional[Dict]:
        """Return the latest financial context received from the Finance agent."""
        try:
            raw = self._redis.get(self._FIN_CTX_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def publish_analysis(
        self,
        trend_result:    Dict[str, Any],
        vision_result:   Dict[str, Any],
        emotion_result:  Dict[str, Any],
        creative_result: Dict[str, Any],
        project_description: str = "",
        context: Optional[Dict] = None,
    ) -> None:
        """
        Broadcast the completed marketing analysis to all specialist agents.
        Called by views.py after the LangGraph pipeline completes.
        """
        fin_ctx   = self.get_financial_context() or {}
        sector    = fin_ctx.get("sector") or "tech"
        phase     = fin_ctx.get("phase") or "SEED"

        # Extract key signals from pipeline results
        trend_summary    = self._extract_text(trend_result)
        vision_summary   = self._extract_text(vision_result)
        emotion_summary  = self._extract_text(emotion_result)
        creative_summary = self._extract_text(creative_result)

        # Build confidence score from self-correction
        confidence = min(1.0, max(0.3, 0.65))

        summary = (
            f"Marketing analysis for sector '{sector}' (phase {phase}). "
            f"Trends: {trend_summary[:80]}. "
            f"Vision: {vision_summary[:80]}."
        )

        msg = {
            "message_id": str(uuid.uuid4()),
            "type":       "marketing.analysis",
            "from":       "marketing_agent",
            "to":         _ALL_AGENTS,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    context or {},
            "payload": {
                "data": {
                    "sector":           sector,
                    "phase":            phase,
                    "trend":            trend_result,
                    "vision":           vision_result,
                    "emotion":          emotion_result,
                    "creative":         creative_result,
                    "project_description": project_description[:400],
                    "trend_summary":    trend_summary[:200],
                    "vision_summary":   vision_summary[:200],
                    "emotion_summary":  emotion_summary[:200],
                    "creative_summary": creative_summary[:200],
                    "summary":          summary,
                    "score":            confidence,
                    "status":           "completed",
                },
                "recommendation": summary,
            },
            "confidence": confidence,
            "metadata": {
                "priority":          "medium",
                "requires_response": False,
                "tags":              ["marketing", "analysis", sector],
            },
        }

        self.publish(msg)
        _emit("MARKETING ANALYSIS PUBLISHED", sector=sector, phase=phase, recipients=_ALL_AGENTS)
        logger.info("[MarketingBusAdapter] marketing.analysis published to all agents")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_text(self, result: Dict[str, Any]) -> str:
        """Extract the most informative text from a pipeline step result."""
        if not result:
            return ""
        for key in ("summary", "analysis", "content", "text", "report",
                    "description", "output", "result"):
            val = result.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:200]
        # Last resort: first string value
        for v in result.values():
            if isinstance(v, str) and v.strip():
                return v.strip()[:200]
        return ""
