"""
agents/finance/comm_agent.py
============================
Autonomous communication agent for finance_agent.

Architecture — what makes this truly agent-driven and extensible:

  DISPATCH (no hardcoded routing)
    Messages from ANY agent are classified by the LLM on the basis of
    their *content*, not their type string.  Adding a risk_agent, legal_agent
    or marketing_agent requires zero code changes here — the LLM will
    understand their messages and route them correctly.

  AUTONOMOUS CLARIFICATION
    When any specialist agent asks questions about the startup, the finance
    comm agent first tries to answer from the FinancialContext it already
    has stored in Redis.  Only genuinely unknown information is forwarded
    to the founder.

  DYNAMIC CONFLICT DETECTION
    Instead of a hardcoded conflict matrix (investment vs risk only), the
    LLM reasons over ALL stored specialist opinions.  A risk+legal conflict,
    or a marketing+investment disagreement, is detected equally well.

  GENERIC STATE STORAGE
    Recommendations and assessments are stored under  {sender_id}_<field>
    keys — no agent is privileged.  app.py backward compat keys
    (investment_rating, risk_level …) are kept for the existing UI.
"""

from __future__ import annotations

import dataclasses
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

# ── LLM ───────────────────────────────────────────────────────────────────────

_LLM_URL   = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api") + "/chat/completions"
_LLM_KEY   = os.getenv("ESPRIT_API_KEY", "")
_LLM_MODEL = os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"))


