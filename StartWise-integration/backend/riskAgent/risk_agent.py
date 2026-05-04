import json
import logging
import os
import sqlite3
from typing import Dict, List, Optional, Tuple

import httpx
import numpy as np

from riskAgent.config.llm_client import create_llm_client
from riskAgent.rag.sf_cases_rag import build_rag
from riskAgent.protocol_models import (
    Artifact,
    DataPart,
    Message,
    Task,
    TaskStatus,
    TextPart,
)

logger = logging.getLogger(__name__)

# =========================================================
# CONFIG
# =========================================================

SIMULATION_RUNS = 1000
STABILITY_RUNS  = 20

rag = build_rag()

# =========================================================
# DATA STRUCTURE
# =========================================================

class AgentOutput:
    def __init__(self, agent_name: str, claims: List[Dict], confidence: float):
        self.agent_name = agent_name
        self.claims     = claims
        self.confidence = confidence

    def get_claim(self, claim_type: str, default=None):
        """Helper: first claim of a given type, or default."""
        return next(
            (c["value"] for c in self.claims if c.get("type") == claim_type),
            default
        )

# =========================================================
# LLM
# =========================================================

def query_llm(prompt: str) -> str:
    client, model_name = create_llm_client()
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# =========================================================
# CORE FUNCTIONS  (identical to the non-A2A version)
# =========================================================

def detect_conflicts_llm(agent_outputs: List[AgentOutput]) -> List[Dict]:
    if len(agent_outputs) < 2:
        return []
    structured = [
        {"agent": a.agent_name, "claims": a.claims, "confidence": a.confidence}
        for a in agent_outputs
    ]
    prompt = f"""
Detect contradictions between agents.

Data:
{json.dumps(structured, indent=2)}

Return JSON:
[
  {{
    "conflict": "...",
    "agents": ["a", "b"],
    "severity": 0.7
  }}
]
"""
    raw = query_llm(prompt)
    try:
        return json.loads(raw[raw.find("["):raw.rfind("]") + 1])
    except Exception:
        return []


def rule_based_checks(agent_outputs: List[AgentOutput]) -> List[Dict]:
    """
    Hard-coded sanity rules applied to ALL agents, not just finance.
    """
    conflicts = []
    for a in agent_outputs:
        for c in a.claims:
            t, v = c.get("type"), c.get("value", 0)

            if t == "roi" and v > 1:
                conflicts.append({
                    "conflict": f"[{a.agent_name}] ROI > 100 % – unrealistic",
                    "agents":   [a.agent_name],
                    "severity": 0.9
                })
            if t == "revenue" and v < 0:
                conflicts.append({
                    "conflict": f"[{a.agent_name}] Negative revenue",
                    "agents":   [a.agent_name],
                    "severity": 0.85
                })
            if t == "legal_risk" and v > 1:
                conflicts.append({
                    "conflict": f"[{a.agent_name}] Legal risk score out of range",
                    "agents":   [a.agent_name],
                    "severity": 0.8
                })
            if t == "market_share" and not (0 <= v <= 1):
                conflicts.append({
                    "conflict": f"[{a.agent_name}] Market share out of [0,1]",
                    "agents":   [a.agent_name],
                    "severity": 0.7
                })

    return conflicts


def compute_uncertainty(agent_outputs: List[AgentOutput]) -> float:
    if not agent_outputs:
        return 1.0
    return 1 - sum(a.confidence for a in agent_outputs) / len(agent_outputs)


# ------------------------------------------------------------------
# MONTE CARLO  –  multi-agent (finance + marketing + investissement)
# ------------------------------------------------------------------

