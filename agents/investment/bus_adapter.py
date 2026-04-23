"""
agents/investment/bus_adapter.py
=================================
LLM-driven A2A negotiation protocol:

  1. finance_agent  →  investment_agent   financial_analysis
  2. investment_agent → finance_agent     investment.clarification_request  (only if LLM detects red flags)
  3. finance_agent  →  investment_agent   finance.clarification_response    (only if step 2 happened)
  4. investment_agent → finance_agent     investment.recommendation (final)

Step 2-3 are skipped entirely when the LLM finds the data unambiguous.
The LLM decides what to ask and whether to ask — no hardcoded thresholds.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from a2a_bus.comm_agent import CommAgent
from agents.investment.main import InvestmentAgent
from agents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME

logger = logging.getLogger(__name__)

_instance: "InvestmentBusAdapter | None" = None
_lock = threading.Lock()


def get_investment_bus_adapter() -> "InvestmentBusAdapter":
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = InvestmentBusAdapter()
            _instance.start()
            logger.info("[InvestmentBusAdapter] started")
    return _instance


class InvestmentBusAdapter(CommAgent):
    AGENT_ID = "investment_agent"

    # Red-flag thresholds that trigger a clarification round
    _HIGH_BURN_RATIO   = 0.15   # burn > 15% of annual revenue → ask about path to profitability
    _LOW_RUNWAY        = 12     # runway < 12 months → ask about bridge plan
    _HIGH_FUNDING_RATIO = 0.30  # funding > 30% of valuation → ask about dilution tolerance

    def __init__(self):
        super().__init__()
        self._agent = InvestmentAgent()
        self._llm = ChatOpenAI(
            model=MODEL_NAME, base_url=BASE_URL, api_key=TOKENFACTORY_API_KEY,
            temperature=0.3, max_tokens=400,
        )
        # pending clarification state keyed by project_id
        self._pending: dict[str, dict] = {}
        self._pending_lock = threading.Lock()

    # ── Message dispatcher (autonomous — agent decides whether to engage) ─────

    def _process(self, msg: dict) -> None:
        """
        Autonomous message processing.

        The investment agent receives ALL broadcast messages from the finance agent.
        It does NOT blindly process every message — it first decides independently:
          "Given this message content, is it relevant to my investment specialty?
           Do I have meaningful value to add? Should I engage or stay silent?"

        This is the correct autonomous agent pattern:
          - The finance agent broadcasts to everyone
          - Each specialist agent decides for itself whether to respond
          - Staying silent is a valid and correct decision
        """
        msg_type = msg.get("type", "")

        if msg_type == "financial_analysis":
            should, reason = self._should_engage(msg)
            if should:
                logger.info("[InvestmentBusAdapter] engaging: %s", reason)
                self._handle_financial_analysis(msg)
            else:
                logger.info("[InvestmentBusAdapter] staying silent: %s", reason)

        elif msg_type == "finance.clarification_response":
            # Always handle our own clarification responses
            self._handle_clarification_response(msg)

        else:
            logger.debug("[InvestmentBusAdapter] ignoring unrecognised type=%s", msg_type)

    def _should_engage(self, msg: dict) -> tuple[bool, str]:
        """
        Autonomous engagement decision.

        The investment agent reads the message content and uses its LLM to decide:
          - Does this analysis have enough data for a meaningful investment assessment?
          - Is the startup's situation within the scope of investment analysis?
          - Would staying silent be more appropriate? (e.g. empty payload, test message)

        Returns (should_engage: bool, reason: str).
        Falls back to True if LLM is unavailable — better to engage than miss.
        """
        data = msg.get("payload", {}).get("data", {})
        kpis = data.get("kpis", {}) or {}
        mc   = data.get("monte_carlo", {}) or {}

        # Hard filter: completely empty payload — nothing to analyse
        if not data:
            return False, "payload is empty — nothing to analyse"

        # Hard filter: no financial data at all
        has_any_financials = any(
            kpis.get(k) for k in ["mrr", "arr", "runway_months", "burn_net", "burn_rate_raw"]
        )
        if not has_any_financials:
            return False, "no financial KPIs present — cannot make investment assessment"

        # LLM-driven decision: agent reasons about its own relevance
        runway      = kpis.get("runway_months", "?")
        mrr         = kpis.get("mrr", "?")
        proba       = mc.get("proba_survie_12m", "?")
        secteur     = data.get("secteur", "?")
        phase       = data.get("phase", "?")
        cash_alert  = kpis.get("cash_out_alert", "")
        gross_margin= kpis.get("gross_margin_pct", "?")
        ltv_cac     = kpis.get("ltv_cac_ratio", "?")

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "Tu es un agent d'investissement autonome spécialisé dans l'analyse "
                 "de startups. Tu reçois des analyses financières diffusées à tous les agents. "
                 "Décide si TU dois t'engager et fournir une recommandation d'investissement, "
                 "ou rester silencieux.\n\n"
                 "IMPORTANT : runway_months=null/None signifie que la startup est CASH-FLOW POSITIF "
                 "(revenus > dépenses) — ce n'est PAS une donnée manquante, c'est un signal POSITIF. "
                 "De même, cash_out_alert='RENTABLE' confirme la rentabilité.\n\n"
                 "Engage-toi si : les données financières sont suffisantes pour évaluer "
                 "le potentiel d'investissement (MRR, survie, secteur, rentabilité).\n"
                 "Reste silencieux UNIQUEMENT si : le payload est vide ou totalement inexploitable.\n\n"
                 "Réponds UNIQUEMENT avec ce JSON : "
                 "{{\"engage\": true/false, \"reason\": \"explication courte en français\"}}"),
                ("user",
                 f"Secteur: {secteur} | Phase: {phase}\n"
                 f"MRR: {mrr} | Runway: {runway} mois | cash_out_alert: {cash_alert}\n"
                 f"Gross Margin: {gross_margin}% | LTV/CAC: {ltv_cac}x | Survie 12m: {proba}"),
            ])
            response = (prompt | self._llm).invoke({})
            raw = response.content.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(raw[start:end])
                engage = bool(parsed.get("engage", True))
                reason = str(parsed.get("reason", ""))
                return engage, reason
        except Exception as exc:
            logger.debug("[InvestmentBusAdapter] LLM engagement decision failed: %s", exc)

        # Safe fallback: engage (never miss a real analysis due to LLM failure)
        return True, "LLM unavailable — engaging by default"

    # ── Round 1 → 2 (or straight to 4) ──────────────────────────────────────

    def _handle_financial_analysis(self, msg: dict) -> None:
        logger.info("[InvestmentBusAdapter] Round 1 received: financial_analysis")
        try:
            finance_data, marketing_data = self._extract_inputs(msg)
            project_id = msg.get("context", {}).get("project_id", "default")
            session_id = msg.get("context", {}).get("session_id", "")

            # Detect red flags — questions + natural-language phrasing in one LLM call
            questions, phrased = self._detect_red_flags(finance_data, marketing_data)

            if questions:
                # Clarification round: ask before final analysis
                with self._pending_lock:
                    self._pending[project_id] = {
                        "finance_data":   finance_data,
                        "marketing_data": marketing_data,
                        "session_id":     session_id,
                        "original_msg":   msg,
                    }
                clarification_msg = self._build_clarification_request(
                    questions, phrased, project_id, session_id, msg
                )
                self.publish(clarification_msg)
                logger.info("[InvestmentBusAdapter] Round 2: sent clarification_request (%d questions)", len(questions))
            else:
                # No red flags → go straight to final recommendation
                self._run_analysis_and_publish(finance_data, marketing_data, project_id, session_id, msg)

        except Exception as e:
            logger.exception("[InvestmentBusAdapter] error in round 1: %s", e)
            self._publish_error(msg, str(e))

    # ── Round 3 → 4 ──────────────────────────────────────────────────────────

    def _handle_clarification_response(self, msg: dict) -> None:
        logger.info("[InvestmentBusAdapter] Round 3 received: clarification_response")
        project_id = msg.get("context", {}).get("project_id", "default")
        with self._pending_lock:
            pending = self._pending.pop(project_id, None)

        if pending is None:
            logger.warning("[InvestmentBusAdapter] no pending state for project_id=%s", project_id)
            return

        try:
            # Accept either structured answers dict or plain founder text
            payload      = msg.get("payload", {})
            data         = payload.get("data", {})
            founder_text = data.get("founder_answer") or payload.get("recommendation", "")
            answers      = data.get("answers", {})
            finance_data = {**pending["finance_data"], **(answers if answers else {}),
                            "founder_clarification": founder_text}
            marketing_data = pending["marketing_data"]
            session_id     = pending["session_id"]
            original_msg   = pending["original_msg"]

            self._run_analysis_and_publish(
                finance_data, marketing_data, project_id, session_id, original_msg
            )
        except Exception as e:
            logger.exception("[InvestmentBusAdapter] error in round 3: %s", e)
            self._publish_error(msg, str(e))

    # ── Core analysis ─────────────────────────────────────────────────────────

    def _run_analysis_and_publish(self, finance_data, marketing_data,
                                   project_id, session_id, original_msg):
        result = self._agent.analyze(
            finance_data=finance_data,
            marketing_data=marketing_data,
            project_id=project_id,
        )
        a2a_msg = result.get("a2a_message") or self._build_a2a(result, project_id, session_id)
        a2a_msg["to"]        = ["finance_agent"]
        a2a_msg["timestamp"] = datetime.now(timezone.utc).isoformat()  # always fresh
        self.publish(a2a_msg)
        logger.info("[InvestmentBusAdapter] Round 4: sent investment.recommendation")

        # Bridge: update the HTTP A2A task state so tasks/get returns "completed"
        # Uses HTTP (not in-process import) because bus_adapter runs in a separate
        # process from the uvicorn a2a_server — in-process imports modify the wrong _tasks dict.
        a2a_task_id = original_msg.get("context", {}).get("a2a_task_id") or project_id
        if a2a_task_id:
            self._update_a2a_task_state(a2a_task_id, "completed")

    # ── Red-flag detector ─────────────────────────────────────────────────────

    def _detect_red_flags(self, finance_data: dict, marketing_data: dict) -> tuple[list[str], str]:
        """
        Use LLM to decide which questions (if any) to ask the finance agent,
        and produce the natural-language phrasing in the same call.

        Returns (questions, phrased_message).
        questions is empty when the data is clear enough to proceed directly.
        Falls back to deterministic threshold rules if the LLM is unavailable.
        """
        rev   = finance_data.get("projected_revenue", 0)
        burn  = finance_data.get("monthly_burn_rate", 0)
        run   = finance_data.get("runway_months", 18)
        track = finance_data.get("traction_score", 0)

        # ── LLM-driven decision (questions + phrasing in one call) ────────────
        try:
            summary = (
                f"Revenus annuels projetés : {rev:,.0f} TND\n"
                f"Burn mensuel : {burn:,.0f} TND\n"
                f"Runway : {run:.1f} mois\n"
                f"Traction score : {track:.2f}\n"
                f"Secteur : {marketing_data.get('industry', '?')}\n"
                + (f"Burn/revenu annuel ratio : {(burn * 12) / max(rev, 1):.1%}" if rev > 0 else "Pas de revenu")
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "Tu es un analyste d'investissement expérimenté. "
                 "Examine les données financières d'une startup et détermine "
                 "si tu as besoin de clarifications avant de faire une recommandation.\n\n"
                 "Si les données sont claires, réponds avec ce JSON exactement : "
                 "{{\"questions\": [], \"message\": \"\"}}\n\n"
                 "Sinon, génère 1-2 questions précises et un message professionnel en français. "
                 "Réponds UNIQUEMENT avec un JSON valide :\n"
                 "{{\"questions\": [\"question1\"], \"message\": \"message naturel pour le fondateur\"}}"),
                ("user", summary),
            ])
            response = (prompt | self._llm).invoke({})
            raw = response.content.strip()
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start >= 0 and end > start:
                parsed    = json.loads(raw[start:end])
                questions = [str(q).strip() for q in parsed.get("questions", []) if q and str(q).strip()]
                phrased   = parsed.get("message", "").strip()
                if not phrased and questions:
                    phrased = "\n".join(f"• {q}" for q in questions)
                logger.info(
                    "[InvestmentBusAdapter] LLM decided: %d clarification questions",
                    len(questions),
                )
                return questions, phrased
        except Exception as exc:
            logger.warning("[InvestmentBusAdapter] LLM red-flag check failed, using rules: %s", exc)

        # ── Deterministic fallback (only triggered by actual thresholds) ───────
        questions = []

        if burn > 0 and rev > 0 and (burn * 12) / max(rev, 1) > self._HIGH_BURN_RATIO:
            questions.append(
                f"Le burn annuel ({burn * 12:,.0f} TND) représente "
                f"{(burn * 12) / max(rev, 1):.0%} du revenu annuel. "
                "Quels sont les principaux postes de dépenses et lesquels sont compressibles ?"
            )

        if burn > 0 and rev == 0:
            questions.append(
                "Aucun revenu récurrent n'est encore enregistré. "
                "Avez-vous des lettres d'intention ou des contrats signés en pipeline ?"
            )

        if 0 < run < self._LOW_RUNWAY:
            questions.append(
                f"La runway est de {int(run)} mois. "
                "Quel est votre plan de contingence si la levée prend plus de temps que prévu ?"
            )

        phrased = "\n".join(f"• {q}" for q in questions)
        return questions, phrased

    # ── Message builders ──────────────────────────────────────────────────────

    def _build_clarification_request(self, questions: list[str], phrased: str,
                                      project_id: str, session_id: str,
                                      original_msg: dict) -> dict:
        return {
            "message_id": str(uuid.uuid4()),
            "type":       "investment.clarification_request",
            "from":       "investment_agent",
            "to":         ["finance_agent"],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    original_msg.get("context", {"project_id": project_id, "session_id": session_id}),
            "payload": {
                "data": {
                    "questions":       questions,
                    "questions_count": len(questions),
                },
                "recommendation": phrased,
            },
            "confidence": 0.0,
            "metadata": {"priority": "high", "requires_response": True, "tags": ["clarification"]},
        }

    def _build_a2a(self, result: dict, project_id: str, session_id: str) -> dict:
        return {
            "message_id": str(uuid.uuid4()),
            "type":       "investment.recommendation",
            "from":       "investment_agent",
            "to":         ["finance_agent"],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    {"project_id": project_id, "session_id": session_id},
            "payload": {
                "data":           result.get("data", {}),
                "recommendation": result.get("recommendation", ""),
            },
            "confidence": result.get("confidence_score", 0.0),
            "metadata":   {"priority": "high", "requires_response": False, "tags": ["investment"]},
        }

    def _publish_error(self, original_msg: dict, error: str) -> None:
        self.publish({
            "message_id": str(uuid.uuid4()),
            "type":       "investment.error",
            "from":       "investment_agent",
            "to":         ["finance_agent"],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "context":    original_msg.get("context", {}),
            "payload":    {"data": {"error": error}, "recommendation": "Analysis failed."},
            "confidence": 0.0,
            "metadata":   {"priority": "high", "requires_response": False, "tags": []},
        })
        a2a_task_id = original_msg.get("context", {}).get("a2a_task_id")
        if a2a_task_id:
            self._update_a2a_task_state(a2a_task_id, "failed")

    def _update_a2a_task_state(self, task_id: str, state: str) -> None:
        """
        Update the task state in the a2a_server process via its internal HTTP endpoint.

        This is needed because bus_adapter runs in the run_mocks process (separate from
        the uvicorn a2a_server process).  Direct in-process import modifies the wrong
        in-memory _tasks dict and has no effect on what tasks/get returns.
        """
        import os as _os
        import httpx as _httpx
        a2a_url = _os.getenv("INVESTMENT_AGENT_URL", "http://localhost:8002")
        try:
            _httpx.post(
                f"{a2a_url}/internal/tasks/{task_id}/state/{state}",
                timeout=2.0,
            )
            logger.debug("[InvestmentBusAdapter] task %s → %s (via HTTP)", task_id, state)
        except Exception as exc:
            logger.debug("[InvestmentBusAdapter] could not update task state via HTTP: %s", exc)

    # ── Input extraction ──────────────────────────────────────────────────────

    def _extract_inputs(self, msg: dict) -> tuple[dict, dict]:
        data = msg.get("payload", {}).get("data", {})
        kpis = data.get("kpis", {})          # keys: burn_net, runway_months, mrr, arr, cac, ltv…
        mc   = data.get("monte_carlo", {})   # keys: p10, p50, p90, proba_survie_12m…

        burn_net = float(kpis.get("burn_net") or 0)      # negative = burning cash
        arr      = float(kpis.get("arr") or 0)
        mrr      = float(kpis.get("mrr") or 0)
        runway   = float(kpis.get("runway_months") or 18)
        annual_rev = arr or mrr * 12

        finance_data = {
            "projected_revenue":   annual_rev,
            "revenue_growth_rate": 0.5,
            "monthly_burn_rate":   abs(burn_net),
            "funding_needed":      abs(burn_net) * min(runway, 18),
            "runway_months":       runway,
            "implied_valuation":   0,
            "traction_score":      float(mc.get("proba_survie_12m") or 0.5),
            "has_export":          False,
            "company_age":         3,
        }
        marketing_data = {
            "industry":                 data.get("secteur") or "tech",
            "total_addressable_market": 0,
            "team_score":               0.5,
            "product_score":            0.5,
            "market_score":             0.5,
        }
        return finance_data, marketing_data
