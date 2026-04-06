"""
Data models for Investment Agent MVP.
"""

import uuid as _uuid
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ValuationResult:
    """Valuation calculation result."""
    revenue_multiple: Optional[float] = None
    dcf: Optional[float] = None
    scorecard: Optional[float] = None
    final_valuation: float = 0.0
    method_used: str = "hybrid"


@dataclass
class DilutionResult:
    """Dilution calculation result."""
    pre_money: float
    raise_amount: float
    post_money: float
    new_investor_pct: float
    founder_before_pct: float
    founder_after_pct: float
    founder_dilution_pct: float


@dataclass
class FundingScenario:
    """Single funding scenario."""
    name: str
    raise_amount: float
    grants: float
    equity: float
    debt: float
    pre_money: float
    post_money: float
    dilution_pct: float
    score: float = 0.0
    rationale: str = ""  # LLM-generated explanation


@dataclass
class InvestmentRecommendation:
    """Final investment recommendation."""
    agent_id: str = "investment"
    recommendation: str = ""
    confidence_score: float = 0.0
    
    valuation: Optional[ValuationResult] = None
    optimal_scenario: Optional[FundingScenario] = None
    all_scenarios: list = field(default_factory=list)
    dilution: Optional[DilutionResult] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "timestamp": self.timestamp.isoformat(),
            "data": {
                "valuation": {
                    "revenue_multiple": self.valuation.revenue_multiple if self.valuation else None,
                    "dcf": self.valuation.dcf if self.valuation else None,
                    "scorecard": self.valuation.scorecard if self.valuation else None,
                    "final_valuation": self.valuation.final_valuation if self.valuation else None,
                    "method": self.valuation.method_used if self.valuation else None,
                },
                "optimal_scenario": {
                    "name": self.optimal_scenario.name,
                    "raise_amount": self.optimal_scenario.raise_amount,
                    "grants": self.optimal_scenario.grants,
                    "equity": self.optimal_scenario.equity,
                    "debt": self.optimal_scenario.debt,
                    "dilution_pct": self.optimal_scenario.dilution_pct,
                    "post_money": self.optimal_scenario.post_money,
                    "score": self.optimal_scenario.score,
                    "rationale": self.optimal_scenario.rationale,
                } if self.optimal_scenario else None,
                "all_scenarios": [
                    {
                        "name": s.name,
                        "raise_amount": s.raise_amount,
                        "grants": s.grants,
                        "equity": s.equity,
                        "dilution_pct": s.dilution_pct,
                        "score": s.score,
                    }
                    for s in self.all_scenarios
                ],
                "dilution": {
                    "pre_money": self.dilution.pre_money,
                    "post_money": self.dilution.post_money,
                    "new_investor_pct": self.dilution.new_investor_pct,
                    "founder_before_pct": self.dilution.founder_before_pct,
                    "founder_after_pct": self.dilution.founder_after_pct,
                    "founder_dilution_pct": self.dilution.founder_dilution_pct,
                } if self.dilution else None,
            }
        }

    def to_a2a_message(
        self,
        project_id: str = None,
        session_id: str = None,
        to: list = None,
        event_type: str = "investment.recommendation",
        priority: str = "high",
        requires_response: bool = False,
        tags: list = None,
    ) -> dict:
        """
        Wrap the result in the A2A message envelope format.

        Args:
            project_id      : stable project identifier
            session_id      : current session identifier
            to              : list of recipient agent names
            event_type      : message type (default: investment.recommendation)
            priority        : low | medium | high
            requires_response: whether a response is expected
            tags            : optional list of tags

        Returns:
            A2A-compliant message dict
        """
        inner = self.to_dict()

        return {
            "message_id": str(_uuid.uuid4()),
            "type": event_type,
            "from": "InvestmentAgent",
            "to": to or ["Orchestrator"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "context": {
                "project_id": project_id or str(_uuid.uuid4()),
                "session_id": session_id or str(_uuid.uuid4()),
            },
            "payload": {
                "data": inner["data"],
                "recommendation": inner["recommendation"],
            },
            "confidence": inner["confidence_score"],
            "metadata": {
                "priority": priority,
                "requires_response": requires_response,
                "tags": tags or [
                    inner["data"].get("stage", "unknown"),
                    inner["data"].get("sector") or inner["data"].get("industry", "unknown"),
                    inner.get("agent_id", "investment"),
                ],
            },
        }