def monte_carlo_risk(agent_outputs: List[AgentOutput]) -> Tuple[float, Tuple[float, float]]:
    """
    Runs a Monte Carlo simulation that incorporates signals from
    finance, marketing, legal, and investissement agents.

    Each agent contributes normally-distributed noise around its claims.
    A scenario is a "failure" if the net value (revenue − cost − legal
    penalty − market drag − investment shortfall) is negative.
    """
    by_name: Dict[str, AgentOutput] = {a.agent_name: a for a in agent_outputs}

    # ── Finance ────────────────────────────────────────────────────
    finance     = by_name.get("finance")
    revenue     = finance.get_claim("revenue", 10_000) if finance else 10_000
    cost        = finance.get_claim("cost",     8_000) if finance else  8_000

    # ── Marketing ──────────────────────────────────────────────────
    marketing   = by_name.get("marketing")
    market_risk = marketing.get_claim("market_risk", 0.0) if marketing else 0.0
    # market_risk is a score in [0,1]; translate to revenue drag
    market_drag_base = revenue * market_risk

    # ── Legal ──────────────────────────────────────────────────────
    legal       = by_name.get("legal")
    legal_risk  = legal.get_claim("legal_risk",  0.0) if legal else 0.0
    # legal_risk [0,1] → potential penalty proportional to cost
    legal_penalty_base = cost * legal_risk

    # ── Investissement ─────────────────────────────────────────────
    invest      = by_name.get("investissement")
    inv_needed  = invest.get_claim("investment_needed", 0.0) if invest else 0.0
    inv_secured = invest.get_claim("investment_secured", inv_needed) if invest else inv_needed
    # Shortfall is a direct cash gap
    inv_shortfall = max(inv_needed - inv_secured, 0.0)

    failures = 0
    for _ in range(SIMULATION_RUNS):
        sim_revenue       = np.random.normal(revenue,            revenue            * 0.20)
        sim_cost          = np.random.normal(cost,               cost               * 0.20)
        sim_market_drag   = np.random.normal(market_drag_base,   market_drag_base   * 0.30 + 1)
        sim_legal_penalty = np.random.normal(legal_penalty_base, legal_penalty_base * 0.40 + 1)
        sim_inv_gap       = np.random.normal(inv_shortfall,      inv_shortfall      * 0.25 + 1)

        net = sim_revenue - sim_cost - sim_market_drag - sim_legal_penalty - sim_inv_gap
        if net < 0:
            failures += 1

    p   = failures / SIMULATION_RUNS
    err = 1.96 * np.sqrt(p * (1 - p) / SIMULATION_RUNS)
    return p, (p - err, p + err)


def compute_conflict_score(conflicts: List[Dict], agent_outputs: List[AgentOutput]) -> float:
    if not conflicts:
        return 0.0

    conf_map = {a.agent_name: a.confidence for a in agent_outputs}

    scores = []
    for c in conflicts:
        avg_conf = sum(conf_map.get(ag, 0.5) for ag in c["agents"]) / len(c["agents"])
        scores.append(c["severity"] * (1 - avg_conf))

    return sum(scores) / len(scores)


# ------------------------------------------------------------------
# RAG  –  FAISS vector search over failed-startup descriptions
# ------------------------------------------------------------------

def compute_rag_risk(description: str) -> Tuple[float, float, float, List[Dict]]:
    """
    Queries the FAISS index (built from data/ with startup description +
    causes) and returns (risk, confidence, avg_similarity, similar_cases).
    """
    result = rag.run(description, k=5)
    cases  = result["similar_cases"]

    if not cases:
        return 0.5, 0.0, 0.0, []

    causes       = []
    similarities = []
    for c in cases:
        causes.extend(c.get("cause", []))
        similarities.append(c.get("score", 0))

    diversity   = len(set(causes)) / (len(causes) + 1)
    risk        = min(diversity + len(cases) / 10, 1.0)
    confidence  = min(len(cases) / 5, 1.0)
    avg_sim     = float(np.mean(similarities)) if similarities else 0.0

    return risk, confidence, avg_sim, cases


# ------------------------------------------------------------------
# SQL  –  sector scores from the failed-startup SQL database
# ------------------------------------------------------------------

def compute_score_risk(db_conn, sector: Optional[str]) -> Tuple[float, float]:
    """
    Reads score_market, score_scale, score_rebuild from the SQL DB
    for the matched sector.
    """
    if not sector:
        return 0.5, 0.0

    cursor = db_conn.cursor()
    cursor.execute("""
        SELECT score_market, score_scale, score_rebuild
        FROM scores
        WHERE sector = ?
    """, (sector,))
    rows = cursor.fetchall()

    if not rows:
        return 0.5, 0.0

    vals = [v for r in rows for v in r if v is not None]
    risk       = sum(vals) / len(vals)
    confidence = min(len(rows) / 10, 1.0)

    return risk, confidence


