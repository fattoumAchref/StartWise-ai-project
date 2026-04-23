"""
a2a_bus/mock_agents.py
======================
Agents simulés pour les tests du bus A2A.

Ces mocks reproduisent le comportement attendu de investment_agent et risk_agent :
ils lisent les messages de leur inbox, génèrent une réponse structurée,
et la publient vers finance_agent via le bus.

Usage :
    from a2a_bus.mock_agents import MockInvestmentAgent, MockRiskAgent
    inv = MockInvestmentAgent()
    inv.process_inbox()   # lit + répond à tous les messages en attente
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from a2a_bus.bus_client import A2ABusClient


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# INVESTMENT AGENT MOCK
# ─────────────────────────────────────────────────────────────────────────────

class MockInvestmentAgent:
    """
    Simule investment_agent.
    Reçoit un message financial_analysis et produit un investment_scoring.

    Logique de scoring simplifiée (à remplacer par le vrai agent) :
      - LTV/CAC ratio     → unit economics
      - Probabilité survie 12m → risk appetite
      - Gross margin      → SaaS quality
      - Confidence score  → fiabilité des données
    """

    AGENT_ID = "investment_agent"

    def __init__(self, bus_url: str = "http://localhost:8765"):
        self.client = A2ABusClient(self.AGENT_ID, bus_url)

    # ── Traitement d'un message ───────────────────────────────────────────────

    def _score(self, finance_msg: Dict[str, Any]) -> Dict[str, Any]:
        """Génère la réponse investment_scoring à partir d'un financial_analysis."""
        data  = finance_msg.get("payload", {}).get("data", {})
        kpis  = data.get("kpis", {}) or {}
        mc    = data.get("monte_carlo", {}) or {}
        bench = data.get("benchmarks", {}) or {}
        conf  = finance_msg.get("confidence", 0.0) or 0.0

        score   = 0
        reasons = []

        # ── Unit economics ────────────────────────────────────────────────────
        ltv_cac = kpis.get("ltv_cac_ratio") or 0
        if ltv_cac >= 3:
            score += 30
            reasons.append(f"LTV/CAC {ltv_cac:.1f}x ✓ — unit economics excellents")
        elif ltv_cac >= 1.5:
            score += 15
            reasons.append(f"LTV/CAC {ltv_cac:.1f}x — unit economics acceptables")
        elif ltv_cac > 0:
            reasons.append(f"LTV/CAC {ltv_cac:.1f}x ✗ — unit economics faibles")
        else:
            reasons.append("LTV/CAC non disponible — due diligence requise")

        # ── Survie probabiliste ───────────────────────────────────────────────
        proba = mc.get("proba_survie_12m") or 0
        if proba >= 0.70:
            score += 25
            reasons.append(f"Survie 12m {proba:.0%} ✓ — runway confortable")
        elif proba >= 0.40:
            score += 10
            reasons.append(f"Survie 12m {proba:.0%} — risque modéré acceptable")
        elif proba > 0:
            reasons.append(f"Survie 12m {proba:.0%} ✗ — risque élevé")

        # ── Marge brute ───────────────────────────────────────────────────────
        gm = kpis.get("gross_margin_pct") or 0
        if gm >= 60:
            score += 20
            reasons.append(f"Marge brute {gm:.0f}% ✓ — profil SaaS")
        elif gm >= 40:
            score += 10
            reasons.append(f"Marge brute {gm:.0f}% — acceptable")
        elif gm > 0:
            reasons.append(f"Marge brute {gm:.0f}% ✗ — à améliorer")

        # ── Fiabilité des données ─────────────────────────────────────────────
        if conf >= 0.70:
            score += 15
            reasons.append(f"Confiance données {conf:.0%} ✓ — analyse fiable")
        elif conf >= 0.45:
            score += 5
            reasons.append(f"Confiance données {conf:.0%} — due diligence complémentaire conseillée")
        else:
            reasons.append(f"Confiance données {conf:.0%} ✗ — données insuffisantes")

        # ── Valorisation estimée ──────────────────────────────────────────────
        val_mult = bench.get("valorisation_multiple") or 0
        arr      = kpis.get("arr") or 0
        if val_mult and arr:
            val_est = arr * val_mult
            reasons.append(f"Valorisation estimée : {val_est:,.0f} TND (ARR × {val_mult}x multiple secteur)")

        # ── Breakeven ─────────────────────────────────────────────────────────
        be_months = kpis.get("breakeven_months")
        be_ok     = kpis.get("breakeven_reachable")
        if be_ok and be_months:
            score += 10
            reasons.append(f"Breakeven atteignable en {be_months:.0f} mois ✓")

        # ── Rating final ──────────────────────────────────────────────────────
        if score >= 70:
            rating = "STRONG_BUY"
            recommendation = "Investissement fortement recommandé — profil de croissance solide."
        elif score >= 50:
            rating = "BUY"
            recommendation = "Investissement recommandé — due diligence standard avant closing."
        elif score >= 30:
            rating = "HOLD"
            recommendation = "En attente — compléter les données et revalider dans 30 jours."
        else:
            rating = "PASS"
            recommendation = "Investissement déconseillé à ce stade — revoir les fondamentaux."

        return {
            "message_id":   str(uuid.uuid4()),
            "type":         "investment_scoring",
            "from":         self.AGENT_ID,
            "to":           ["finance_agent", "orchestrator"],
            "timestamp":    _ts(),
            "context":      finance_msg.get("context", {}),
            "payload": {
                "data": {
                    "in_reply_to":    finance_msg.get("message_id"),
                    "rating":         rating,
                    "score":          score,
                    "recommendation": recommendation,
                    "reasons":        reasons,
                    "phase":          data.get("phase", "unknown"),
                    "secteur":        data.get("secteur", "unknown"),
                    "pays":           data.get("pays", "TN"),
                }
            },
            "confidence": conf,
            "metadata": {
                "priority":          "high" if rating in ("STRONG_BUY", "PASS") else "medium",
                "requires_response": False,
                "tags":              ["investment_scoring", rating.lower(), data.get("secteur", "")],
            },
        }

    def process_inbox(self) -> List[Dict[str, Any]]:
        """
        Lit tous les messages de l'inbox, génère une réponse, publie, acquitte.
        Retourne la liste des réponses envoyées.
        """
        messages  = self.client.get_inbox()
        responses = []

        for msg in messages:
            if msg.get("type") != "financial_analysis":
                continue  # ce mock ne traite que les financial_analysis

            response = self._score(msg)
            self.client.publish_raw(response)
            self.client.ack(msg["message_id"])
            responses.append(response)
            print(
                f"  [investment_agent] reçu {msg['message_id'][:8]}… "
                f"→ {response['payload']['data']['rating']} "
                f"(score {response['payload']['data']['score']}/100)"
            )

        return responses


