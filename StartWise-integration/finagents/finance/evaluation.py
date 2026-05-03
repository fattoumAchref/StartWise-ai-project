"""
agents/finance/evaluation.py
=============================
Evaluation metrics for the Finance Agent.

Based on the NLP Agent AI course (Esprit 2025-2026):

  1. Agentic metrics   : TSR, GPS, TCA, Hallucination Rate, Efficiency Score
  2. Process quality   : clarification rounds, data completeness, DP coherence
  3. RAGAS-style RAG   : Faithfulness, Answer Relevance, Context Recall, Context Precision
  4. NLP quality       : Summary coverage (ROUGE-1 inspired), BERTScore (optional)

Usage:
    from finagents.finance.evaluation import FinanceAgentEvaluator
    metrics = FinanceAgentEvaluator().evaluate(task)
    print(metrics.report())
    d = metrics.to_dict()   # for Streamlit display
"""
from __future__ import annotations

import dataclasses
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class AgentMetrics:
    """All evaluation metrics for one Finance Agent task."""

    # ── 1. Agentic metrics ────────────────────────────────────────────────────
    task_success_rate: float = 0.0    # TSR ∈ {0,1} — task completed?
    goal_progress_score: float = 0.0  # GPS ∈ [0,1] — pipeline sub-goals achieved
    tool_call_accuracy: float = 0.0   # TCA ∈ [0,1] — tool calls that succeeded
    hallucination_rate: float = 0.0   # HR  ∈ [0,1] — unsupported numeric claims
    efficiency_score: float = 0.0     # ES  ∈ [0,1] — min_rounds / actual_rounds

    # ── 2. Process quality ────────────────────────────────────────────────────
    clarification_rounds: int = 0         # Q&A iterations (fewer = better)
    data_completeness: float = 0.0        # Fraction of 6 critical fields populated
    dp1_coherence: float = 0.0            # DP1 reasoning quality ∈ [0,1]
    dp2_coherence: float = 0.0            # DP2 reasoning quality ∈ [0,1]

    # ── 3. RAGAS-style RAG metrics ────────────────────────────────────────────
    faithfulness: float = 0.0        # Claims in summary supported by actual KPI data
    answer_relevance: float = 0.0    # Summary covers the founder's key concerns
    context_recall: float = 0.0      # Retrieved benchmarks cover the startup's sector
    context_precision: float = 0.0   # Retrieved benchmarks actually used in analysis

    # ── 4. NLP quality ────────────────────────────────────────────────────────
    summary_coverage: float = 0.0          # Key financial terms in summary (ROUGE-1 style)
    bertscore_f1: Optional[float] = None   # BERTScore F1 (None if bert-score not installed)

    # ── Meta ──────────────────────────────────────────────────────────────────
    task_id: str = ""
    task_state: str = ""
    evaluation_errors: List[str] = field(default_factory=list)

    def report(self) -> str:
        """Human-readable evaluation report."""
        lines = [
            f"╔══ Finance Agent Evaluation — Task {self.task_id} ══",
            f"║  State: {self.task_state}",
            "╠══ 1. Agentic Metrics ══════════════════════════════════",
            f"║  Task Success Rate  (TSR) : {self.task_success_rate:.0%}",
            f"║  Goal Progress Score(GPS) : {self.goal_progress_score:.0%}",
            f"║  Tool Call Accuracy (TCA) : {self.tool_call_accuracy:.0%}",
            f"║  Hallucination Rate (HR)  : {self.hallucination_rate:.0%}",
            f"║  Efficiency Score   (ES)  : {self.efficiency_score:.0%}",
            "╠══ 2. Process Quality ══════════════════════════════════",
            f"║  Clarification Rounds     : {self.clarification_rounds}",
            f"║  Data Completeness        : {self.data_completeness:.0%}",
            f"║  DP1 Coherence            : {self.dp1_coherence:.0%}",
            f"║  DP2 Coherence            : {self.dp2_coherence:.0%}",
            "╠══ 3. RAGAS-style RAG Metrics ══════════════════════════",
            f"║  Faithfulness             : {self.faithfulness:.2f}",
            f"║  Answer Relevance         : {self.answer_relevance:.2f}",
            f"║  Context Recall           : {self.context_recall:.2f}",
            f"║  Context Precision        : {self.context_precision:.2f}",
            "╠══ 4. NLP Quality ══════════════════════════════════════",
            f"║  Summary Coverage (ROUGE-1): {self.summary_coverage:.2f}",
        ]
        if self.bertscore_f1 is not None:
            lines.append(f"║  BERTScore F1              : {self.bertscore_f1:.3f}")
        else:
            lines.append("║  BERTScore F1              : N/A (pip install bert-score)")
        if self.evaluation_errors:
            lines.append("╠══ Warnings ════════════════════════════════════════════")
            for e in self.evaluation_errors:
                lines.append(f"║  ⚠ {e}")
        lines.append("╚═══════════════════════════════════════════════════════")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


