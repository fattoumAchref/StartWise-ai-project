"""
Modèles de données simplifiés pour le MVP.
"""

from dataclasses import dataclass, field
from typing import Optional, Any
from datetime import datetime


@dataclass
class StartupProject:
    """Projet startup simplifié."""
    project_id: str
    user_id: str
    raw_text: str
    
    # Données extraites
    business_model: Optional[str] = None
    industry: Optional[str] = None
    annual_revenue: Optional[float] = None
    growth_rate: Optional[float] = None
    monthly_burn_rate: Optional[float] = None
    funding_needed: Optional[float] = None
    team_size: Optional[int] = None
    tam: Optional[float] = None
    
    submitted_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentMessage:
    """Message d'un agent."""
    agent_id: str
    project_id: str
    recommendation: str
    confidence_score: float
    data: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "project_id": self.project_id,
            "recommendation": self.recommendation,
            "confidence_score": self.confidence_score,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "dependencies": []
        }