def _call_llm(messages: List[Dict], max_tokens: int = 600) -> str:
    if not _LLM_KEY:
        return ""
    try:
        r = httpx.post(
            _LLM_URL,
            headers={"Authorization": f"Bearer {_LLM_KEY}", "Content-Type": "application/json"},
            json={"model": _LLM_MODEL, "messages": messages,
                  "temperature": 0.2, "max_tokens": max_tokens},
            timeout=30.0,
            verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("[finance_comm] LLM call failed: %s", exc)
        return ""


# ── Backward-compat helpers (kept for app.py conflict badge) ─────────────────

def _score_to_rating(confidence: float) -> str:
    if confidence >= 0.8:   return "STRONG_BUY"
    if confidence >= 0.65:  return "BUY"
    if confidence >= 0.45:  return "HOLD"
    return "PASS"


def _is_investment_conflict_stance_bus_message(msg: Dict[str, Any], rec_text: str) -> bool:
    """
    True for investment.conflict_stance or any mis-routed copy that carries the
    reactive conflict note — must never update investment_* verdict fields.
    """
    t = (msg.get("type") or "").lower()
    if "conflict_stance" in t:
        return True
    pl = msg.get("payload")
    if not isinstance(pl, dict):
        pl = {}
    data = pl.get("data") or {}
    if data.get("confidence_reduced") is True and data.get("conflict_severity"):
        return True
    rt = (rec_text or "").lower()
    return "cross-agent conflict" in rt and "confidence is reduced" in rt


# ── Finance Comm Agent ────────────────────────────────────────────────────────

class FinanceCommAgent(CommAgent):
    """
    Autonomous communication agent for finance_agent.
    Handles messages from any specialist agent without hardcoded routing.
    """

    AGENT_ID = "finance_agent"

    _CTX_KEY = "a2a:finance_agent:financial_context"
    _CTX_TTL = 3600

    # ── Main dispatcher (LLM-driven) ─────────────────────────────────────────

    def _process(self, msg: Dict[str, Any]) -> None:
        """
        Classify incoming message by CONTENT (not type string) and dispatch.

        Works for any agent — investment, risk, legal, marketing, or future ones
        we haven't built yet.  No elif chain needed.
        """
        sender = msg.get("from", "unknown_agent")
        intent = self._classify_message(msg)

        logger.info("[finance_comm] %s → intent: %s", sender, intent)

        if intent == "recommendation":
            self._handle_recommendation(msg)

        elif intent == "conflict_stance":
            # investment.conflict_stance — store stance only; do not run finance LLM conflict pass
            self._handle_recommendation(msg)

        elif intent == "clarification_request":
            # Finance agent reasons autonomously before involving the founder
            self._handle_clarification_request(msg)

        elif intent == "assessment":
            self._handle_assessment(msg)

        elif intent == "error":
            error_detail = msg.get("payload", {}).get("data", {}).get("error", "(no detail)")
            logger.warning("[finance_comm] error from %s: %s", sender, error_detail)
            # Store error in state so frontend stops polling and shows the error
            self.set_state({
                "investment_error": error_detail,
                "investment_rating": "ERROR",
                "investment_recommendation": f"L'agent d'investissement a rencontré une erreur : {error_detail}",
            })

        else:
            # Unknown intent — store it generically so the UI can still show it
            self._handle_other(msg, intent)

    def _classify_message(self, msg: Dict[str, Any]) -> str:
        """
        Determine message intent — heuristic first, LLM only for ambiguous cases.

        The type string already encodes the intent for all structured agent messages
        (e.g. investment.recommendation, investment.clarification_request). The LLM
        is reserved for genuinely novel or ambiguous payloads where the type string
        gives no clear signal.

        Categories:
          recommendation        — final analysis, rating, scoring, buy/hold/pass
          clarification_request — asking for missing data or information
          assessment            — risk, legal, compliance, marketing analysis
          error                 — failure or exception notification
          other                 — anything else
        """
        msg_type = msg.get("type", "")
        t = msg_type.lower()

        # Fast path — type string is unambiguous for all known agent message types
        if "conflict_stance" in t:
            return "conflict_stance"
        # Do not use bare "stance" — it matches investment.conflict_stance and mis-routes messages.
        if any(x in t for x in ("recommendation", "scoring", "rating",
                                 "alignment", "investment_note")):
            return "recommendation"
        if "clarification_request" in t:
            return "clarification_request"
        if any(x in t for x in ("assessment", "risk", "legal", "compliance",
                                 "marketing", "conflict", "regulatory", "strategy_note")):
            return "assessment"
        if "error" in t:
            return "error"

        # Slow path — type string is uninformative; use LLM to read the payload
        sender          = msg.get("from", "")
        payload_preview = str(msg.get("payload", {}))[:400]
        raw = _call_llm(
            [
                {
                    "role": "system",
                    "content": (
                        "Classify an inter-agent message into exactly ONE category:\n"
                        "  recommendation        — final analysis, rating, scoring, buy/hold/pass\n"
                        "  clarification_request — asking for missing data or information\n"
                        "  assessment            — risk, legal, compliance, marketing analysis\n"
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
        if intent in ("recommendation", "clarification_request", "assessment", "error"):
            return intent
        return "other"

    # ── Generic recommendation handler ───────────────────────────────────────

    def _handle_recommendation(self, msg: Dict[str, Any]) -> None:
        """
        Store a recommendation from ANY specialist agent.
        State keys are prefixed with the sender ID so multiple agents
        can each store their own result without collisions.

        Backward-compat investment_* keys are maintained for app.py.
        """
        sender     = msg.get("from", "unknown_agent").lower().replace(" ", "_")
        msg_type   = msg.get("type", "")
        payload    = msg.get("payload", {})
        data       = payload.get("data", {})
        rec_text   = payload.get("recommendation", "")
        confidence = msg.get("confidence", 0.0)
        rating     = data.get("rating") or _score_to_rating(confidence)

        if _is_investment_conflict_stance_bus_message(msg, rec_text):
            note = str(data.get("note") or rec_text or "")[:800]
            self.set_state({
                "investment_conflict_stance":          note,
                "investment_conflict_stance_severity": str(data.get("conflict_severity", "")),
                "investment_conflict_stance_ts":       msg.get("timestamp", ""),
            })
            logger.info("[finance_comm] investment conflict stance stored (verdict keys unchanged)")
            return

        # Generic keys — work for any sender
        self.set_state({
            f"{sender}_rating":         rating,
            f"{sender}_score":          str(int(confidence * 100)),
            f"{sender}_recommendation": rec_text[:300] if rec_text else "",
            f"{sender}_msg_id":         msg.get("message_id", ""),
            f"{sender}_ts":             msg.get("timestamp", ""),
            f"{sender}_confidence":     str(confidence),
            "last_recommendation_from": sender,
            "last_recommendation_ts":   msg.get("timestamp", ""),
        })

        # Backward-compat keys for app.py — only real verdicts / errors, never conflict stance text.
        if (
            "investment" in sender
            and msg_type in ("investment.recommendation", "investment.error")
            and not _is_investment_conflict_stance_bus_message(msg, rec_text)
        ):
            val = data.get("valuation") or {}
            opt = data.get("optimal_scenario") or {}
            dil = data.get("dilution") or {}
            self.set_state({
                "investment_rating":         rating,
                "investment_score":          str(int(confidence * 100)),
                "investment_recommendation": rec_text[:300] if rec_text else "",
                "investment_reasons":        json.dumps([], ensure_ascii=False),
                "investment_msg_id":         msg.get("message_id", ""),
                "investment_ts":             msg.get("timestamp", ""),
                "investment_confidence":     str(confidence),
                "valuation":                 str(val.get("final_valuation", "")),
                "valuation_method":          val.get("method", ""),
                "best_scenario":             opt.get("name", ""),
                "best_scenario_raise":       str(opt.get("raise_amount", "")),
                "best_scenario_dilution":    str(opt.get("dilution_pct", "")),
                "best_scenario_post_money":  str(opt.get("post_money", "")),
                "best_scenario_rationale":   opt.get("rationale", "")[:200],
                "dilution_pct":              str(dil.get("founder_dilution_pct", "")),
                "founder_after_pct":         str(dil.get("founder_after_pct", "")),
            })
            if msg_type == "investment.recommendation":
                self._redis.hdel(
                    self._state_key,
                    "conflict_type", "conflict_message", "conflict_severity",
                )

        logger.info(
            "[finance_comm] %s → recommendation: %s (%.0f%%)",
            sender, rating, confidence * 100,
        )

    # ── Generic assessment handler ────────────────────────────────────────────

    def _handle_assessment(self, msg: Dict[str, Any]) -> None:
        """
        Store a specialist assessment from ANY agent (risk, legal, marketing…).
        Extracts common fields generically — not tied to any agent's schema.

        Backward-compat risk_* keys are maintained for app.py.
        """
        sender  = msg.get("from", "unknown_agent").lower().replace(" ", "_")
        data    = msg.get("payload", {}).get("data", {})

        # Generic field extraction — try common naming conventions
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

        # Backward-compat risk_* keys for app.py
        if "risk" in sender:
            self.set_state({
                "risk_level":      level,
                "risk_score":      str(score),
                "risk_details":    json.dumps(details, ensure_ascii=False),
                "risk_msg_id":     msg.get("message_id", ""),
                "risk_ts":         msg.get("timestamp", ""),
                "risk_confidence": str(msg.get("confidence", 0)),
            })

        logger.info("[finance_comm] %s → assessment: level=%s", sender, level)

    def _handle_other(self, msg: Dict[str, Any], intent: str) -> None:
        """Store any unrecognised message under a generic key so the UI can show it."""
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

        Works for any combination of agents — not just investment vs risk.
        A legal+investment conflict, or a marketing+risk disagreement,
        is detected equally well.

        Falls back to a simple heuristic if fewer than 2 opinions are stored
        or if the LLM is unavailable.
        """
        state = self.get_state()

        # Collect every stored opinion from any agent
        opinions: List[str] = []
        seen_agents: set = set()

        for key in list(state.keys()):
            if key.endswith("_recommendation") and not key.startswith("last_"):
                agent_id = key[: -len("_recommendation")]
                # Skip backward-compat shorthand keys (e.g. "investment_recommendation"
                # is a compat alias for "investment_agent_recommendation" — same agent)
                if not agent_id.endswith("_agent"):
                    continue
                if agent_id in seen_agents:
                    continue
                seen_agents.add(agent_id)
                rec        = state.get(key, "")
                rating     = state.get(f"{agent_id}_rating", "")
                confidence = state.get(f"{agent_id}_confidence", "")
                if rec or rating:
                    opinions.append(
                        f"{agent_id}: rating={rating}, confidence={confidence} — {rec[:120]}"
                    )

            elif key.endswith("_level") and not key.startswith("last_"):
                agent_id = key[: -len("_level")]
                if agent_id in seen_agents:
                    continue
                seen_agents.add(agent_id)
                level = state.get(key, "")
                score = state.get(f"{agent_id}_score", "")
                if level:
                    opinions.append(f"{agent_id}: level={level}, score={score}")

        if len(opinions) < 2:
            # Not enough signals yet — clear any stale conflict
            self._redis.hdel(
                self._state_key,
                "conflict_type", "conflict_message", "conflict_severity",
            )
            return

        system = (
            "Tu es coordinateur d'agents IA. Analyse les évaluations suivantes de "
            "différents agents spécialistes et détecte toute contradiction importante.\n"
            "Si contradiction : retourne UNIQUEMENT un objet JSON valide :\n"
            '{"type": "CONTRADICTION_TYPE", "message": "explication courte", '
            '"severity": "high|medium|low"}\n'
            "Si tout est cohérent : retourne null"
        )
        prompt = "Évaluations des agents :\n" + "\n".join(f"  • {o}" for o in opinions)

        raw = _call_llm(
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
                    logger.warning("[finance_comm] conflict detected: %s", conflict.get("type"))
                    return
            except (json.JSONDecodeError, KeyError):
                pass

        # No conflict detected — clear previous conflict state
        self._redis.hdel(
            self._state_key,
            "conflict_type", "conflict_message", "conflict_severity",
        )

    # ── Context store (called by app.py after pipeline runs) ─────────────────

    def store_financial_context(self, context: Any) -> None:
        """
        Persist the current FinancialContext in Redis so the background thread
        can read it when any specialist agent asks questions.
        Called by app.py each time a new analysis is completed.
        """
        try:
            if dataclasses.is_dataclass(context):
                ctx_dict = dataclasses.asdict(context)
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
            logger.info("[finance_comm] financial context stored in Redis")
        except Exception as exc:
            logger.warning("[finance_comm] could not store context: %s", exc)

    def _load_financial_context(self) -> Optional[Dict]:
        try:
            raw = self._redis.get(self._CTX_KEY)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("[finance_comm] could not load context: %s", exc)
        return None

    # ── Autonomous clarification handler ─────────────────────────────────────

    def _handle_clarification_request(self, msg: Dict[str, Any]) -> None:
        """
        Any specialist agent is asking questions about the startup.

        The finance agent reasons autonomously:
          1. Load the FinancialContext it already has
          2. Use LLM to answer what it knows from context
          3. Answer immediately what it knows (no founder needed)
          4. Forward ONLY what it genuinely doesn't know to the founder
        """
        data      = msg.get("payload", {}).get("data", {})
        questions = data.get("questions", [])
        phrased   = msg.get("payload", {}).get("recommendation", "")
        sender    = msg.get("from", "investment_agent")   # who asked — we reply to them

        if not questions:
            logger.warning("[finance_comm] clarification_request with no questions from %s", sender)
            return

        logger.info(
            "[finance_comm] %s asking %d questions — reasoning autonomously",
            sender, len(questions),
        )

        context = self._load_financial_context()

        if context:
            auto_answers = self._auto_answer(questions, context)
            unanswered   = [q for q, a in auto_answers.items() if a is None]
            answered     = {q: a for q, a in auto_answers.items() if a is not None}

            logger.info(
                "[finance_comm] autonomous: %d/%d answered from context, %d for founder",
                len(answered), len(questions), len(unanswered),
            )

            if not unanswered:
                # Agent knows everything — reply immediately
                self._send_clarification_response(
                    answers=answered,
                    founder_text="Toutes les données sont disponibles dans le contexte financier.",
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
                # Partial auto-response — send what we know immediately
                self._send_clarification_response(
                    answers=answered,
                    founder_text=(
                        "Réponse partielle depuis le contexte : "
                        + "; ".join(f"{q}: {a}" for q, a in answered.items())
                    ),
                    original_msg=msg,
                    autonomous=True,
                )
                logger.info(
                    "[finance_comm] partial auto-response sent — %d questions for founder",
                    len(unanswered),
                )
        else:
            unanswered = questions
            answered   = {}
            logger.info("[finance_comm] no stored context — all %d questions for founder", len(questions))

        # ── Fallback: always respond so the investment agent doesn't hang ─────
        # When ALL questions are unanswered (LLM unavailable, no usable context,
        # or no auto-answers found), send an immediate "proceed with available
        # data" response.  Without this the investment agent waits indefinitely
        # on its BRPOP inbox and Round 4 never happens.
        if unanswered and not answered:
            useful: dict = {}
            if context:
                for k in [
                    "burn_rate", "cash_balance", "monthly_revenue", "n_clients",
                    "churn_rate", "secteur", "pays", "intent_fundraising",
                ]:
                    if k in context and context[k] is not None:
                        useful[k] = context[k]
            ctx_str = (
                "Données contextuelles disponibles : "
                + ", ".join(f"{k}={v}" for k, v in useful.items()) + "."
                if useful else
                "Aucune donnée supplémentaire disponible."
            )
            self._send_clarification_response(
                answers={},
                founder_text=ctx_str + " Procédez avec les données existantes.",
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
            logger.info(
                "[finance_comm] fallback auto-response sent to %s "
                "(%d question(s) unanswered — LLM unavailable or no answers found)",
                sender, len(unanswered),
            )
            return

        # Store remaining questions + sender for when the founder replies
        # (only reached when answered is non-empty but unanswered is also non-empty)
        self.set_state({
            "clarification_questions":    json.dumps(unanswered, ensure_ascii=False),
            "clarification_phrased":      phrased,
            "clarification_ts":           msg.get("timestamp", ""),
            "clarification_context":      json.dumps(msg.get("context", {}), ensure_ascii=False),
            "clarification_status":       "pending",
            "clarification_auto_answers": json.dumps(answered, ensure_ascii=False),
            "clarification_sender":       sender,   # ← who asked; we reply to them
        })

    # ── LLM: answer questions from stored context ─────────────────────────────

    def _auto_answer(self, questions: List[str], context: Dict) -> Dict[str, Optional[str]]:
        """
        Use LLM to match each question to available context data.
        Returns {question → answer_or_None}.
        """
        useful_keys = [
            "burn_rate", "cash_balance", "monthly_revenue", "n_clients", "prix_client",
            "churn_rate", "marketing_budget", "new_clients_month", "cogs",
            "secteur", "pays", "revenue_history", "hypotheses",
            "intent_fundraising", "months_data",
        ]
        known = {
            k: v for k, v in context.items()
            if k in useful_keys and v is not None and v != []
        }

        if not known:
            return {q: None for q in questions}

        system = (
            "Tu es un agent financier. Tu disposes des données financières d'une startup. "
            "Pour chaque question, détermine si tu peux répondre à partir des données disponibles. "
            "Cite les chiffres exacts. Si tu ne peux pas répondre, réponds null.\n\n"
            "Réponds UNIQUEMENT avec un JSON valide :\n"
            '{"answers": [{"question": "...", "answer": "..." | null}]}'
        )
        prompt = (
            f"Données disponibles :\n{json.dumps(known, ensure_ascii=False, indent=2)}\n\n"
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
            logger.warning("[finance_comm] could not parse LLM auto-answer: %s", exc)
            return {q: None for q in questions}

    # ── Send clarification response ───────────────────────────────────────────

    def _send_clarification_response(
        self,
        answers: Dict[str, str],
        founder_text: str,
        original_msg: Dict,
        autonomous: bool = False,
    ) -> None:
        """
        Publish a finance.clarification_response to whichever agent asked.
        The recipient is taken from original_msg["from"] — NOT hardcoded.
        """
        context  = original_msg.get("context", {})
        source   = "auto (contexte financier)" if autonomous else "fondateur"
        # Reply to whoever sent the clarification request
        requester = original_msg.get("from", "investment_agent")

        response = {
            "message_id": str(uuid.uuid4()),
            "type":       "finance.clarification_response",
            "from":       "finance_agent",
            "to":         [requester],                      # ← dynamic, not hardcoded
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    context,
            "payload": {
                "data": {
                    "founder_answer": founder_text,
                    "answers":        answers,
                    "source":         source,
                },
                "recommendation": founder_text,
            },
            "confidence": 0.9 if autonomous else 0.85,
            "metadata": {
                "priority":          "high",
                "requires_response": True,
                "tags":              ["clarification", source],
            },
        }
        self.publish(response)
        logger.info(
            "[finance_comm] clarification_response → %s (%s, %d answers)",
            requester, source, len(answers),
        )

    # ── Called by app.py when founder answers remaining questions ─────────────

    def answer_clarification(self, founder_answer: str) -> None:
        """
        Founder has answered the questions the agent couldn't answer itself.
        Combines founder answer with any auto-answers, sends ONE combined response
        to whoever originally asked (stored in clarification_sender).
        """
        state        = self.get_state()
        context      = json.loads(state.get("clarification_context", "{}"))
        auto_answers = json.loads(state.get("clarification_auto_answers", "{}"))
        sender       = state.get("clarification_sender", "investment_agent")

        parts: List[str] = []
        if auto_answers:
            parts.append(
                "Données du contexte financier : "
                + "; ".join(f"{q}: {a}" for q, a in auto_answers.items())
            )
        parts.append(f"Réponse du fondateur : {founder_answer}")
        combined_text = "\n".join(parts)

        # Pass sender through so _send_clarification_response routes correctly
        original_msg = {"context": context, "from": sender}
        self._send_clarification_response(
            answers=auto_answers,
            founder_text=combined_text,
            original_msg=original_msg,
            autonomous=False,
        )
        self.set_state({"clarification_status": "answered"})
        logger.info(
            "[finance_comm] combined response sent to %s (%d auto + founder)",
            sender, len(auto_answers),
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

_instance: Optional[FinanceCommAgent] = None
_lock = threading.Lock()


def get_finance_bus_publisher() -> FinanceCommAgent:
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = FinanceCommAgent()
            _instance.start()
            logger.info("[finance_comm] thread started")
    return _instance