# ------------------------------------------------------------------
# Per-agent domain risk extractors
# ------------------------------------------------------------------

def compute_marketing_risk(agent_outputs: List[AgentOutput]) -> Tuple[float, float]:
    """
    Derives a standalone marketing risk signal from the marketing agent's claims.
    Combines market_risk + competition + churn into a single score.
    """
    marketing = next((a for a in agent_outputs if a.agent_name == "marketing"), None)
    if not marketing:
        return 0.5, 0.0

    market_risk  = marketing.get_claim("market_risk",  0.5)
    competition  = marketing.get_claim("competition",  0.5)   # [0,1]
    churn        = marketing.get_claim("churn_rate",   0.2)   # [0,1]

    combined = (market_risk * 0.5) + (competition * 0.3) + (churn * 0.2)
    return min(combined, 1.0), marketing.confidence


def compute_legal_risk(agent_outputs: List[AgentOutput]) -> Tuple[float, float]:
    """
    Derives a standalone legal risk signal.
    """
    legal = next((a for a in agent_outputs if a.agent_name == "legal"), None)
    if not legal:
        return 0.5, 0.0

    legal_risk    = legal.get_claim("legal_risk",    0.5)
    compliance    = legal.get_claim("compliance",    0.5)   # [0,1], higher = riskier
    pending_suits = legal.get_claim("pending_suits", 0)     # count

    suit_penalty  = min(pending_suits * 0.05, 0.3)
    combined      = (legal_risk * 0.5) + (compliance * 0.3) + suit_penalty
    return min(combined, 1.0), legal.confidence


def compute_investment_risk(agent_outputs: List[AgentOutput]) -> Tuple[float, float]:
    """
    Derives a standalone investment risk signal.
    """
    invest = next((a for a in agent_outputs if a.agent_name == "investissement"), None)
    if not invest:
        return 0.5, 0.0

    needed   = invest.get_claim("investment_needed",  1.0)
    secured  = invest.get_claim("investment_secured", 0.0)
    runway   = invest.get_claim("runway_months",     12.0)

    coverage     = secured / needed if needed > 0 else 0.0
    runway_risk  = max(0.0, 1 - runway / 24)          # 24 months = ideal
    combined     = ((1 - coverage) * 0.6) + (runway_risk * 0.4)
    return min(combined, 1.0), invest.confidence


# ------------------------------------------------------------------
# FUSION
# ------------------------------------------------------------------

def fuse(signals: List[Tuple[float, float]]) -> float:
    """Weighted average using confidence as weight (floor 0.05)."""
    total_w, total = 0.0, 0.0
    for risk, conf in signals:
        w       = max(conf, 0.05)
        total  += risk * w
        total_w += w
    return total / total_w if total_w > 0 else 0.5


# =========================================================
# METRICS
# =========================================================

def ablation(signals: List[Tuple[float, float]]) -> List[float]:
    """Leave-one-out sensitivity analysis."""
    results = []
    for i in range(len(signals)):
        reduced = signals[:i] + signals[i + 1:]
        results.append(fuse(reduced))
    return results


def conflict_density(conflicts: List[Dict], agents: List[AgentOutput]) -> float:
    return len(conflicts) / (len(agents) + 1)


# =========================================================
# RISK AGENT  –  A2A (Task protocol)
# =========================================================