# ─────────────────────────────────────────────────────────────────────────────
# RISK AGENT MOCK
# ─────────────────────────────────────────────────────────────────────────────

class MockRiskAgent:
    """
    Simule risk_agent.
    Reçoit un message financial_analysis et produit un risk_assessment.
    """

    AGENT_ID = "risk_agent"

    def __init__(self, bus_url: str = "http://localhost:8765"):
        self.client = A2ABusClient(self.AGENT_ID, bus_url)

    def _assess(self, finance_msg: Dict[str, Any]) -> Dict[str, Any]:
        data    = finance_msg.get("payload", {}).get("data", {})
        kpis    = data.get("kpis", {}) or {}
        mc      = data.get("monte_carlo", {}) or {}
        alertes = data.get("alertes", []) or []
        conf    = finance_msg.get("confidence", 0.0) or 0.0

        risks      = []
        risk_score = 0  # 0 = faible, 100 = critique

        # ── Liquidité ────────────────────────────────────────────────────────
        runway = kpis.get("runway_months") or 999
        if runway <= 3:
            risk_score += 45
            risks.append({
                "level":  "CRITIQUE",
                "type":   "liquidite",
                "detail": f"Runway {runway} mois — cash-out imminent",
            })
        elif runway <= 6:
            risk_score += 25
            risks.append({
                "level":  "ÉLEVÉ",
                "type":   "liquidite",
                "detail": f"Runway {runway} mois — levée urgente nécessaire",
            })
        elif runway <= 12:
            risk_score += 10
            risks.append({
                "level":  "MOYEN",
                "type":   "liquidite",
                "detail": f"Runway {runway} mois — surveiller de près",
            })

        # ── Monte Carlo worst case ────────────────────────────────────────────
        p10 = mc.get("p10") or runway
        if p10 <= 2:
            risk_score += 20
            risks.append({
                "level":  "ÉLEVÉ",
                "type":   "monte_carlo",
                "detail": f"Scénario P10 : {p10} mois — pire cas très défavorable",
            })

        # ── Alertes critiques ────────────────────────────────────────────────
        n_critical = sum(1 for a in alertes if "CRITIQUE" in str(a))
        if n_critical > 0:
            risk_score += 10 * n_critical

        # ── Confiance données ────────────────────────────────────────────────
        if conf < 0.45:
            risk_score += 10
            risks.append({
                "level":  "MOYEN",
                "type":   "donnees",
                "detail": f"Confiance {conf:.0%} — projections peu fiables",
            })

        # ── LTV/CAC ──────────────────────────────────────────────────────────
        ltv_cac = kpis.get("ltv_cac_ratio") or 0
        if 0 < ltv_cac < 1:
            risk_score += 15
            risks.append({
                "level":  "ÉLEVÉ",
                "type":   "unit_economics",
                "detail": f"LTV/CAC {ltv_cac:.1f}x — destruction de valeur par client",
            })

        # ── Niveau de risque global ───────────────────────────────────────────
        if risk_score >= 60:
            risk_level = "CRITIQUE"
        elif risk_score >= 35:
            risk_level = "ÉLEVÉ"
        elif risk_score >= 15:
            risk_level = "MOYEN"
        else:
            risk_level = "FAIBLE"

        return {
            "message_id": str(uuid.uuid4()),
            "type":       "risk_assessment",
            "from":       self.AGENT_ID,
            "to":         ["finance_agent", "orchestrator"],
            "timestamp":  _ts(),
            "context":    finance_msg.get("context", {}),
            "payload": {
                "data": {
                    "in_reply_to": finance_msg.get("message_id"),
                    "risk_level":  risk_level,
                    "risk_score":  risk_score,
                    "risks":       risks,
                    "phase":       data.get("phase", "unknown"),
                    "secteur":     data.get("secteur", "unknown"),
                }
            },
            "confidence": conf,
            "metadata": {
                "priority":          "high" if risk_level in ("CRITIQUE", "ÉLEVÉ") else "medium",
                "requires_response": False,
                "tags":              ["risk_assessment", risk_level.lower()],
            },
        }

    def process_inbox(self) -> List[Dict[str, Any]]:
        messages  = self.client.get_inbox()
        responses = []
        for msg in messages:
            if msg.get("type") != "financial_analysis":
                continue
            response = self._assess(msg)
            self.client.publish_raw(response)
            self.client.ack(msg["message_id"])
            responses.append(response)
            print(
                f"  [risk_agent] reçu {msg['message_id'][:8]}… "
                f"→ risque {response['payload']['data']['risk_level']} "
                f"(score {response['payload']['data']['risk_score']}/100)"
            )
        return responses