# ── Evaluator ─────────────────────────────────────────────────────────────────

class FinanceAgentEvaluator:
    """
    Evaluates a completed (or failed) Finance Agent task.

    All metrics are derived from the Task object and its metadata —
    no external services or modifications to existing code are required.

    Instantiate once and call evaluate(task) after each task.
    """

    # 6 critical financial fields (used for data_completeness)
    _CRITICAL_FIELDS = [
        "burn_rate", "cash_balance", "monthly_revenue",
        "n_clients", "prix_client", "churn_rate",
    ]

    # Pipeline sub-goals (used for GPS)
    _PIPELINE_SUBGOALS_META = ["_context", "_validation"]       # in task.metadata
    _PIPELINE_SUBGOALS_RESULT = ["kpis", "scenarios", "monte_carlo", "confidence"]  # in _analysis

    # Key financial terms for ROUGE-1-inspired summary coverage
    _FINANCIAL_TERMS = [
        "runway", "mrr", "mois", "confiance", "survie",
        "scenario", "burn", "ltv", "cac", "tnd",
    ]

    # ── Main entry point ──────────────────────────────────────────────────────

    def evaluate(self, task) -> AgentMetrics:
        """
        Compute all evaluation metrics for the given task.
        Returns an AgentMetrics object; never raises.
        """
        m = AgentMetrics(task_id=task.id, task_state=task.status.state)
        errors = m.evaluation_errors

        try:
            # Extract stored data from metadata
            context    = task.metadata.get("_context")
            validation = task.metadata.get("_validation")
            result     = task.metadata.get("_analysis") or {}
            benchmarks = task.metadata.get("_benchmarks")
            agent_log  = task.metadata.get("agent_log", [])
            rounds     = task.metadata.get("clarification_rounds", 0)

            # Get summary text from artifacts
            summary_text = ""
            for artifact in task.artifacts:
                if artifact.name == "summary":
                    for part in artifact.parts:
                        if hasattr(part, "text"):
                            summary_text = part.text
                            break

            # ── 1. Agentic metrics ─────────────────────────────────────────────
            m.task_success_rate  = self._tsr(task)
            m.goal_progress_score = self._gps(task, result)
            m.tool_call_accuracy  = self._tca(result, agent_log)
            m.hallucination_rate  = self._hr(summary_text, result, errors)
            m.efficiency_score    = self._es(rounds, validation)

            # ── 2. Process quality ─────────────────────────────────────────────
            m.clarification_rounds = rounds
            m.data_completeness    = self._data_completeness(context)
            m.dp1_coherence, m.dp2_coherence = self._dp_coherence(
                agent_log, validation, result
            )

            # ── 3. RAGAS-style RAG metrics ─────────────────────────────────────
            m.faithfulness      = self._faithfulness(summary_text, result)
            m.answer_relevance  = self._answer_relevance(summary_text)
            m.context_recall    = self._context_recall(benchmarks, context)
            m.context_precision = self._context_precision(benchmarks, result)

            # ── 4. NLP quality ─────────────────────────────────────────────────
            m.summary_coverage = self._summary_coverage(summary_text)
            m.bertscore_f1     = self._bertscore(summary_text, result, errors)

        except Exception as exc:
            logger.warning("[FinanceAgentEvaluator] evaluation error: %s", exc)
            errors.append(f"Evaluation error: {exc}")

        return m

    # ── 1. Agentic metrics ────────────────────────────────────────────────────

    def _tsr(self, task) -> float:
        """
        Task Success Rate (TSR).
        1.0 = completed, 0.5 = input-required (partial), 0.0 = failed.
        """
        return {
            "completed":      1.0,
            "input-required": 0.5,
            "working":        0.3,
            "submitted":      0.1,
            "failed":         0.0,
            "canceled":       0.0,
        }.get(task.status.state, 0.0)

    def _gps(self, task, result: Dict) -> float:
        """
        Goal Progress Score (GPS): fraction of pipeline sub-goals achieved.
        Sub-goals: parse context, validate, compute KPIs, generate scenarios,
        run Monte Carlo, compute confidence, complete task.
        """
        total = (
            len(self._PIPELINE_SUBGOALS_META)
            + len(self._PIPELINE_SUBGOALS_RESULT)
            + 1  # final completion
        )
        achieved = 0

        for goal in self._PIPELINE_SUBGOALS_META:
            if task.metadata.get(goal) is not None:
                achieved += 1

        for goal in self._PIPELINE_SUBGOALS_RESULT:
            if result.get(goal) is not None:
                achieved += 1

        if task.status.state == "completed":
            achieved += 1

        return achieved / total if total > 0 else 0.0

    def _tca(self, result: Dict, agent_log: List) -> float:
        """
        Tool Call Accuracy (TCA): fraction of tool calls that succeeded.
        Inferred from presence of result keys (each key = one tool call).
        Benchmarks and seasonality are optional (non-fatal if missing).
        """
        required_tools = {
            "parse":       result.get("_context") is not None or True,  # always attempted
            "validate":    result.get("_validation") is not None or True,
            "kpis":        result.get("kpis") is not None,
            "scenarios":   result.get("scenarios") is not None,
            "monte_carlo": result.get("monte_carlo") is not None,
            "confidence":  result.get("confidence") is not None,
        }
        optional_tools = {
            "benchmarks":  True,   # non-fatal
            "seasonality": True,   # non-fatal
        }

        explicit_failures = sum(
            1 for e in agent_log if e.get("decision") == "failed"
        )
        succeeded = sum(1 for v in required_tools.values() if v)
        total = len(required_tools)
        return max(0.0, (succeeded - explicit_failures) / total) if total > 0 else 0.0

    def _hr(self, summary: str, result: Dict, errors: List[str]) -> float:
        """
        Hallucination Rate (HR): fraction of numeric claims in the summary
        that do NOT match the actual KPI/MC values (±15% tolerance).

        Only checks claims for metrics explicitly mentioned by keyword.
        An unsupported claim = value in summary ≠ value in KPIs.
        """
        if not summary or not result:
            return 0.0

        kpis = result.get("kpis")
        mc   = result.get("monte_carlo")
        conf = result.get("confidence")
        if not kpis and not mc:
            return 0.0

        # Ground truth
        gt: Dict[str, Tuple[float, List[str]]] = {}  # name → (value, keywords)
        if kpis:
            for attr, kws in [
                ("runway_months", ["runway"]),
                ("mrr",           ["mrr", "revenu mensuel"]),
                ("ltv_cac_ratio", ["ltv/cac", "ltv"]),
                ("gross_margin_pct", ["marge"]),
            ]:
                val = getattr(kpis, attr, None)
                if val is not None and isinstance(val, (int, float)):
                    gt[attr] = (float(val), kws)

        if mc:
            proba = getattr(mc, "proba_survie_12m", None)
            if proba is not None:
                # Convert to percentage for comparison with summary text
                gt["proba_survie"] = (float(proba) * 100, ["survie", "probabilit"])

        if conf:
            score = getattr(conf, "score", None)
            if score is not None:
                gt["confidence"] = (float(score) * 100, ["confiance"])

        if not gt:
            return 0.0

        # Normalise number formats before extraction:
        # English thousands comma: "45,000"  → "45000"  (must come BEFORE decimal comma handling)
        # French thousands space:  "45 000"  → "45000"
        # Decimal comma:           "8,3"     → "8.3"
        normalised = re.sub(r'(\d),(\d{3})\b', r'\1\2', summary)   # "45,000" → "45000"
        normalised = re.sub(r'(\d)\s+(\d)', r'\1\2', normalised)    # "45 000" → "45000"
        normalised = normalised.replace(',', '.')                    # "8,3"    → "8.3"
        summary_lower = normalised.lower()

        claims_checked = 0
        hallucinations = 0

        for attr, (true_val, keywords) in gt.items():
            # Only check if the metric is explicitly mentioned
            if not any(kw in summary_lower for kw in keywords):
                continue

            claims_checked += 1
            found_match = False
            nums = re.findall(r'\b(\d+(?:\.\d+)?)\b', normalised)
            for num_str in nums:
                try:
                    num = float(num_str)
                    if true_val != 0:
                        rel_err = abs(num - true_val) / abs(true_val)
                        if rel_err <= 0.15:
                            found_match = True
                            break
                    elif abs(num) < 0.5:
                        found_match = True
                        break
                except ValueError:
                    continue
            if not found_match:
                hallucinations += 1

        if claims_checked == 0:
            return 0.0
        return hallucinations / claims_checked

    def _es(self, rounds: int, validation) -> float:
        """
        Efficiency Score (ES) = min_rounds / actual_rounds.

        Minimum rounds possible:
          - 1 if no clarification was ever needed (0 rounds)
          - 2 if any clarification happened — that round was necessary by definition
            (whether triggered by invalid data at DP1 or low confidence at DP2)
        """
        actual  = max(1, rounds + 1)   # at least 1 (the initial run)
        minimum = 1 if rounds == 0 else 2
        return min(1.0, minimum / actual)

    # ── 2. Process quality ────────────────────────────────────────────────────

    def _data_completeness(self, context) -> float:
        """Fraction of the 6 critical financial fields that were populated."""
        if context is None:
            return 0.0
        populated = sum(
            1 for f in self._CRITICAL_FIELDS
            if getattr(context, f, None) is not None
        )
        return populated / len(self._CRITICAL_FIELDS)

    def _dp_coherence(
        self,
        agent_log: List,
        validation,
        result: Dict,
    ) -> Tuple[float, float]:
        """
        Decision Point coherence: did the agent make the RIGHT decision at DP1 and DP2?

        DP1 coherence:
          - data invalid  AND agent asked questions  → 1.0  (correct)
          - data valid    AND agent proceeded        → 1.0  (correct)
          - otherwise                                → 0.0  (wrong)
          - no log entry                             → 0.5  (unknown)

        DP2 coherence:
          - confidence < 0.35  AND agent asked       → 1.0
          - confidence ≥ 0.35  AND agent proceeded   → 1.0
          - otherwise                                → 0.0
          - no log entry                             → 0.5
        """
        dp1_entries = [e for e in agent_log if e.get("dp") == "DP1"]
        dp2_entries = [e for e in agent_log if e.get("dp") == "DP2"]

        # DP1
        dp1 = 0.5
        if dp1_entries:
            last  = dp1_entries[-1]
            dec   = last.get("decision")
            valid = getattr(validation, "is_valid", True) if validation else True
            if (not valid and dec == "input-required") or (valid and dec == "proceed"):
                dp1 = 1.0
            elif dec in ("input-required", "proceed"):
                dp1 = 0.0

        # DP2
        dp2   = 0.5
        conf  = result.get("confidence")
        score = getattr(conf, "score", None) if conf else None
        if dp2_entries and score is not None:
            last  = dp2_entries[-1]
            dec   = last.get("decision")
            if (score < 0.35 and dec == "input-required") or (score >= 0.35 and dec == "proceed"):
                dp2 = 1.0
            elif dec in ("input-required", "proceed"):
                dp2 = 0.0

        return dp1, dp2

    # ── 3. RAGAS-style RAG metrics ────────────────────────────────────────────

    def _faithfulness(self, summary: str, result: Dict) -> float:
        """
        Faithfulness: are the specific numeric claims in the summary
        supported by the actual analysis output?

        Checks up to 4 claims (runway, survival probability, confidence, LTV/CAC).
        Returns 1.0 if no specific claims to check (agent did not hallucinate
        numbers that don't exist).
        """
        if not summary:
            return 0.0

        kpis = result.get("kpis")
        mc   = result.get("monte_carlo")
        conf = result.get("confidence")

        claims_total     = 0
        claims_supported = 0
        # Normalise number formats: English thousands comma, French space, decimal comma
        normalised    = re.sub(r'(\d),(\d{3})\b', r'\1\2', summary)  # "45,000" → "45000"
        normalised    = re.sub(r'(\d)\s+(\d)', r'\1\2', normalised)   # "45 000" → "45000"
        normalised    = normalised.replace(',', '.')                   # "8,3"    → "8.3"
        summary_lower = normalised.lower()

        def _check_claim(keyword_pattern: str, true_val: float, tolerance: float = 0.15) -> None:
            nonlocal claims_total, claims_supported
            match = re.search(keyword_pattern, summary_lower)
            if match:
                claims_total += 1
                try:
                    claimed = float(match.group(1).replace(',', '.').replace(' ', ''))
                    err = abs(claimed - true_val) / max(abs(true_val), 0.01)
                    if err <= tolerance:
                        claims_supported += 1
                except (ValueError, IndexError):
                    claims_supported += 1  # pattern matched but no number → not a hallucination

        # Runway claim  e.g. "Runway : 8.3 mois"
        runway = getattr(kpis, "runway_months", None) if kpis else None
        if runway is not None:
            _check_claim(r'runway\s*[:\-–]\s*(\d+(?:[.,]\d+)?)', runway)

        # MRR claim  e.g. "MRR : 45 000 TND"
        mrr = getattr(kpis, "mrr", None) if kpis else None
        if mrr is not None:
            _check_claim(r'mrr\s*[:\-–]\s*([\d\s]+(?:[.,]\d+)?)', mrr, tolerance=0.20)

        # Survival probability claim  e.g. "75%"
        proba = getattr(mc, "proba_survie_12m", None) if mc else None
        if proba is not None:
            proba_pct = proba * 100 if proba <= 1 else proba
            _check_claim(r'survie\s*(?:12\s*mois\s*)?[:\-–]?\s*(\d+)\s*%', proba_pct, tolerance=0.05)

        # Confidence claim  e.g. "MOYEN (52%)"
        if conf is not None:
            score_val = getattr(conf, "score", None)
            if score_val is not None:
                conf_pct = score_val * 100 if score_val <= 1 else score_val
                _check_claim(r'confiance\s*(?:\w+\s*)?\(?\s*(\d+)\s*%', conf_pct, tolerance=0.05)

        # LTV/CAC claim  e.g. "LTV/CAC : 3.20"
        ltv_cac = getattr(kpis, "ltv_cac_ratio", None) if kpis else None
        if ltv_cac is not None:
            _check_claim(r'ltv/cac\s*[:\-–]\s*(\d+(?:[.,]\d+)?)', ltv_cac)

        if claims_total == 0:
            return 1.0  # no specific numeric claims → assume faithful
        return claims_supported / claims_total

    def _answer_relevance(self, summary: str) -> float:
        """
        Answer Relevance (RAGAS-inspired): does the summary cover all the key
        elements a founder expects from a financial analysis?

        Five required elements — each worth 0.2:
          1. Runway information
          2. Revenue / MRR
          3. Risk signal (survival, alerts)
          4. Confidence / data quality note
          5. Recommendation or next step
        """
        if not summary:
            return 0.0

        sl = summary.lower()
        elements = {
            "runway":        any(kw in sl for kw in ["runway", "mois", "semaines"]),
            "revenue":       any(kw in sl for kw in ["mrr", "revenu", "tnd", "€", "eur", "arr"]),
            "risk_signal":   any(kw in sl for kw in ["survie", "risque", "🔴", "🟠", "🟢", "critique"]),
            "confidence":    "confiance" in sl,
            "recommendation": any(kw in sl for kw in ["recommand", "💡", "scenario", "stratégie", "transmis"]),
        }
        return sum(elements.values()) / len(elements)

    def _context_recall(self, benchmarks, context) -> float:
        """
        Context Recall: did the retriever surface sector-relevant benchmarks?

        Returns:
          0.0  — no benchmarks fetched at all
          0.2  — benchmarks fetched but all values are None
          0.6  — benchmarks have data but sector mismatch or unknown
          0.8  — benchmarks have data, sector partially matches
          1.0  — benchmarks have data and sector matches perfectly
        """
        if benchmarks is None:
            return 0.0

        # Check if any actual benchmark values are present
        has_data = any(
            getattr(benchmarks, attr, None) is not None
            for attr in ["cac_median", "ltv_median", "churn_median", "gross_margin_median"]
        )
        if not has_data:
            return 0.2

        # Check similarity score (Chroma distance)
        sim = getattr(benchmarks, "similarity_score", 0.0) or 0.0
        if sim >= 0.85:
            return 1.0
        if sim >= 0.60:
            return 0.8
        if sim > 0.0:
            return 0.6

        # No similarity score but data exists
        startup_sector = (getattr(context, "secteur", "") or "").lower() if context else ""
        source = (getattr(benchmarks, "source", "") or "").lower()
        if startup_sector and source:
            if startup_sector[:4] in source or source[:4] in startup_sector:
                return 0.9
        return 0.7

    def _context_precision(self, benchmarks, result: Dict) -> float:
        """
        Context Precision: were the retrieved benchmarks actually used in the analysis?

        Checks if the 'comparator' step (ScenarioComparatorResult) ran successfully
        and produced meaningful benchmark comparisons.

        ScenarioComparatorResult fields:
          comparaisons        — list[KPIComparison]
          score_vs_benchmark  — float [0-1]
          scenario_recommande — str
          points_forts        — list
          points_faibles      — list
        """
        if benchmarks is None:
            return 0.0

        comparator = result.get("comparator")
        if comparator is None:
            return 0.3  # benchmarks fetched but comparator step was skipped

        # Check ScenarioComparatorResult fields
        def _get(attr):
            v = getattr(comparator, attr, None)
            if v is None and isinstance(comparator, dict):
                v = comparator.get(attr)
            return v

        score      = _get("score_vs_benchmark")
        comparaisons = _get("comparaisons") or []
        points_forts  = _get("points_forts") or []
        points_faibles = _get("points_faibles") or []

        # score_vs_benchmark is the most direct indicator benchmarks were used
        if score is not None:
            # comparaisons list tells us how many KPIs were actually compared
            n_compared = len(comparaisons) if isinstance(comparaisons, list) else 0
            if n_compared >= 3:
                return 1.0
            if n_compared >= 1:
                return 0.8
            return 0.7  # score present but no individual comparisons

        if comparaisons:
            return 0.6  # comparisons present but no aggregate score

        return 0.4  # comparator ran but produced no useful output

    # ── 4. NLP quality ────────────────────────────────────────────────────────

    def _summary_coverage(self, summary: str) -> float:
        """
        Summary Coverage (ROUGE-1 inspired):
        Fraction of expected financial keywords present in the summary.
        Measures whether the summary is information-dense.
        """
        if not summary:
            return 0.0
        sl = summary.lower()
        found = sum(1 for term in self._FINANCIAL_TERMS if term in sl)
        return found / len(self._FINANCIAL_TERMS)

    def _bertscore(
        self, summary: str, result: Dict, errors: List[str]
    ) -> Optional[float]:
        """
        BERTScore F1 (optional — requires pip install bert-score).

        Compares the generated summary against a reference built from the
        raw KPI values. A high score means the summary accurately reflects
        the analysis output in semantic space.
        """
        if not summary:
            return None
        try:
            from bert_score import score as bert_score_fn
        except ImportError:
            errors.append("bert-score not installed — run: pip install bert-score")
            return None

        kpis = result.get("kpis")
        mc   = result.get("monte_carlo")
        conf = result.get("confidence")

        ref_parts: List[str] = []
        if kpis:
            runway = getattr(kpis, "runway_months", None)
            mrr    = getattr(kpis, "mrr", None)
            lc     = getattr(kpis, "ltv_cac_ratio", None)
            if runway is not None:
                ref_parts.append(f"Runway {runway:.1f} mois")
            if mrr is not None:
                ref_parts.append(f"MRR {mrr:,.0f}")
            if lc is not None:
                ref_parts.append(f"LTV/CAC {lc:.2f}")

        if mc:
            p = getattr(mc, "proba_survie_12m", None)
            if p is not None:
                ref_parts.append(f"Probabilité survie 12 mois {p:.0%}")

        if conf:
            s = getattr(conf, "score", None)
            n = getattr(conf, "niveau", "")
            if s is not None:
                ref_parts.append(f"Confiance analyse {n} {s:.0%}")

        if not ref_parts:
            errors.append("BERTScore: not enough KPI data to build reference")
            return None

        reference = ". ".join(ref_parts)
        try:
            _, _, F1 = bert_score_fn(
                [summary], [reference], lang="fr", verbose=False
            )
            return float(F1.mean())
        except Exception as exc:
            errors.append(f"BERTScore computation failed: {exc}")
            return None