class RiskAgent:

    def __init__(self):
        self.agent_outputs: Dict[str, AgentOutput] = {}

    # ── A2A entrypoints ────────────────────────────────────────────

    def process_task(self, task: Task) -> Task:
        """Primary entry point for the A2A server."""
        try:
            payload     = self._extract_payload(task)
            description = payload.get("description", "")
            db_path     = os.path.join(os.path.dirname(__file__), "data", "sf_scores.db")

            if not description:
                return self._fail(task, "Missing description")

            db_conn = sqlite3.connect(db_path) if db_path else sqlite3.connect(":memory:")

            # Accept pre-loaded outputs from an orchestrator
            self._load_agent_outputs(payload.get("agent_outputs", []))

            report   = self._execute(description, db_conn)
            artifact = Artifact(
                name="risk_report",
                parts=[DataPart(data=report[0]["payload"])]
            )
            task.artifacts = [artifact]
            task.status    = TaskStatus(state="completed")
            return task

        except Exception as e:
            logger.exception("RiskAgent failure")
            return self._fail(task, str(e))

    def continue_task(self, task: Task) -> Task:
        """Resume after input-required."""
        return self.process_task(task)

    # ── on_message  (non-A2A / legacy message bus) ─────────────────

    def on_message(self, message: Dict):
        """
        Kept for backward compatibility with the message-bus pattern.
        """
        if message["type"] == "agent_output":
            sender  = message["sender"]
            payload = message["payload"]
            self.agent_outputs[sender] = AgentOutput(
                sender,
                payload.get("claims",     []),
                payload.get("confidence", 0.5)
            )

        elif message["type"] == "run_risk_analysis":
            return self._execute(
                message["payload"]["description"],
                message["payload"]["db_conn"]
            )

    # ── CORE EXECUTION ─────────────────────────────────────────────

    def _execute(self, description: str, db_conn) -> List[Dict]:
        """
        Full risk computation using ALL available agents.
        Mirrors _execute / _compute_once from the non-A2A version,
        extended to marketing, legal, and investissement.
        """
        agents = list(self.agent_outputs.values())

        # ── 1. Sector (searched across ALL agents, not just marketing) ──
        sector = None
        for a in agents:
            sector = a.get_claim("sector")
            if sector:
                break

        # ── 2. Conflict detection ───────────────────────────────────────
        # Skip LLM conflict detection when no peer agents are present
        # (standalone call — only RAG/sector risk matters)
        llm_conflicts  = detect_conflicts_llm(agents) if len(agents) >= 2 else []
        rule_conflicts = rule_based_checks(agents)
        all_conflicts  = llm_conflicts + rule_conflicts

        # ── 3. Uncertainty ─────────────────────────────────────────────
        uncertainty = compute_uncertainty(agents)

        # ── 4. Monte Carlo  (multi-agent) ──────────────────────────────
        mc_risk, mc_ci = monte_carlo_risk(agents)
        mc_conf        = max(0.05, 1 - (mc_ci[1] - mc_ci[0]))

        # ── 5. Conflict score ───────────────────────────────────────────
        conflict_score = compute_conflict_score(all_conflicts, agents)
        conflict_conf  = 0.7 if all_conflicts else 0.3

        # ── 6. RAG  (FAISS – failed startup descriptions + causes) ─────
        rag_risk, rag_conf, rag_similarity, rag_cases = compute_rag_risk(description)

        # ── 7. SQL sector scores ────────────────────────────────────────
        score_risk, score_conf = compute_score_risk(db_conn, sector)

        # ── 8. Domain-specific agent risks ─────────────────────────────
        mkt_risk,  mkt_conf  = compute_marketing_risk(agents)
        legal_risk, legal_conf = compute_legal_risk(agents)
        inv_risk,  inv_conf  = compute_investment_risk(agents)

        # ── 9. Fusion ───────────────────────────────────────────────────
        signals = [
            (mc_risk,       mc_conf),       # Monte Carlo financial failure
            (conflict_score, conflict_conf), # Cross-agent contradictions
            (uncertainty,    0.6),           # Ensemble confidence gap
            (rag_risk,       rag_conf),      # FAISS similarity to failed startups
            (score_risk,     score_conf),    # SQL sector benchmark scores
            (mkt_risk,       mkt_conf),      # Marketing domain risk
            (legal_risk,     legal_conf),    # Legal domain risk
            (inv_risk,       inv_conf),      # Investment / runway risk
        ]

        global_risk = fuse(signals)

        # ── 10. Stability (STABILITY_RUNS Monte Carlo resamples) ────────
        stability = self._compute_stability(description, db_conn, agents)

        # ── 11. Diagnostic metrics ──────────────────────────────────────
        ablation_scores = ablation(signals)
        density         = conflict_density(all_conflicts, agents)

        return [{
            "sender": "risk",
            "type":   "risk_report",
            "payload": {
                "global_risk":    global_risk,

                # Per-signal breakdown
                "monte_carlo": {
                    "risk": mc_risk,
                    "ci":   mc_ci,
                    "conf": mc_conf
                },
                "conflict_score":  conflict_score,
                "uncertainty":     uncertainty,
                "rag": {
                    "risk":           rag_risk,
                    "confidence":     rag_conf,
                    "avg_similarity": rag_similarity,
                    "similar_cases":  rag_cases,
                },
                "sector_score": {
                    "sector":     sector,
                    "risk":       score_risk,
                    "confidence": score_conf
                },

                # Domain agents
                "agent_risks": {
                    "finance":       mc_risk,
                    "marketing":     mkt_risk,
                    "legal":         legal_risk,
                    "investissement": inv_risk
                },

                # Diagnostics
                "metrics": {
                    "stability":        stability,
                    "ablation":         ablation_scores,
                    "conflict_density": density,
                    "signal_labels": [
                        "monte_carlo", "conflict", "uncertainty",
                        "rag", "sector_sql",
                        "marketing", "legal", "investissement"
                    ]
                },

                "conflicts": all_conflicts
            }
        }]

    # ── STABILITY ──────────────────────────────────────────────────

    def _compute_once(self, description: str, db_conn, agents: List[AgentOutput]) -> float:
        """Single lightweight fuse for stability sampling."""
        mc_risk, mc_ci   = monte_carlo_risk(agents)
        mc_conf          = max(0.05, 1 - (mc_ci[1] - mc_ci[0]))
        conflicts        = detect_conflicts_llm(agents) + rule_based_checks(agents)
        conflict_score   = compute_conflict_score(conflicts, agents)
        uncertainty      = compute_uncertainty(agents)
        rag_risk, rag_conf, _, _cases = compute_rag_risk(description)
        sector           = next((a.get_claim("sector") for a in agents if a.get_claim("sector")), None)
        score_risk, score_conf = compute_score_risk(db_conn, sector)
        mkt_risk,  mkt_conf   = compute_marketing_risk(agents)
        legal_risk, legal_conf = compute_legal_risk(agents)
        inv_risk,  inv_conf   = compute_investment_risk(agents)

        return fuse([
            (mc_risk,        mc_conf),
            (conflict_score, 0.7),
            (uncertainty,    0.6),
            (rag_risk,       rag_conf),
            (score_risk,     score_conf),
            (mkt_risk,       mkt_conf),
            (legal_risk,     legal_conf),
            (inv_risk,       inv_conf),
        ])

    def _compute_stability(self, description: str, db_conn, agents: List[AgentOutput]) -> float:
        scores = [self._compute_once(description, db_conn, agents) for _ in range(STABILITY_RUNS)]
        return float(np.var(scores))

    # ── INTERNAL HELPERS ───────────────────────────────────────────

    def _load_agent_outputs(self, outputs: List[Dict]):
        """Ingest pre-serialized agent outputs from an orchestrator payload."""
        for o in outputs:
            name = o.get("agent") or o.get("agent_name", "unknown")
            self.agent_outputs[name] = AgentOutput(
                name,
                o.get("claims",     []),
                o.get("confidence", 0.5)
            )

    def _extract_payload(self, task: Task) -> Dict:
        if not task.messages:
            return {}
        msg = task.messages[-1]
        for p in msg.parts:
            if isinstance(p, DataPart):
                return p.data
            if isinstance(p, TextPart):
                try:
                    return json.loads(p.text)
                except Exception:
                    return {"description": p.text}
        return {}

    def _fail(self, task: Task, error: str) -> Task:
        task.status    = TaskStatus(state="failed")
        task.artifacts = [Artifact(name="error", parts=[TextPart(text=error)])]
        return task