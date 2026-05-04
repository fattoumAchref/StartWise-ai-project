"""
finagents/risk/bus_adapter.py
==============================
Risk Agent — n×n A2A bus participant.

All agents broadcast to all other agents; Risk is no exception.
Risk's *unique* additional role is cross-agent conflict detection:
after it has accumulated signals from 2+ agents it compares them for
contradictions and publishes a risk.conflict_report to the full network.

Protocol flow (n×n):
  ANY agent  →  risk_agent   <any message type>
  risk_agent →  ALL agents   risk.assessment     (after financial_analysis)
  risk_agent →  ALL agents   risk.conflict_report (when 2+ agents have sent data)

The FinanceCommAgent (bus_publisher.py) stores the result under
risk_level / risk_score / risk_details backward-compat keys so the
frontend can read it immediately via GET /api/a2a/state.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import httpx
import os

from a2a_bus.comm_agent import CommAgent

logger = logging.getLogger(__name__)

_SEP = "═" * 68

# ── LLM config (same Token Factory used by other agents) ─────────────────────

_BASE_URL  = os.getenv("ESPRIT_BASE_URL", "https://tokenfactory.esprit.tn/api")
_API_KEY   = os.getenv("ESPRIT_API_KEY", "")
_MODEL     = os.getenv("ESPRIT_MODEL", os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct"))


def _call_llm(messages: list[dict], max_tokens: int = 400) -> str:
    if not _API_KEY:
        return ""
    try:
        r = httpx.post(
            _BASE_URL + "/chat/completions",
            headers={"Authorization": f"Bearer {_API_KEY}"},
            json={"model": _MODEL, "messages": messages,
                  "temperature": 0.2, "max_tokens": max_tokens},
            timeout=30.0,
            verify=False,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("[RiskBusAdapter] LLM call failed: %s", exc)
        return ""


def _emit(label: str, **fields) -> None:
    print(f"\n{_SEP}", flush=True)
    print(f"[RiskBusAdapter]  {label}", flush=True)
    for k, v in fields.items():
        print(f"  {k:<28} {v}", flush=True)
    print(_SEP, flush=True)


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: "RiskBusAdapter | None" = None
_lock = threading.Lock()


def get_risk_bus_adapter() -> "RiskBusAdapter":
    global _instance
    with _lock:
        if _instance is None or not _instance.is_alive():
            _instance = RiskBusAdapter()
            _instance.start()
            logger.info("[RiskBusAdapter] started")
    return _instance


# ── Risk Bus Adapter ──────────────────────────────────────────────────────────

class RiskBusAdapter(CommAgent):
    """
    Listens on the A2A bus for financial_analysis messages.
    Runs a deterministic multi-dimension risk scoring and publishes
    risk.assessment back to finance_agent.
    """

    AGENT_ID = "risk_agent"

    # ── Known message types from all agents ───────────────────────────────────
    _KNOWN_TYPES = {
        "financial_analysis",
        "marketing.analysis",
        "legal.assessment",
        "investment.recommendation",
        # allow any risk.* messages from future risk sub-agents
    }

    def _should_engage(self, msg: dict) -> bool:
        """
        Autonomous engagement decision.

        Risk talks to ALL agents (n×n).  We skip only truly empty or unknown
        messages.  For financial_analysis we additionally require at least one
        numeric KPI so we don't fire on skeleton payloads.
        """
        msg_type = msg.get("type", "")

        # Accept any message from a known agent type
        if msg_type in self._KNOWN_TYPES or msg_type.startswith("risk."):
            # For financial_analysis, require at least one real KPI
            if msg_type == "financial_analysis":
                kpis = msg.get("payload", {}).get("data", {}).get("kpis") or {}
                has_data = any(
                    kpis.get(k) is not None
                    for k in ("runway_months", "mrr", "burn_net", "gross_margin_pct")
                )
                if not has_data:
                    logger.info("[RiskBusAdapter] skipping financial_analysis — no KPI data")
                    return False
            return True

        logger.debug("[RiskBusAdapter] ignoring unknown type=%s", msg_type)
        return False

    def _process(self, msg: dict) -> None:
        msg_type = msg.get("type", "")
        sender   = msg.get("from", "?")

        if not self._should_engage(msg):
            return

        _emit(f"MSG RECEIVED — type={msg_type}", from_agent=sender,
              msg_id=msg.get("message_id", "?")[:16])

        if msg_type == "financial_analysis":
            kpis = msg.get("payload", {}).get("data", {}).get("kpis") or {}
            _emit(
                "FINANCIAL KPIs",
                runway=kpis.get("runway_months", "—"),
                mrr=kpis.get("mrr", "—"),
            )
            self._handle_financial_analysis(msg)

        elif msg_type == "marketing.analysis":
            self._store_peer_context(msg, "marketing_agent",
                                     score_key="score", level_key="status")

        elif msg_type == "legal.assessment":
            self._store_peer_context(msg, "legal_agent",
                                     score_key="risk_score", level_key="risk_level")

        elif msg_type == "investment.recommendation":
            data = msg.get("payload", {}).get("data", {})
            self.set_state({
                "investment_agent_rating":     str(data.get("rating") or "?"),
                "investment_agent_confidence": str(msg.get("confidence", 0)),
                "investment_agent_ts":         msg.get("timestamp", ""),
            })
            self._store_peer_context(msg, "investment_agent",
                                     score_key="score", level_key="rating")

        # After every message, attempt cross-agent conflict detection
        self._run_cross_agent_conflict_check(triggering_msg=msg)

    def _store_peer_context(self, msg: dict, sender_id: str,
                            score_key: str = "score", level_key: str = "level") -> None:
        """Store a peer agent's message in Risk state for cross-agent awareness."""
        data  = msg.get("payload", {}).get("data", {})
        level = str(data.get(level_key) or data.get("level") or data.get("status") or "?")
        score = str(data.get(score_key) or data.get("score") or msg.get("confidence", 0))
        summary = str(
            data.get("summary") or
            msg.get("payload", {}).get("recommendation", "")
        )[:200]
        self.set_state({
            f"{sender_id}_level":   level,
            f"{sender_id}_score":   score,
            f"{sender_id}_summary": summary,
            f"{sender_id}_ts":      msg.get("timestamp", ""),
        })
        logger.info("[RiskBusAdapter] stored context from %s: level=%s", sender_id, level)

    # ── Cross-agent conflict detection (Risk's unique role) ───────────────────

    def _run_cross_agent_conflict_check(self, triggering_msg: dict) -> None:
        """
        Risk's unique responsibility in the n×n network:
        compare signals from ALL agents and flag contradictions.

        Only fires when we have data from at least 2 different agents.
        Publishes risk.conflict_report to the entire network.
        """
        try:
            state = self.get_state()
            # Collect which peer agents have already sent us data
            peers_with_data: Dict[str, dict] = {}
            for agent_id in ("finance_agent", "marketing_agent",
                             "legal_agent", "investment_agent"):
                key_prefix = agent_id
                level = state.get(f"{key_prefix}_level") or state.get(f"{key_prefix}_rating")
                score = state.get(f"{key_prefix}_score")
                if level or score:
                    peers_with_data[agent_id] = {
                        "level":   level or "?",
                        "score":   score or "?",
                        "summary": state.get(f"{key_prefix}_summary", ""),
                    }

            if len(peers_with_data) < 2:
                return  # not enough cross-agent data yet

            conflicts = self._detect_cross_agent_conflicts(peers_with_data)

            conflict_msg = {
                "message_id": str(uuid.uuid4()),
                "type":       "risk.conflict_report",
                "from":       "risk_agent",
                "to":         ["finance_agent", "investment_agent",
                               "marketing_agent", "legal_agent"],
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "context":    triggering_msg.get("context", {}),
                "payload": {
                    "data": {
                        "conflicts":     conflicts,
                        "conflict_count": len(conflicts),
                        "agents_compared": list(peers_with_data.keys()),
                        "severity":      "high" if len(conflicts) >= 2 else
                                         "medium" if conflicts else "none",
                        "summary":       self._conflicts_summary(conflicts,
                                                                  peers_with_data),
                    }
                },
                "confidence": 0.75,
                "metadata": {
                    "priority":          "medium",
                    "requires_response": False,
                    "tags":              ["risk", "conflict", "cross-agent"],
                },
            }
            self.publish(conflict_msg)
            logger.info(
                "[RiskBusAdapter] conflict_report published — %d conflict(s) across %s",
                len(conflicts), list(peers_with_data.keys()),
            )

        except Exception as exc:
            logger.warning("[RiskBusAdapter] conflict check failed: %s", exc)

    def _detect_cross_agent_conflicts(
        self, peers: Dict[str, dict]
    ) -> List[dict]:
        """
        Rule-based conflict detection between agent signals.
        Returns a list of conflict dicts with keys: agents, type, description, severity.
        """
        conflicts: List[dict] = []

        def _score(v) -> float:
            try:
                return float(v)
            except (TypeError, ValueError):
                return -1.0

        agents = list(peers.keys())
        signals = {a: _score(peers[a]["score"]) for a in agents}

        # Rule 1: Risk LOW but Finance CRITICAL runway
        finance_score = signals.get("finance_agent", -1)
        invest_score  = signals.get("investment_agent", -1)
        marketing_lvl = (peers.get("marketing_agent") or {}).get("level", "").upper()
        legal_lvl     = (peers.get("legal_agent") or {}).get("level", "").upper()

        if finance_score > 7 and invest_score >= 0 and invest_score < 0.4:
            conflicts.append({
                "agents":      ["finance_agent", "investment_agent"],
                "type":        "finance_investment_mismatch",
                "description": (
                    f"Finance signals critical risk (score {finance_score:.1f}/10) "
                    f"but Investment confidence is low ({invest_score:.2f}). "
                    "Investment recommendation may be based on stale data."
                ),
                "severity": "high",
            })

        if finance_score > 5 and legal_lvl in ("LOW", "NONE"):
            conflicts.append({
                "agents":      ["finance_agent", "legal_agent"],
                "type":        "finance_legal_gap",
                "description": (
                    f"Finance risk is elevated (score {finance_score:.1f}/10) "
                    f"but Legal reports no legal risk ({legal_lvl}). "
                    "Legal assessment may not have accounted for financial exposure."
                ),
                "severity": "medium",
            })

        if marketing_lvl in ("HIGH", "CRITICAL") and finance_score >= 0 and finance_score < 3:
            conflicts.append({
                "agents":      ["marketing_agent", "finance_agent"],
                "type":        "marketing_finance_gap",
                "description": (
                    f"Marketing signals high market risk ({marketing_lvl}) "
                    f"but Finance risk score is low ({finance_score:.1f}/10). "
                    "Revenue projections may be overly optimistic."
                ),
                "severity": "medium",
            })

        # LLM enrichment for free-text signals when we have an API key
        if _API_KEY and len(peers) >= 2:
            peer_summary = "\n".join(
                f"- {aid}: level={d['level']}, score={d['score']}, "
                f"summary={d['summary'][:100]}"
                for aid, d in peers.items()
            )
            raw = _call_llm([
                {"role": "system", "content":
                 "You are a conflict detection engine for AI agents. "
                 "List any contradictions you find between the agent signals below. "
                 "Reply with a JSON array: "
                 '[{"agents":["a","b"],"type":"...","description":"...","severity":"high|medium|low"}]. '
                 "If no conflicts, reply with []."},
                {"role": "user", "content": peer_summary},
            ], max_tokens=300)
            try:
                start, end = raw.find("["), raw.rfind("]") + 1
                if start >= 0 and end > start:
                    llm_conflicts = json.loads(raw[start:end])
                    if isinstance(llm_conflicts, list):
                        conflicts.extend(llm_conflicts)
            except Exception:
                pass

        return conflicts

    def _conflicts_summary(
        self, conflicts: List[dict], peers: Dict[str, dict]
    ) -> str:
        if not conflicts:
            return (
                f"No contradictions detected across {len(peers)} agents "
                f"({', '.join(peers.keys())})."
            )
        sev_counts = {}
        for c in conflicts:
            sev_counts[c.get("severity", "?")] = sev_counts.get(c.get("severity", "?"), 0) + 1
        detail = ", ".join(f"{v} {k}" for k, v in sev_counts.items())
        return (
            f"{len(conflicts)} conflict(s) detected ({detail}) "
            f"across {len(peers)} agents. "
            f"Top issue: {conflicts[0].get('description', '')[:120]}"
        )

    # ── Core handler ──────────────────────────────────────────────────────────

    def _handle_financial_analysis(self, msg: dict) -> None:
        try:
            data = msg.get("payload", {}).get("data", {})
            kpis = data.get("kpis") or {}
            mc   = data.get("monte_carlo") or {}
            project_id = msg.get("context", {}).get("project_id", "default")
            session_id = msg.get("context", {}).get("session_id", "")

            alerts, composite_score, risk_level = self._score_risk(kpis, mc, data)

            _emit(
                "RISK ANALYSIS COMPLETE",
                project_id=project_id,
                risk_level=risk_level,
                composite_score=f"{composite_score:.2f}",
                alerts=len(alerts),
            )

            summary = self._build_summary(risk_level, composite_score, alerts, kpis)

            # Store Finance's signal in our own state so conflict check can compare
            self.set_state({
                "finance_agent_level":   risk_level,
                "finance_agent_score":   str(composite_score),
                "finance_agent_summary": summary[:200],
                "finance_agent_ts":      datetime.now(timezone.utc).isoformat(),
            })

            a2a_msg = {
                "message_id": str(uuid.uuid4()),
                "type":       "risk.assessment",
                "from":       "risk_agent",
                "to":         ["finance_agent", "investment_agent", "marketing_agent", "legal_agent"],
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "context":    {"project_id": project_id, "session_id": session_id},
                "payload": {
                    "data": {
                        "risk_level":     risk_level,
                        "risk_score":     composite_score,
                        "composite_risk": composite_score,
                        "risks":          alerts,
                        "risk_alerts":    alerts,
                        "breakdown":      self._build_breakdown(kpis, mc),
                        "uncertainty":    mc.get("std_12m", 0) / max(float(mc.get("p50", 1) or 1), 1),
                        "monte_carlo":    {
                            "p10":             mc.get("p10"),
                            "p50":             mc.get("p50"),
                            "p90":             mc.get("p90"),
                            "proba_survie":    mc.get("proba_survie_12m"),
                        },
                        "summary": summary,
                    },
                    "recommendation": summary,
                },
                "confidence": max(0.0, 1.0 - composite_score / 10.0),
                "metadata": {
                    "priority":          "high",
                    "requires_response": False,
                    "tags":              ["risk", "assessment", risk_level.lower()],
                },
            }

            self.publish(a2a_msg)
            logger.info("[RiskBusAdapter] risk.assessment published (level=%s)", risk_level)

            # Bridge: update A2A task state if available
            a2a_task_id = msg.get("context", {}).get("a2a_task_id")
            if a2a_task_id:
                self._update_a2a_task_state(a2a_task_id, "completed")

        except Exception as exc:
            logger.exception("[RiskBusAdapter] error in risk analysis: %s", exc)

    # ── Multi-dimension risk scoring ──────────────────────────────────────────

    def _score_risk(
        self, kpis: dict, mc: dict, data: dict
    ) -> Tuple[List[dict], float, str]:
        """
        Score 6 risk dimensions. Returns (alerts, composite_score 0-10, level).
        """
        alerts: List[dict] = []
        total_pts = 0
        max_pts   = 0

        def add(pts: int, max_p: int, severity: str, category: str,
                title: str, description: str, recommendation: str) -> None:
            nonlocal total_pts, max_pts
            total_pts += pts
            max_pts   += max_p
            if pts > 0:
                alerts.append({
                    "severity":       severity,
                    "category":       category,
                    "title":          title,
                    "description":    description,
                    "recommendation": recommendation,
                })

        # ── 1. Runway ──────────────────────────────────────────────────────────
        runway = kpis.get("runway_months")
        if runway is not None:
            runway = float(runway)
            if runway < 3:
                add(4, 4, "critical", "Liquidité",
                    f"Runway critique: {runway:.1f} mois",
                    f"La startup a moins de 3 mois de trésorerie ({runway:.1f} mois). "
                    "Risque immédiat de cessation de paiement.",
                    "Levée de fonds d'urgence ou réduction drastique du burn rate dans les 30 jours.")
            elif runway < 6:
                add(3, 4, "high", "Liquidité",
                    f"Runway court: {runway:.1f} mois",
                    f"Moins de 6 mois de trésorerie disponible ({runway:.1f} mois).",
                    "Initier une levée de fonds ou négocier un pont bancaire dès maintenant.")
            elif runway < 12:
                add(2, 4, "medium", "Liquidité",
                    f"Runway limité: {runway:.1f} mois",
                    f"Runway inférieur à 12 mois ({runway:.1f} mois). Fenêtre de levée serrée.",
                    "Préparer le dossier de levée de fonds dans les 60 jours.")
            else:
                add(0, 4, "low", "Liquidité", "", "", "")

        # ── 2. Survie Monte Carlo ──────────────────────────────────────────────
        proba = mc.get("proba_survie_12m")
        if proba is not None:
            proba = float(proba)
            if proba < 0.35:
                add(3, 3, "critical", "Survie",
                    f"Probabilité de survie très faible: {proba:.0%}",
                    f"Les simulations Monte Carlo indiquent seulement {proba:.0%} de chances "
                    "de survie sur 12 mois selon les trajectoires actuelles.",
                    "Revoir fondamentalement le modèle économique et les hypothèses de croissance.")
            elif proba < 0.55:
                add(2, 3, "high", "Survie",
                    f"Probabilité de survie faible: {proba:.0%}",
                    f"Survie à 12 mois estimée à {proba:.0%}. Trajectoire fragile.",
                    "Identifier 2-3 leviers de croissance rapide pour améliorer la trajectoire.")
            elif proba < 0.70:
                add(1, 3, "medium", "Survie",
                    f"Probabilité de survie modérée: {proba:.0%}",
                    f"Survie à 12 mois estimée à {proba:.0%}. Marge de manoeuvre limitée.",
                    "Accélérer l'acquisition client et optimiser le cycle de vente.")
            else:
                add(0, 3, "low", "Survie", "", "", "")

        # ── 3. Burn vs Revenus ────────────────────────────────────────────────
        burn_net = kpis.get("burn_net") or 0
        mrr      = kpis.get("mrr") or 0
        if burn_net < 0 and mrr > 0:
            burn_ratio = abs(burn_net) / max(mrr, 1)
            if burn_ratio > 2.0:
                add(3, 3, "critical", "Burn Rate",
                    f"Burn rate excessif: {burn_ratio:.1f}x le MRR",
                    f"Le burn mensuel ({abs(burn_net):,.0f}) est {burn_ratio:.1f}x supérieur "
                    f"au MRR ({mrr:,.0f}). Consommation de cash insoutenable.",
                    "Réduire les coûts fixes de 30-40% et accélérer la monétisation.")
            elif burn_ratio > 1.0:
                add(2, 3, "high", "Burn Rate",
                    f"Burn rate élevé: {burn_ratio:.1f}x le MRR",
                    f"Le burn mensuel dépasse le MRR (ratio {burn_ratio:.1f}x).",
                    "Identifier les postes de dépenses compressibles à court terme.")
            elif burn_ratio > 0.5:
                add(1, 3, "medium", "Burn Rate",
                    f"Burn rate modéré: {burn_ratio:.1f}x le MRR",
                    f"Le burn représente {burn_ratio:.0%} du MRR. Surveiller l'évolution.",
                    "Maintenir le cap sur la croissance du MRR pour améliorer le ratio.")
            else:
                add(0, 3, "low", "Burn Rate", "", "", "")
        elif burn_net < 0 and mrr == 0:
            add(3, 3, "critical", "Burn Rate",
                "Burn sans revenus",
                f"Burn mensuel de {abs(burn_net):,.0f} sans aucun revenu récurrent.",
                "Générer un premier revenu récurrent devient la priorité absolue.")

        # ── 4. Marge brute ────────────────────────────────────────────────────
        margin = kpis.get("gross_margin_pct")
        if margin is not None:
            margin = float(margin)
            if margin < 0:
                add(3, 3, "critical", "Rentabilité",
                    f"Marge brute négative: {margin:.1f}%",
                    f"La marge brute est négative ({margin:.1f}%). "
                    "Chaque vente détruit de la valeur.",
                    "Revoir la structure de prix ou réduire le COGS immédiatement.")
            elif margin < 20:
                add(2, 3, "high", "Rentabilité",
                    f"Marge brute faible: {margin:.1f}%",
                    f"Marge brute de {margin:.1f}%, insuffisante pour couvrir les coûts fixes.",
                    "Optimiser le COGS et envisager une hausse des prix.")
            elif margin < 40:
                add(1, 3, "medium", "Rentabilité",
                    f"Marge brute à améliorer: {margin:.1f}%",
                    f"Marge brute de {margin:.1f}%. La cible sectorielle est souvent 60%+.",
                    "Identifier les leviers d'amélioration de la marge à 6 mois.")
            else:
                add(0, 3, "low", "Rentabilité", "", "", "")

        # ── 5. LTV/CAC ────────────────────────────────────────────────────────
        ltv_cac = kpis.get("ltv_cac_ratio")
        if ltv_cac is not None:
            ltv_cac = float(ltv_cac)
            if ltv_cac < 1.0:
                add(3, 3, "critical", "Acquisition",
                    f"LTV/CAC défavorable: {ltv_cac:.2f}x",
                    f"Le LTV/CAC est de {ltv_cac:.2f}x. La startup dépense plus pour acquérir "
                    "un client que ce client ne rapportera jamais.",
                    "Revoir le modèle de pricing ou réduire drastiquement le CAC.")
            elif ltv_cac < 3.0:
                add(1, 3, "medium", "Acquisition",
                    f"LTV/CAC sous la cible: {ltv_cac:.2f}x",
                    f"LTV/CAC de {ltv_cac:.2f}x (cible: >3x). Efficacité marketing à améliorer.",
                    "Allonger la durée de rétention et optimiser les canaux d'acquisition.")
            else:
                add(0, 3, "low", "Acquisition", "", "", "")

        # ── 6. Alerte cash explicite ──────────────────────────────────────────
        cash_alert = (kpis.get("cash_out_alert") or "").upper()
        if "CRITIQUE" in cash_alert or "CRITICAL" in cash_alert:
            add(2, 2, "critical", "Trésorerie",
                "Alerte trésorerie critique",
                "Le système de KPIs a déclenché une alerte trésorerie de niveau CRITIQUE.",
                "Action immédiate requise: gel des dépenses non-essentielles.")
        elif "DANGER" in cash_alert or "WARNING" in cash_alert:
            add(1, 2, "high", "Trésorerie",
                "Alerte trésorerie élevée",
                "Alerte trésorerie niveau DANGER/WARNING détectée.",
                "Surveiller de près la trésorerie hebdomadairement.")
        else:
            add(0, 2, "low", "Trésorerie", "", "", "")

        # ── Composite score 0-10 ──────────────────────────────────────────────
        if max_pts > 0:
            composite = (total_pts / max_pts) * 10
        else:
            composite = 0.0

        if composite >= 7.5:
            level = "CRITICAL"
        elif composite >= 5.0:
            level = "HIGH"
        elif composite >= 2.5:
            level = "MEDIUM"
        else:
            level = "LOW"

        # Filter out empty alerts
        alerts = [a for a in alerts if a.get("title")]

        return alerts, round(composite, 2), level

    def _build_breakdown(self, kpis: dict, mc: dict) -> dict:
        return {
            "runway_months":    kpis.get("runway_months"),
            "burn_net":         kpis.get("burn_net"),
            "mrr":              kpis.get("mrr"),
            "gross_margin_pct": kpis.get("gross_margin_pct"),
            "ltv_cac_ratio":    kpis.get("ltv_cac_ratio"),
            "proba_survie_12m": mc.get("proba_survie_12m"),
            "cash_out_alert":   kpis.get("cash_out_alert"),
        }

    def _build_summary(
        self, level: str, score: float, alerts: list, kpis: dict
    ) -> str:
        """Build a concise natural-language summary. Uses LLM if available."""
        level_fr = {
            "CRITICAL": "CRITIQUE", "HIGH": "ÉLEVÉ",
            "MEDIUM": "MODÉRÉ", "LOW": "FAIBLE",
        }.get(level, level)

        base = (
            f"Niveau de risque global : {level_fr} (score {score:.1f}/10). "
            f"{len(alerts)} facteur(s) de risque identifié(s)."
        )

        if not alerts:
            return base + " Profil de risque satisfaisant — continuer à surveiller les KPIs."

        top = alerts[0]
        base += f" Priorité : {top['title']}. {top['recommendation']}"

        if not _API_KEY:
            return base

        # Optional LLM enhancement
        alert_list = "; ".join(
            f"[{a['severity'].upper()}] {a['title']}" for a in alerts[:4]
        )
        raw = _call_llm([
            {"role": "system", "content":
             "Tu es un analyste de risque financier. Rédige un résumé de risque "
             "en 2 phrases maximum, en français, sans répéter les chiffres déjà listés. "
             "Commence par le niveau de risque global."},
            {"role": "user", "content":
             f"Niveau: {level_fr} | Score: {score:.1f}/10 | Alertes: {alert_list}"},
        ], max_tokens=120)
        return raw if raw else base

    def _update_a2a_task_state(self, task_id: str, state: str) -> None:
        risk_url = os.getenv("RISK_AGENT_URL", "http://localhost:8003")
        try:
            httpx.post(
                f"{risk_url}/internal/tasks/{task_id}/state/{state}",
                timeout=2.0,
            )
        except Exception as exc:
            logger.debug("[RiskBusAdapter] could not update task state: %s", exc)
