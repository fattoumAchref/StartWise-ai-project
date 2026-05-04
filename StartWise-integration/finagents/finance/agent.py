"""
agents/finance/agent.py
=======================
Autonomous Finance Agent.

What makes this a *real* agent:

  GOAL       — produce a complete, confident financial analysis for a startup
               founder and delegate the result to the investment agent.

  AUTONOMY   — two explicit LLM-driven decision points:
               1. After parsing: "Do I have enough data to run the analysis?"
                  → If not: generate contextual clarification questions in French,
                    transition task to 'input-required', wait for founder reply.
               2. After analysis: "Is confidence acceptable (≥ 0.35)?"
                  → If not: identify the ONE most impactful missing data point,
                    transition task to 'input-required' again.

  TOOL USE   — calls the existing calcul_tools/pipeline deterministically
               (no LLM math — correct by design). LLM is only used for
               reasoning at decision points, not for calculation.

  MEMORY     — multi-turn: the full conversation history is preserved inside
               the Task object and re-used for context on each clarification round.

  DELEGATION — forwards the finished A2A message to the investment agent via
               the existing Redis bus (backwards compatible — investment agent
               interface is unchanged).

Task state transitions managed here:
  submitted → working → [input-required ⇄ working] → completed | failed
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from finagents.finance.protocol_models import (
    Artifact,
    DataPart,
    Message,
    Task,
    TaskStatus,
    TextPart,
)

logger = logging.getLogger(__name__)

# ── Terminal visibility — ensure our logs show in uvicorn output ──────────────
_root_logger = logging.getLogger()
if not _root_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s", "%H:%M:%S"))
    _root_logger.addHandler(_h)
logging.getLogger("finagents").setLevel(logging.DEBUG)

_SEP = "─" * 68


def _emit(label: str, task_id: str = "", **fields) -> None:
    """Print a clearly visible structured agent thought block to the terminal."""
    tid = f"  task={task_id[:14]}" if task_id else ""
    print(f"\n{_SEP}", flush=True)
    print(f"[FinanceAgent]  {label}{tid}", flush=True)
    for k, v in fields.items():
        print(f"  {k:<26} {v}", flush=True)
    print(_SEP, flush=True)


# ── LLM helper (mirrors app.py _call_llm_text) ───────────────────────────────

_LLM_URL   = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api") + "/chat/completions"
_LLM_KEY   = os.getenv("ESPRIT_API_KEY", "")
_LLM_MODEL = os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"))


def _call_llm(messages: List[Dict], max_tokens: int = 400) -> str:
    """Call the ESPRIT LLM. Returns empty string on any failure (never raises)."""
    if not _LLM_KEY:
        logger.debug("[FinanceAgent] ESPRIT_API_KEY not set — skipping LLM call")
        return ""
    try:
        r = httpx.post(
            _LLM_URL,
            headers={
                "Authorization": f"Bearer {_LLM_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": _LLM_MODEL,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
            timeout=30.0,
            verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("[FinanceAgent] LLM call failed: %s", exc)
        return ""


# ── Finance Agent ─────────────────────────────────────────────────────────────

class FinanceAgent:
    """
    Autonomous finance agent.

    Public interface:
        process_task(task)  → call for a brand-new task
        continue_task(task) → call when founder answered an 'input-required' task
    """

    # Minimum confidence score to complete without asking for more data
    MIN_CONFIDENCE: float = 0.35

    # Hard cap on clarification rounds — prevents infinite loops
    MAX_CLARIFICATION_ROUNDS: int = 2

    # ── Public API ────────────────────────────────────────────────────────────

    def process_task(self, task: Task) -> Task:
        """Entry point for a new task (state: submitted → working → ...)."""
        task.status = TaskStatus(state="working")

        # Clear stale A2A conversation log and investment state so the UI never
        # shows results from a previous analysis alongside a new one — even if
        # the new task stops early at DP1 before the pipeline runs.
        self._clear_a2a_state()

        user_text = task.get_user_text()
        if not user_text.strip():
            return self._fail(task, "Aucune donnée fournie.")

        try:
            return self._run(task, user_text)
        except Exception as exc:
            logger.exception("[FinanceAgent] unexpected error in task %s", task.id)
            return self._fail(task, str(exc))

    def continue_task(self, task: Task) -> Task:
        """
        Resume a task that was in 'input-required'.
        Re-parses the *full* conversation history so nothing is lost.
        """
        task.status = TaskStatus(state="working")
        full_text = task.all_user_text()

        try:
            return self._run(task, full_text)
        except Exception as exc:
            logger.exception("[FinanceAgent] unexpected error continuing task %s", task.id)
            return self._fail(task, str(exc))

    # ── Core reasoning loop ───────────────────────────────────────────────────

    def _run(self, task: Task, input_text: str) -> Task:
        """
        The agent's reasoning loop.

        Step 1  — parse founder input into FinancialContext
        Step 2  — validate data quality
        *** DECISION POINT 1 ***: enough data? → else input-required
        Step 3  — fetch sector benchmarks
        Step 4  — run full deterministic analysis pipeline
        *** DECISION POINT 2 ***: confidence acceptable? → else input-required
        Step 5  — delegate to investment agent
        Step 6  — complete task with artifacts
        """

        # ── Step 1: Parse ─────────────────────────────────────────────────────
        from finagents.finance.tools.parser import parse_founder_input

        _ACCUMULATE_FIELDS = (
            "burn_rate", "cash_balance", "monthly_revenue", "n_clients",
            "prix_client", "churn_rate", "secteur", "pays",
            "marketing_budget", "cogs", "new_clients_month",
        )

        # Build known_context from the accumulated parent so the LLM can resolve
        # relative answers like "j'ai perdu 3 clients" when n_clients is already known.
        parent_ctx = task.metadata.get("_parent_context")
        known_context: dict = {}
        if parent_ctx is not None:
            known_context = {
                f: getattr(parent_ctx, f)
                for f in _ACCUMULATE_FIELDS
                if getattr(parent_ctx, f, None) is not None
            }

        context = parse_founder_input(input_text, known_context=known_context or None)

        # Fill in any fields the parser missed on this turn using the accumulated
        # context from all previous turns (_parent_context is set by process_ctx).
        # This is critical for short block answers ("5000 TND") that don't carry
        # enough text context for the LLM parser to re-extract all prior fields.
        if parent_ctx is not None:
            carry = {
                f: getattr(parent_ctx, f)
                for f in _ACCUMULATE_FIELDS
                if getattr(context, f, None) is None and getattr(parent_ctx, f, None) is not None
            }
            if carry:
                context = dataclasses.replace(context, **carry)
                logger.debug("[FinanceAgent] task=%s carried fields from parent: %s", task.id, list(carry))

        _emit(
            "STEP 1 — PARSE COMPLETE", task.id,
            phase=getattr(context, "phase_hint", "?"),
            secteur=getattr(context, "secteur", "—"),
            burn_rate=getattr(context, "burn_rate", None),
            cash_balance=getattr(context, "cash_balance", None),
            monthly_revenue=getattr(context, "monthly_revenue", None),
            n_clients=getattr(context, "n_clients", None),
            churn_rate=getattr(context, "churn_rate", None),
            known_ctx_fields=list(known_context.keys()) if known_context else "none (first turn)",
            carried_fields=list(carry.keys()) if parent_ctx and carry else "—",
        )
        logger.info(
            "[FinanceAgent] task=%s parsed — phase=%s secteur=%s",
            task.id,
            getattr(context, "phase", "?"),
            getattr(context, "secteur", "?"),
        )

        # ── Step 2: Validate ──────────────────────────────────────────────────
        from finagents.finance.pipeline.validate_inputs import validate_inputs
        validation = validate_inputs(context)

        # ── DECISION POINT 1 — do I have enough data? ─────────────────────────
        rounds = task.metadata.get("clarification_rounds", 0)
        log: List[Dict] = task.metadata.setdefault("agent_log", [])

        # Store intermediate refs for app.py to extract (skipped in serialisation)
        task.metadata["_context"]    = context
        task.metadata["_validation"] = validation

        if not validation.is_valid and rounds < self.MAX_CLARIFICATION_ROUNDS:
            questions = self._reason_about_missing_data(validation, context, task)
            if questions:
                log.append({
                    "dp":       "DP1",
                    "decision": "input-required",
                    "reason":   "champs critiques manquants : "
                                + ", ".join(getattr(validation, "missing_critical", []) or []),
                    "questions": questions,
                })
                task.metadata["clarification_rounds"] = rounds + 1
                _emit(
                    "DECISION POINT 1 — INPUT REQUIRED", task.id,
                    round=f"{rounds + 1}/{self.MAX_CLARIFICATION_ROUNDS}",
                    missing_critical=", ".join(getattr(validation, "missing_critical", []) or []),
                    data_quality_score=getattr(validation, "data_quality_score", "?"),
                    questions_asked=questions,
                )
                return self._ask_clarification(task, questions)

        _emit(
            "DECISION POINT 1 — PROCEED (enough data)", task.id,
            is_valid=validation.is_valid,
            data_quality_score=getattr(validation, "data_quality_score", "?"),
            missing_fields=getattr(validation, "missing_critical", []),
            round=rounds,
        )
        log.append({
            "dp":       "DP1",
            "decision": "proceed",
            "reason":   "données suffisantes pour l'analyse",
        })

        # ── Step 3: Benchmarks ────────────────────────────────────────────────
        benchmarks = None
        try:
            from finagents.finance.tools.benchmark_fetcher import fetch_benchmarks
            benchmarks = fetch_benchmarks(context)
        except Exception as exc:
            logger.warning("[FinanceAgent] benchmark fetch failed (non-fatal): %s", exc)

        # ── Step 4: Full analysis pipeline ────────────────────────────────────
        from finagents.finance.pipeline.orchestrator import run_analysis_pipeline
        result = run_analysis_pipeline(context, benchmarks=benchmarks)
        result["context"]    = context
        result["benchmarks"] = benchmarks

        confidence_score: float = (
            getattr(result.get("confidence"), "score", 0.0) or 0.0
        )

        # Store analysis + benchmarks refs for app.py extraction (skipped in serialisation)
        task.metadata["_analysis"]    = result
        task.metadata["_benchmarks"]  = benchmarks

        kpis = result.get("kpis")
        _emit(
            "STEP 4 — PIPELINE COMPLETE", task.id,
            confidence_score=f"{confidence_score:.0%}",
            runway_months=getattr(kpis, "runway_months", "—"),
            mrr=getattr(kpis, "mrr", "—"),
            gross_margin=f"{getattr(kpis, 'gross_margin_pct', None):.1f}%" if getattr(kpis, 'gross_margin_pct', None) is not None else "—",
            ltv_cac=f"{getattr(kpis, 'ltv_cac_ratio', None):.2f}x" if getattr(kpis, 'ltv_cac_ratio', None) is not None else "—",
            cash_alert=getattr(kpis, "cash_out_alert", "—"),
            phase=getattr(result.get("phase"), "value", result.get("phase", "?")),
        )

        # ── DECISION POINT 2 — is confidence acceptable? ──────────────────────
        if confidence_score < self.MIN_CONFIDENCE and rounds < self.MAX_CLARIFICATION_ROUNDS:
            question = self._reason_about_low_confidence(context, result, confidence_score)
            if question:
                log.append({
                    "dp":       "DP2",
                    "decision": "input-required",
                    "reason":   f"confiance {confidence_score:.0%} < seuil {self.MIN_CONFIDENCE:.0%}",
                    "questions": [question],
                })
                task.metadata["clarification_rounds"] = rounds + 1
                _emit(
                    "DECISION POINT 2 — CONFIDENCE TOO LOW", task.id,
                    confidence=f"{confidence_score:.0%}",
                    threshold=f"{self.MIN_CONFIDENCE:.0%}",
                    round=f"{rounds + 1}/{self.MAX_CLARIFICATION_ROUNDS}",
                    question_asked=question,
                )
                return self._ask_clarification(task, [question])

        _emit(
            "DECISION POINT 2 — PROCEED (confidence ok)", task.id,
            confidence=f"{confidence_score:.0%}",
            threshold=f"{self.MIN_CONFIDENCE:.0%}",
        )
        log.append({
            "dp":       "DP2",
            "decision": "proceed",
            "reason":   f"confiance {confidence_score:.0%} ≥ seuil {self.MIN_CONFIDENCE:.0%}",
        })

        # ── Step 5: Delegate to all relevant specialist agents ───────────────
        self._delegate_to_agents(result)

        # ── Step 6: Complete ──────────────────────────────────────────────────
        return self._complete(task, result, context)

    # ── Reasoning methods (LLM at decision points only) ──────────────────────

    def _reason_about_missing_data(
        self,
        validation,
        context,
        task: Task,
    ) -> List[str]:
        """
        DECISION POINT 1.

        Agent reasons: "I have missing or incoherent data.
        What specific questions should I ask the founder?"

        Uses LLM to generate natural, contextual questions in French.
        Falls back to validation's pre-built questions if LLM is unavailable.
        """
        missing      = list(getattr(validation, "missing_critical", None) or [])
        incoherences = list(getattr(validation, "incoherences", None) or [])
        already_asked: set = set(task.metadata.get("already_asked", []))

        # Skip fields that are already set in context (parser extracted them successfully)
        # This prevents re-asking about a field the user already answered, even if the
        # missing_critical list still contains it due to a stale validation snapshot.
        FIELD_KEYWORDS = {
            "burn_rate":       "burn",
            "cash_balance":    "cash_balance",
            "monthly_revenue": "monthly_revenue",
            "n_clients":       "n_clients",
            "prix_client":     "prix_client",
            "churn_rate":      "churn",
            "secteur":         "secteur",
            "pays":            "pays",
        }
        ctx_set_fields: set[str] = set()
        for field in FIELD_KEYWORDS:
            if getattr(context, field, None) is not None:
                ctx_set_fields.add(FIELD_KEYWORDS[field])

        new_missing = [
            f for f in missing
            if f not in already_asked
            and not any(kw in f for kw in ctx_set_fields)
        ]
        if not new_missing and not incoherences:
            return []  # nothing new to ask — proceed anyway

        # Remember we asked these so we don't repeat on next round
        task.metadata["already_asked"] = list(already_asked | set(new_missing))

        # Build a summary of what the founder already provided — the LLM must NOT
        # ask about these fields again, regardless of how it phrases the question.
        provided_fields = {
            f: getattr(context, f)
            for f in ("burn_rate", "cash_balance", "monthly_revenue", "n_clients",
                      "prix_client", "churn_rate", "secteur", "pays", "marketing_budget")
            if getattr(context, f, None) is not None
        }
        provided_str = (
            ", ".join(f"{k}={v}" for k, v in provided_fields.items())
            if provided_fields else "aucun champ encore fourni"
        )

        system = (
            "Tu es un analyste financier aidant un fondateur de startup. "
            "Génère des questions claires et empathiques en français UNIQUEMENT "
            "pour les champs listés dans 'Champs manquants'. "
            "NE POSE JAMAIS de question sur les champs déjà fournis. "
            "Maximum 3 questions. "
            "Retourne UNIQUEMENT un tableau JSON : [\"question1\", \"question2\"]"
        )
        prompt = (
            f"Secteur : {getattr(context, 'secteur', 'inconnu')}\n"
            f"Champs déjà fournis (NE PAS redemander) : {provided_str}\n"
            f"Champs manquants (à demander) : {', '.join(new_missing)}\n"
            f"Incohérences détectées : {'; '.join(incoherences)}\n\n"
            "Génère les questions pour les champs manquants uniquement."
        )
        raw = _call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        )

        if raw:
            try:
                start = raw.find("[")
                end   = raw.rfind("]") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start:end])
                    questions = [str(q) for q in parsed if q][:3]
                    if questions:
                        return questions
            except (json.JSONDecodeError, ValueError):
                pass

        # Fallback: use validation's pre-built questions
        return list(getattr(validation, "questions_to_ask", None) or [])[:3]

    def _reason_about_low_confidence(
        self,
        context,
        result: Dict,
        score: float,
    ) -> Optional[str]:
        """
        DECISION POINT 2.

        Agent reasons: "My analysis confidence is too low.
        What single question would improve it most?"

        Returns one question string, or None if LLM unavailable / no improvement possible.
        """
        kpis = result.get("kpis")

        system = (
            "Tu es un analyste financier. L'analyse d'une startup a un score de confiance trop bas. "
            "Identifie UNE question précise en français dont la réponse améliorerait le plus "
            "la fiabilité de l'analyse. Retourne uniquement le texte de la question, rien d'autre."
        )
        prompt = (
            f"Score de confiance actuel : {score:.2f} (minimum requis : {self.MIN_CONFIDENCE})\n"
            f"Secteur : {getattr(context, 'secteur', 'inconnu')}\n"
            f"Runway estimé : {getattr(kpis, 'runway_months', '?')} mois\n"
            f"Qualité des données : {getattr(context, 'data_quality', '?')}\n\n"
            "Quelle est la question la plus impactante pour améliorer la fiabilité de l'analyse ?"
        )
        return _call_llm(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            max_tokens=150,
        ) or None

    # ── A2A task state transitions ────────────────────────────────────────────

    def _ask_clarification(self, task: Task, questions: List[str]) -> Task:
        """
        Transition task → 'input-required'.
        Attaches the agent's questions as a Message so the client can display them.
        """
        question_text = "\n".join(f"• {q}" for q in questions)
        agent_msg = Message(role="agent", parts=[TextPart(text=question_text)])
        task.add_message(agent_msg)
        task.status = TaskStatus(state="input-required", message=agent_msg)
        logger.info(
            "[FinanceAgent] task %s → input-required (%d questions, round %d/%d)",
            task.id, len(questions),
            task.metadata.get("clarification_rounds", 1),
            self.MAX_CLARIFICATION_ROUNDS,
        )
        return task

    def _complete(self, task: Task, result: Dict, context) -> Task:
        """
        Transition task → 'completed'.
        Attaches two artifacts:
          - 'financial-analysis' : full structured JSON result
          - 'summary'            : human-readable text summary
        """
        summary = self._build_summary(result, context)

        task.artifacts = [
            Artifact(
                name="financial-analysis",
                description="Complete startup financial analysis (KPIs, MC, scenarios, benchmarks)",
                parts=[DataPart(data=self._to_serializable(result))],
                index=0,
            ),
            Artifact(
                name="summary",
                description="Human-readable analysis summary in French",
                parts=[TextPart(text=summary)],
                index=1,
            ),
        ]
        task.add_message(Message(role="agent", parts=[TextPart(text=summary)]))
        task.status = TaskStatus(state="completed")

        logger.info(
            "[FinanceAgent] task %s → completed (confidence=%.2f, rounds=%d)",
            task.id,
            getattr(result.get("confidence"), "score", 0) or 0,
            task.metadata.get("clarification_rounds", 0),
        )
        return task

    def _fail(self, task: Task, reason: str) -> Task:
        """Transition task → 'failed'."""
        msg = Message(role="agent", parts=[TextPart(text=f"Erreur d'analyse : {reason}")])
        task.add_message(msg)
        task.status = TaskStatus(state="failed", message=msg)
        logger.error("[FinanceAgent] task %s → failed: %s", task.id, reason)
        return task

    # ── Multi-agent delegation ────────────────────────────────────────────────

    def _delegate_to_agents(self, result: Dict) -> None:
        """
        Broadcast the completed analysis to ALL registered specialist agents.

        The finance agent does NOT pre-select who should respond.
        Each specialist agent receives the full analysis and autonomously
        decides — using its own LLM reasoning — whether to engage or stay silent.

        This is the correct autonomous multi-agent pattern:
          Sender  : broadcast to all (no sender-side filtering)
          Receiver: each agent decides independently ("is this relevant to me?")

        Adding a new agent = set one env var (e.g. RISK_AGENT_URL=...).
        Zero changes to this file required.
        """
        from finagents.finance.agent_card import get_registry

        registry = get_registry()
        agents   = registry.get_all()

        if not agents:
            logger.warning("[FinanceAgent] no agents in registry — skipping delegation")
            return

        _emit(
            "STEP 5 — BROADCASTING TO SPECIALIST AGENTS",
            targets=[a["id"] for a in agents],
            count=len(agents),
        )
        logger.info(
            "[FinanceAgent] broadcasting to all %d registered agents: %s",
            len(agents),
            [a["id"] for a in agents],
        )

        for agent in agents:
            self._send_to_agent(agent, result)

    def _send_to_agent(self, agent: Dict, result: Dict) -> None:
        """
        Send the analysis to one agent — A2A HTTP first, Redis bus as fallback.
        """
        agent_id = agent["id"]

        # Build the financial payload
        a2a_msg = result.get("a2a_message")
        if a2a_msg:
            if dataclasses.is_dataclass(a2a_msg):
                msg_dict: Dict = dataclasses.asdict(a2a_msg)
            else:
                msg_dict = dict(a2a_msg)
            if "from_agent" in msg_dict and "from" not in msg_dict:
                msg_dict["from"] = msg_dict.pop("from_agent")
            financial_data = msg_dict.get("payload", {}).get("data", msg_dict)
        else:
            msg_dict       = {}
            financial_data = self._to_serializable(result)

        # ── A2A HTTP (JSON-RPC 2.0) ────────────────────────────────────────────
        url = agent["url"].rstrip("/") + "/"
        try:
            rpc_payload = {
                "jsonrpc": "2.0",
                "id":      f"delegate-{agent_id}",
                "method":  "tasks/send",
                "params": {
                    "message": {
                        "role":  "agent",
                        "parts": [{"type": "data", "mimeType": "application/json",
                                   "data": financial_data}],
                    }
                },
            }
            _emit(f"A2A HTTP → {agent_id}", url=url)
            r = httpx.post(url, json=rpc_payload, timeout=5.0, verify=False)
            if r.status_code == 200 and "result" in r.json():
                task_returned = r.json().get("result", {}).get("id", "?")
                _emit(
                    f"A2A HTTP ✓ {agent_id} — DELEGATED",
                    remote_task=task_returned,
                    status=r.json().get("result", {}).get("status", {}).get("state", "?"),
                )
                logger.info(
                    "[FinanceAgent] delegated via A2A HTTP → %s (task=%s)",
                    agent_id, task_returned,
                )
                # Log to conversation log (was previously done by pipeline.py step 8)
                self._log_sent_to_conversation(msg_dict, agent_id)
                return
            _emit(f"A2A HTTP ✗ {agent_id} — bad response", status=r.status_code, body=r.text[:120])
        except Exception as exc:
            _emit(f"A2A HTTP ✗ {agent_id} — FAILED", error=str(exc))
            logger.debug("[FinanceAgent] A2A HTTP failed for %s: %s", agent_id, exc)

        # ── Redis bus fallback (only for agents with bus_fallback=True) ────────
        if agent.get("bus_fallback") and msg_dict:
            try:
                msg_dict["to"] = [agent_id]
                from finagents.finance.bus_publisher import get_finance_bus_publisher
                get_finance_bus_publisher().publish(msg_dict)
                logger.info("[FinanceAgent] delegated via Redis bus → %s", agent_id)
            except Exception as exc:
                logger.warning("[FinanceAgent] Redis bus fallback failed for %s: %s", agent_id, exc)

    # ── Public decision method (used by app.py) ───────────────────────────────

    def decide(
        self,
        context,
        validation,
        analysis: Dict,
        task: "Task",
    ) -> List[str]:
        """
        Make autonomous decisions without re-running the pipeline.

        Called by app.py AFTER the pipeline has already run, so the
        finance agent can reason about the results and decide what to ask.

        Decision Point 1 — data sufficiency:
          If validation failed and we haven't exceeded MAX rounds,
          use LLM to generate the most useful clarification questions.

        Decision Point 2 — confidence:
          If confidence < MIN_CONFIDENCE, ask the one question that
          would help most.

        Logs every decision to task.metadata["agent_log"] for the UI.
        Updates task.status.state to reflect the decision.
        Returns list of questions to ask the founder (empty = proceed).
        """
        log: List[Dict] = task.metadata.setdefault("agent_log", [])
        rounds: int = task.metadata.get("clarification_rounds", 0)

        # ── Decision Point 1: data sufficiency ────────────────────────────────
        if not getattr(validation, "is_valid", True) and rounds < self.MAX_CLARIFICATION_ROUNDS:
            questions = self._reason_about_missing_data(validation, context, task)
            if questions:
                log.append({
                    "dp":       "DP1",
                    "decision": "input-required",
                    "reason":   "champs critiques manquants : "
                                + ", ".join(getattr(validation, "missing_critical", []) or []),
                    "questions": questions,
                })
                task.metadata["clarification_rounds"] = rounds + 1
                task.status = TaskStatus(state="input-required")
                return questions

        log.append({
            "dp":       "DP1",
            "decision": "proceed",
            "reason":   "données suffisantes pour l'analyse",
        })

        # ── Decision Point 2: confidence ──────────────────────────────────────
        conf_score: float = getattr(analysis.get("confidence"), "score", 1.0) or 1.0
        if conf_score < self.MIN_CONFIDENCE and rounds < self.MAX_CLARIFICATION_ROUNDS:
            question = self._reason_about_low_confidence(context, analysis, conf_score)
            if question:
                log.append({
                    "dp":       "DP2",
                    "decision": "input-required",
                    "reason":   f"confiance {conf_score:.0%} < seuil {self.MIN_CONFIDENCE:.0%}",
                    "questions": [question],
                })
                task.metadata["clarification_rounds"] = rounds + 1
                task.status = TaskStatus(state="input-required")
                return [question]

        log.append({
            "dp":       "DP2",
            "decision": "proceed",
            "reason":   f"confiance {conf_score:.0%} ≥ seuil {self.MIN_CONFIDENCE:.0%}",
        })
        task.status = TaskStatus(state="completed")
        return []

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _clear_a2a_state(self) -> None:
        """
        Wipe stale A2A conversation log and investment/risk Redis state so the UI
        never displays results from a previous analysis alongside the new one.
        Called at the start of every new task (process_task), before any processing.
        """
        if not os.getenv("A2A_BUS_URL"):
            return
        try:
            import redis as _r
            r = _r.Redis(decode_responses=True)
            stale = [
                "investment_rating", "investment_score", "investment_recommendation",
                "investment_reasons", "investment_msg_id", "investment_ts",
                "investment_confidence",
                "valuation", "valuation_method",
                "best_scenario", "best_scenario_raise", "best_scenario_dilution",
                "best_scenario_post_money", "best_scenario_rationale",
                "dilution_pct", "founder_after_pct",
                "clarification_questions", "clarification_phrased", "clarification_ts",
                "conflict_alert",
            ]
            pipe = r.pipeline()
            for f in stale:
                pipe.hdel("a2a:finance_agent:state", f)
            pipe.execute()
            r.delete("a2a:conversation:log")
        except Exception as exc:
            logger.debug("[FinanceAgent] could not clear A2A state: %s", exc)

    def _build_summary(self, result: Dict, context) -> str:
        """Build a concise French text summary of the completed analysis."""
        kpis       = result.get("kpis")
        confidence = result.get("confidence")
        scenarios  = result.get("scenarios")
        mc         = result.get("monte_carlo")

        lines: List[str] = ["**Analyse financière complète**\n"]

        mrr = getattr(kpis, "mrr", None)
        if mrr is not None:
            lines.append(f"- MRR : {mrr:,.0f} TND")

        runway = getattr(kpis, "runway_months", None)
        if runway is not None:
            icon = "🔴" if runway < 3 else ("🟠" if runway < 6 else "🟢")
            lines.append(f"- Runway : {runway:.1f} mois {icon}")

        ltv_cac = getattr(kpis, "ltv_cac_ratio", None)
        if ltv_cac is not None:
            lines.append(f"- LTV/CAC : {ltv_cac:.2f}")

        proba = getattr(mc, "proba_survie_12m", None)
        if proba is not None:
            lines.append(f"- Probabilité survie 12 mois : {proba:.0%}")

        conf_score = getattr(confidence, "score", None)
        conf_level = getattr(confidence, "level", "?")
        if conf_score is not None:
            lines.append(f"- Confiance analyse : {conf_level} ({conf_score:.0%})")

        if scenarios:
            rec = getattr(scenarios, "recommandation", None)
            if rec:
                lines.append(f"\n💡 {rec}")

        lines.append("\n📤 Analyse transmise à l'agent d'investissement.")
        return "\n".join(lines)

    def _log_sent_to_conversation(self, msg_dict: Dict, agent_id: str) -> None:
        """Write the outgoing A2A message to the shared Redis conversation log."""
        if not os.getenv("A2A_BUS_URL"):
            return
        try:
            import redis as _r, json as _json
            r = _r.Redis(decode_responses=True)
            r.lpush("a2a:conversation:log", _json.dumps({
                "direction":  "sent",
                "from":       "finance_agent",
                "to":         msg_dict.get("to", [agent_id]),
                "type":       msg_dict.get("type", "financial_analysis"),
                "message_id": msg_dict.get("message_id", ""),
                "timestamp":  msg_dict.get("timestamp", ""),
                "confidence": float(msg_dict.get("confidence", 0)),
            }, ensure_ascii=False))
        except Exception as exc:
            logger.debug("[FinanceAgent] could not log sent message: %s", exc)

    def _to_serializable(self, result: Dict) -> Dict:
        """
        Recursively convert dataclasses / enums to JSON-serializable dicts.
        Skips 'context' and 'a2a_message' (too large / already sent via bus).
        """
        _SKIP = {"context", "a2a_message"}

        def _safe(v: Any) -> Any:
            if v is None or isinstance(v, (str, int, float, bool)):
                return v
            if isinstance(v, list):
                return [_safe(i) for i in v]
            if isinstance(v, dict):
                return {k: _safe(val) for k, val in v.items()}
            try:
                if dataclasses.is_dataclass(v):
                    return {k: _safe(val) for k, val in dataclasses.asdict(v).items()}
            except Exception:
                pass
            if hasattr(v, "value"):  # Enum
                return v.value
            return str(v)

        return {k: _safe(v) for k, v in result.items() if k not in _SKIP}
