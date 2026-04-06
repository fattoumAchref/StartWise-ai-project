"""
Orchestrator - coordinates Parser → Finance → Marketing → Investment Agent.
"""

import sys
import os
import uuid

# Ensure workspace root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrateur.project_parser import ProjectParser
from agents.finance.main import FinanceAgent
from agents.marketing.main import MarketingAgent
from agents.investment.main import InvestmentAgent
from orchestrateur.models import StartupProject


class Orchestrator:
    """
    Full end-to-end orchestrator.

    Flow:
        User text
            -> ProjectParser  (LLM extracts structured data)
            -> FinanceAgent   (financial analysis)
            -> MarketingAgent (market analysis)
            -> InvestmentAgent (valuation + strategy + recommendation)
    """

    def __init__(self):
        self.parser     = ProjectParser()
        self.finance    = FinanceAgent()
        self.marketing  = MarketingAgent()
        self.investment = InvestmentAgent()

    def process(self, raw_text: str, user_id: str = "user_001", project_id: str = None) -> dict:
        """
        Run the full pipeline on a user project description.
        Pass a stable project_id to enable memory tracking across sessions.
        """
        if project_id is None:
            project_id = f"proj_{uuid.uuid4().hex[:8]}"

        print("\n" + "="*65)
        print("  ORCHESTRATOR — STARTING PIPELINE")
        print("="*65)

        # Step 1: Parse
        project = self.parser.parse(raw_text, project_id, user_id)

        # Step 2: Finance analysis
        finance_msg = self.finance.analyze(project)

        # Step 3: Marketing analysis
        marketing_msg = self.marketing.analyze(project)

        # Step 4: Investment analysis
        investment_result = self.investment.analyze(
            finance_data=finance_msg.data,
            marketing_data=marketing_msg.data,
            project_id=project_id,
            user_id=user_id,
        )

        print("\n" + "="*65)
        print("  ORCHESTRATOR — PIPELINE COMPLETE")
        print("="*65)

        return {
            "project":    project,
            "finance":    finance_msg.to_dict(),
            "marketing":  marketing_msg.to_dict(),
            "investment": investment_result,
        }
