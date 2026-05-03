"""
agents/risk/bus_publisher.py
==============================
Autonomous communication agent for the Risk Agent.

Architecture — mirrors the finance comm agent pattern:

  DISPATCH (LLM-driven, no hardcoded routing)
    Incoming messages from ANY agent are classified by content, not type string.
    Adding a legal_agent, compliance_agent, or market_agent requires zero changes
    here — the LLM reads the payload and routes accordingly.

  AUTONOMOUS CLARIFICATION
    When the finance agent or any peer asks questions, the risk comm agent first
    tries to answer from the RiskContext it has stored in Redis.  Only genuinely
    unknown information is forwarded to the requester.

  DYNAMIC CONFLICT DETECTION
    LLM reasons over ALL stored agent risk opinions simultaneously.
    A finance+investment conflict is detected as reliably as a legal+risk one.

  GENERIC STATE STORAGE
    All assessments are stored under {sender_id}_<field> keys.
    Backward-compat keys (risk_level, risk_score, risk_details) kept for app.py.
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
from config.llm_client import create_llm_client

logger = logging.getLogger(__name__)

# ── LLM ───────────────────────────────────────────────────────────────────────

_LLM_URL   = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api") + "/chat/completions"
_LLM_KEY   = os.getenv("ESPRIT_API_KEY", "")
_LLM_MODEL = os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"))


# ── Risk Comm Agent ───────────────────────────────────────────────────────────

class RiskCommAgent(CommAgent):
    """
    Autonomous communication agent for the Risk Agent.
    Handles messages from any peer agent without hardcoded routing.
    """

    AGENT_ID = "risk_agent"

    _CTX_KEY = "a2a:risk_agent:risk_context"
    _CTX_TTL = 3600

    # ── Main dispatcher ───────────────────────────────────────────────────────

    def _process(self, msg: Dict[str, Any]) -> None:
        """
        Classify incoming message by CONTENT (not type string) and dispatch.
        Works for any peer agent — finance, investment, legal, marketing, etc.
        """
        sender = msg.get("from", "unknown_agent")
        intent = self._classify_message(msg)

        logger.info("[risk_comm] %s → intent: %s", sender, intent)

        if intent == "assessment_request":
            self._handle_assessment_request(msg)

        elif intent == "recommendation":
            self._handle_recommendation(msg)
            self._reason_about_conflicts()

        elif intent == "assessment":
            self._handle_assessment(msg)
            self._reason_about_conflicts()

        elif intent == "clarification_request":
            self._handle_clarification_request(msg)

        elif intent == "clarification_response":
            self._handle_clarification_response(msg)

        elif intent == "error":
            error_detail = msg.get("payload", {}).get("data", {}).get("error", "(no detail)")
            logger.warning("[risk_comm] error from %s: %s", sender, error_detail)
            self.set_state({
                "peer_error_from":    sender,
                "peer_error_detail":  error_detail,
                "peer_error_ts":      msg.get("timestamp", ""),
            })

        else:
            self._handle_other(msg, intent)

    # ── Message intent classifier ─────────────────────────────────────────────

    def _classify_message(self, msg: Dict[str, Any]) -> str:
        """
        Heuristic-first, LLM-fallback intent classification.

        Categories:
          assessment_request   — peer asking the risk agent to run an assessment
          recommendation       — final analysis / rating / buy-hold-pass from a peer
          assessment           — risk/legal/compliance evaluation from a peer
          clarification_request — peer asking for missing data
          clarification_response — answer to a previous clarification question
          error                — failure notification
          other                — anything unrecognised
        """
        msg_type = msg.get("type", "")
        t = msg_type.lower()

        if "assessment_request" in t or "risk_request" in t:
            return "assessment_request"
        if "clarification_response" in t:
            return "clarification_response"
        if "clarification_request" in t:
            return "clarification_request"
        if any(x in t for x in ("recommendation", "scoring", "rating")):
            return "recommendation"
        if any(x in t for x in ("assessment", "risk", "legal", "compliance", "marketing")):
            return "assessment"
        if "error" in t:
            return "error"

        # Slow path — ambiguous type string: delegate to LLM
        sender          = msg.get("from", "")
        payload_preview = str(msg.get("payload", {}))[:400]
        raw = create_llm_client(
            [
                {
                    "role": "system",
                    "content": (
                        "Classify an inter-agent message into exactly ONE category:\n"
                        "  assessment_request    — peer asking the risk agent to assess\n"
                        "  recommendation        — final analysis, rating, scoring, buy/hold/pass\n"
                        "  assessment            — risk, legal, compliance, marketing evaluation\n"
                        "  clarification_request — asking for missing data or information\n"
                        "  clarification_response — answer to a clarification question\n"
                        "  error                 — failure or exception notification\n"
                        "  other                 — anything else\n\n"
                        "Reply with ONLY the category name, nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": f"from: {sender}\ntype: {msg_type}\npayload: {payload_preview}",
                },
            ],
            max_tokens=10,
        )
        intent = (raw or "").strip().lower()
        valid = {
            "assessment_request", "recommendation", "assessment",
            "clarification_request", "clarification_response", "error",
        }
        return intent if intent in valid else "other"

    # ── Assessment request (peer asks risk agent to evaluate) ─────────────────

    def _handle_assessment_request(self, msg: Dict[str, Any]) -> None:
        """
        A peer agent is asking the risk agent to run
        an assessment.  Store the request payload so the A2A server's task
        pipeline can pick it up.
        """
        sender  = msg.get("from", "unknown_agent")
        data    = msg.get("payload", {}).get("data", {})

        self.set_state({
            "pending_assessment_request": json.dumps(data, ensure_ascii=False),
            "pending_assessment_from":    sender,
            "pending_assessment_ts":      msg.get("timestamp", ""),
            "pending_assessment_msg_id":  msg.get("message_id", ""),
        })
        logger.info("[risk_comm] assessment_request received from %s", sender)

    # ── Generic recommendation handler ────────────────────────────────────────

    def _handle_recommendation(self, msg: Dict[str, Any]) -> None:
        """Store a recommendation from ANY specialist agent."""
        sender     = msg.get("from", "unknown_agent").lower().replace(" ", "_")
        payload    = msg.get("payload", {})
        data       = payload.get("data", {})
        rec_text   = payload.get("recommendation", "")
        confidence = msg.get("confidence", 0.0)
        rating     = data.get("rating", "")

        self.set_state({
            f"{sender}_rating":         rating,
            f"{sender}_score":          str(int(confidence * 100)),
            f"{sender}_recommendation": rec_text[:300],
            f"{sender}_msg_id":         msg.get("message_id", ""),
            f"{sender}_ts":             msg.get("timestamp", ""),
            f"{sender}_confidence":     str(confidence),
            "last_recommendation_from": sender,
            "last_recommendation_ts":   msg.get("timestamp", ""),
        })
        logger.info("[risk_comm] %s → recommendation: %s (%.0f%%)", sender, rating, confidence * 100)

    # ── Generic assessment handler ─────────────────────────────────────────────

    def _handle_assessment(self, msg: Dict[str, Any]) -> None:
        """
        Store a specialist assessment from ANY peer agent.
        Backward-compat risk_* keys maintained for app.py / finance_comm.
        """
        sender  = msg.get("from", "unknown_agent").lower().replace(" ", "_")
        data    = msg.get("payload", {}).get("data", {})

        level   = (data.get("risk_level") or data.get("level")
                   or data.get("severity") or data.get("status") or "?")
        score   = (data.get("risk_score") or data.get("score")
                   or data.get("rating_value") or msg.get("confidence", 0))
        details = (data.get("risks") or data.get("details")
                   or data.get("issues") or data.get("findings") or [])

        self.set_state({
            f"{sender}_level":   level,
            f"{sender}_score":   str(score),
            f"{sender}_details": json.dumps(details, ensure_ascii=False),
            f"{sender}_msg_id":  msg.get("message_id", ""),
            f"{sender}_ts":      msg.get("timestamp", ""),
        })

        # Backward-compat keys consumed by finance_comm and app.py
        if "risk" in sender:
            self.set_state({
                "risk_level":      level,
                "risk_score":      str(score),
                "risk_details":    json.dumps(details, ensure_ascii=False),
                "risk_msg_id":     msg.get("message_id", ""),
                "risk_ts":         msg.get("timestamp", ""),
                "risk_confidence": str(msg.get("confidence", 0)),
            })

        logger.info("[risk_comm] %s → assessment: level=%s", sender, level)

    # ── Clarification request ─────────────────────────────────────────────────

    def _handle_clarification_request(self, msg: Dict[str, Any]) -> None:
        """
        A peer is asking questions about risk data.  The risk agent first tries
        to answer from its stored RiskContext; unanswered questions are queued.
        """
        data      = msg.get("payload", {}).get("data", {})
        questions = data.get("questions", [])
        phrased   = msg.get("payload", {}).get("recommendation", "")
        sender    = msg.get("from", "finance_agent")

        if not questions:
            logger.warning("[risk_comm] clarification_request with no questions from %s", sender)
            return

        logger.info("[risk_comm] %s asking %d questions — reasoning autonomously", sender, len(questions))

        context      = self._load_risk_context()
        auto_answers = self._auto_answer(questions, context) if context else {q: None for q in questions}
        answered     = {q: a for q, a in auto_answers.items() if a is not None}
        unanswered   = [q for q, a in auto_answers.items() if a is None]

        logger.info(
            "[risk_comm] autonomous: %d/%d answered, %d for requester",
            len(answered), len(questions), len(unanswered),
        )

        if not unanswered:
            self._send_clarification_response(
                answers=answered,
                text="Toutes les données sont disponibles dans le contexte de risque.",
                original_msg=msg,
                autonomous=True,
            )
            self.set_state({
                "clarification_status":    "auto_answered",
                "clarification_ts":        datetime.now(timezone.utc).isoformat(),
                "clarification_phrased":   phrased,
                "clarification_questions": json.dumps([], ensure_ascii=False),
                "clarification_sender":    sender,
            })
            return

        if answered:
            self._send_clarification_response(
                answers=answered,
                text=(
                    "Réponse partielle depuis le contexte de risque : "
                    + "; ".join(f"{q}: {a}" for q, a in answered.items())
                ),
                original_msg=msg,
                autonomous=True,
            )

        # Fallback: if nothing could be auto-answered, respond immediately
        if unanswered and not answered:
            useful: Dict = {}
            if context:
                for k in ["sector", "burn_rate", "cash_balance", "monthly_revenue",
                           "conflict_score", "uncertainty", "monte_carlo_risk"]:
                    if k in context and context[k] is not None:
                        useful[k] = context[k]
            ctx_str = (
                "Données de risque disponibles : "
                + ", ".join(f"{k}={v}" for k, v in useful.items()) + "."
                if useful else "Aucune donnée de risque supplémentaire disponible."
            )
            self._send_clarification_response(
                answers={},
                text=ctx_str + " Procédez avec les données existantes.",
                original_msg=msg,
                autonomous=True,
            )
            self.set_state({
                "clarification_status":       "auto_answered",
                "clarification_ts":           datetime.now(timezone.utc).isoformat(),
                "clarification_phrased":      phrased,
                "clarification_questions":    json.dumps([], ensure_ascii=False),
                "clarification_auto_answers": json.dumps({}, ensure_ascii=False),
                "clarification_sender":       sender,
            })
            logger.info("[risk_comm] fallback auto-response sent to %s", sender)
            return

        # Store remaining questions for deferred answering
        self.set_state({
            "clarification_questions":    json.dumps(unanswered, ensure_ascii=False),
            "clarification_phrased":      phrased,
            "clarification_ts":           msg.get("timestamp", ""),
            "clarification_context":      json.dumps(msg.get("context", {}), ensure_ascii=False),
            "clarification_status":       "pending",
            "clarification_auto_answers": json.dumps(answered, ensure_ascii=False),
            "clarification_sender":       sender,
        })

    # ── Clarification response from a peer ────────────────────────────────────

    def _handle_clarification_response(self, msg: Dict[str, Any]) -> None:
        """
        A peer has answered our clarification questions.
        Store the answers so the A2A task pipeline can resume.
        """
        data   = msg.get("payload", {}).get("data", {})
        sender = msg.get("from", "unknown_agent")

        self.set_state({
            "clarification_answer_from":   sender,
            "clarification_answer_text":   data.get("founder_answer", ""),
            "clarification_answer_data":   json.dumps(data.get("answers", {}), ensure_ascii=False),
            "clarification_answer_ts":     msg.get("timestamp", ""),
            "clarification_answer_status": "received",
        })
        logger.info("[risk_comm] clarification_response received from %s", sender)

    # ── Other / unrecognised messages ─────────────────────────────────────────

    def _handle_other(self, msg: Dict[str, Any], intent: str) -> None:
        sender = msg.get("from", "unknown_agent").lower().replace(" ", "_")
        self.set_state({
            f"{sender}_last_msg_type":    msg.get("type", "unknown"),
            f"{sender}_last_msg_intent":  intent,
            f"{sender}_last_msg_ts":      msg.get("timestamp", ""),
            f"{sender}_last_msg_preview": str(msg.get("payload", {}))[:200],
        })

    # ── LLM conflict detection ────────────────────────────────────────────────

    def _reason_about_conflicts(self) -> None:
        """
        Use LLM to detect contradictions across ALL stored agent opinions.
        Works for any combination of agents — not limited to finance vs investment.
        """
        state    = self.get_state()
        opinions: List[str] = []
        seen: set = set()

        for key in list(state.keys()):
            if key.endswith("_recommendation") and not key.startswith("last_"):
                agent_id = key[: -len("_recommendation")]
                if not agent_id.endswith("_agent") or agent_id in seen:
                    continue
                seen.add(agent_id)
                rec        = state.get(key, "")
                rating     = state.get(f"{agent_id}_rating", "")
                confidence = state.get(f"{agent_id}_confidence", "")
                if rec or rating:
                    opinions.append(
                        f"{agent_id}: rating={rating}, confidence={confidence} — {rec[:120]}"
                    )
            elif key.endswith("_level") and not key.startswith("last_"):
                agent_id = key[: -len("_level")]
                if agent_id in seen:
                    continue
                seen.add(agent_id)
                level = state.get(key, "")
                score = state.get(f"{agent_id}_score", "")
                if level:
                    opinions.append(f"{agent_id}: level={level}, score={score}")

        if len(opinions) < 2:
            self._redis.hdel(
                self._state_key,
                "conflict_type", "conflict_message", "conflict_severity",
            )
            return

        system = (
            "Tu es coordinateur d'agents IA spécialisés en évaluation de risque. "
            "Analyse les évaluations suivantes de différents agents spécialistes "
            "et détecte toute contradiction importante.\n"
            "Si contradiction : retourne UNIQUEMENT un objet JSON valide :\n"
            '{"type": "CONTRADICTION_TYPE", "message": "explication courte", '
            '"severity": "high|medium|low"}\n'
            "Si tout est cohérent : retourne null"
        )
        prompt = "Évaluations des agents :\n" + "\n".join(f"  • {o}" for o in opinions)

        raw = create_llm_client(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=200,
        )

        if raw and raw.strip().lower() not in ("null", "none", ""):
            try:
                start = raw.find("{")
                end   = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    conflict = json.loads(raw[start:end])
                    self.set_state({
                        "conflict_type":     conflict.get("type", "CONFLICT"),
                        "conflict_message":  conflict.get("message", ""),
                        "conflict_severity": conflict.get("severity", "medium"),
                    })
                    logger.warning("[risk_comm] conflict detected: %s", conflict.get("type"))
                    return
            except (json.JSONDecodeError, KeyError):
                pass

        self._redis.hdel(
            self._state_key,
            "conflict_type", "conflict_message", "conflict_severity",
        )

    # ── Risk context storage ──────────────────────────────────────────────────

    def store_risk_context(self, context: Any) -> None:
        """
        Persist the current RiskContext in Redis so the background thread
        can read it when a peer agent asks questions.
        Called by app.py each time a new risk assessment is completed.
        """
        try:
            if hasattr(context, "__dict__"):
                ctx_dict = vars(context)
            elif hasattr(context, "_asdict"):
                ctx_dict = context._asdict()
            else:
                ctx_dict = dict(context) if context else {}

            def _safe(v: Any) -> Any:
                if v is None or isinstance(v, (str, int, float, bool, list, dict)):
                    return v
                if hasattr(v, "value"):
                    return v.value
                return str(v)

            serialisable = {k: _safe(v) for k, v in ctx_dict.items()}
            self._redis.setex(
                self._CTX_KEY, self._CTX_TTL,
                json.dumps(serialisable, ensure_ascii=False),
            )
            logger.info("[risk_comm] risk context stored in Redis")
        except Exception as exc:
            logger.warning("[risk_comm] could not store context: %s", exc)

    def _load_risk_context(self) -> Optional[Dict]:
        try:
            raw = self._redis.get(self._CTX_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("[risk_comm] could not load context: %s", exc)
        return None

    # ── LLM auto-answer from stored context ───────────────────────────────────

    def _auto_answer(self, questions: List[str], context: Dict) -> Dict[str, Optional[str]]:
        """Use LLM to match each question to available risk context data."""
        useful_keys = [
            "sector", "burn_rate", "cash_balance", "monthly_revenue",
            "monte_carlo_risk", "monte_carlo_ci_low", "monte_carlo_ci_high",
            "rag_risk", "rag_confidence", "score_risk", "conflict_score",
            "uncertainty", "composite_risk", "risk_level",
            "conflicts", "conflict_density",
        ]
        known = {
            k: v for k, v in context.items()
            if k in useful_keys and v is not None and v != []
        }

        if not known:
            return {q: None for q in questions}

        system = (
            "Tu es un agent de gestion des risques. Tu disposes des données de risque "
            "d'une startup. Pour chaque question, détermine si tu peux répondre à partir "
            "des données disponibles. Cite les chiffres exacts. Si tu ne peux pas répondre, "
            "réponds null.\n\n"
            "Réponds UNIQUEMENT avec un JSON valide :\n"
            '{"answers": [{"question": "...", "answer": "..." | null}]}'
        )
        prompt = (
            f"Données de risque disponibles :\n{json.dumps(known, ensure_ascii=False, indent=2)}\n\n"
            "Questions :\n"
            + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        )

        raw = _call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=800,
        )
        if not raw:
            return {q: None for q in questions}

        try:
            start  = raw.find("{")
            end    = raw.rfind("}") + 1
            if start < 0 or end <= start:
                return {q: None for q in questions}
            parsed  = json.loads(raw[start:end])
            answers = parsed.get("answers", [])
            result: Dict[str, Optional[str]] = {}
            for item in answers:
                q = item.get("question", "")
                a = item.get("answer")
                matched = _fuzzy_match_question(q, questions)
                if matched:
                    result[matched] = (
                        a if a and str(a).strip().lower() not in ("null", "none", "")
                        else None
                    )
            for q in questions:
                if q not in result:
                    result[q] = None
            return result
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("[risk_comm] could not parse LLM auto-answer: %s", exc)
            return {q: None for q in questions}

    # ── Send clarification response ───────────────────────────────────────────

    def _send_clarification_response(
        self,
        answers: Dict[str, str],
        text: str,
        original_msg: Dict,
        autonomous: bool = False,
    ) -> None:
        """
        Publish a risk.clarification_response to whichever agent asked.
        Recipient is taken from original_msg["from"] — NOT hardcoded.
        """
        context   = original_msg.get("context", {})
        source    = "auto (contexte de risque)" if autonomous else "requester"
        requester = original_msg.get("from", "finance_agent")

        response = {
            "message_id": str(uuid.uuid4()),
            "type":       "risk.clarification_response",
            "from":       "risk_agent",
            "to":         [requester],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    context,
            "payload": {
                "data": {
                    "answer": text,
                    "answers": answers,
                    "source":  source,
                },
                "recommendation": text,
            },
            "confidence": 0.9 if autonomous else 0.85,
            "metadata": {
                "priority":          "high",
                "requires_response": False,
                "tags":              ["clarification", source],
            },
        }
        self.publish(response)
        logger.info(
            "[risk_comm] clarification_response → %s (%s, %d answers)",
            requester, source, len(answers),
        )

    # ── Publish risk assessment result ────────────────────────────────────────

    def publish_assessment(
        self,
        to: List[str],
        risk_level: str,
        risk_score: float,
        composite_risk: float,
        details: Dict[str, Any],
        context: Optional[Dict] = None,
    ) -> None:
        """
        Broadcast a completed risk assessment to peer agents.
        Typically called after the A2A task pipeline finishes.
        """
        msg = {
            "message_id": str(uuid.uuid4()),
            "type":       "risk.assessment",
            "from":       "risk_agent",
            "to":         to,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    context or {},
            "payload": {
                "data": {
                    "risk_level":      risk_level,
                    "risk_score":      risk_score,
                    "composite_risk":  composite_risk,
                    "risks":           details.get("risks", []),
                    "mitigation":      details.get("mitigation", []),
                    "breakdown":       details.get("breakdown", {}),
                    "conflicts":       details.get("conflicts", []),
                    "conflict_score":  details.get("conflict_score", 0.0),
                    "uncertainty":     details.get("uncertainty", 0.5),
                    "monte_carlo":     details.get("monte_carlo", {}),
                },
                "recommendation": details.get("summary", ""),
            },
            "confidence": 1.0 - details.get("uncertainty", 0.5),
            "metadata": {
                "priority":          "high",
                "requires_response": False,
                "tags":              ["risk", "assessment"],
            },
        }
        self.publish(msg)
        logger.info(
            "[risk_comm] assessment published → %s (level=%s, score=%.2f)",
            to, risk_level, risk_score,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fuzzy_match_question(llm_question: str, originals: List[str]) -> Optional[str]:
    """Match the LLM's (possibly rephrased) question back to an original."""
    if not llm_question:
        return None
    q_lower    = llm_question.lower()
    best, best_score = None, 0
    for orig in originals:
        orig_words = set(orig.lower().split())
        q_words    = set(q_lower.split())
        score      = len(orig_words & q_words)
        if score > best_score:
            best, best_score = orig, score
    return best if best_score >= 2 else None


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: Optional[RiskCommAgent] = None
_lock = threading.Lock()


def get_risk_bus_publisher() -> RiskCommAgent:
    """Return the process-wide RiskCommAgent singleton."""
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = RiskCommAgent()
            _instance.start()
            logger.info("[risk_comm] thread started")
    return _instance