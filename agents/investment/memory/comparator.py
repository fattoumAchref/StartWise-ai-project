"""
Progress comparator — compares current analysis against project history.
Generates LLM-powered progress narrative when history exists.
"""

from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME
from agents.investment.memory.store import get_project_history


class ProgressComparator:
    """Compares current analysis to previous sessions for the same project."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.3,
            max_tokens=350,
        )

    def compare(self, project_id: str, current: dict) -> Optional[str]:
        """
        Load history for project_id and compare with current result.
        Returns a progress summary string, or None if no history.
        """
        history = get_project_history(project_id)

        # Filter out the entry we just saved (same timestamp within seconds)
        # Keep only entries before the current one
        if len(history) < 2:
            return None  # first time — nothing to compare

        previous = history[-2]  # second-to-last = previous session
        current_data = current.get("data", {})
        val  = current_data.get("valuation", {})
        scen = current_data.get("optimal_scenario", {})
        dil  = current_data.get("dilution", {})

        return self._generate_progress(previous, {
            "stage":          current_data.get("stage"),
            "sector":         current_data.get("sector") or current_data.get("industry"),
            "annual_revenue": current_data.get("annual_revenue"),
            "valuation":      val.get("final_valuation"),
            "funding_asked":  scen.get("raise_amount"),
            "dilution":       dil.get("founder_dilution_pct"),
            "confidence":     current.get("confidence_score"),
            "timestamp":      current.get("timestamp"),
        })

    def _generate_progress(self, previous: dict, current: dict) -> str:
        """LLM generates a progress narrative comparing two sessions."""
        try:
            def fmt(v):
                return f"{v:,.0f}" if isinstance(v, (int, float)) and v else "N/A"

            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "You are a startup investment advisor tracking a startup's progress over time. "
                 "Compare the two analysis sessions and write a 3-sentence progress report. "
                 "Highlight what improved, what worsened, and what the key milestone is next. "
                 "Be specific with numbers. Currency is TND."),
                ("user",
                 "PREVIOUS SESSION ({prev_date}):\n"
                 "  Stage: {prev_stage} | Revenue: {prev_rev} TND | "
                 "Valuation: {prev_val} TND | Dilution: {prev_dil}% | "
                 "Funding asked: {prev_fund} TND\n\n"
                 "CURRENT SESSION ({curr_date}):\n"
                 "  Stage: {curr_stage} | Revenue: {curr_rev} TND | "
                 "Valuation: {curr_val} TND | Dilution: {curr_dil}% | "
                 "Funding asked: {curr_fund} TND")
            ])
            chain = prompt | self.llm
            response = chain.invoke({
                "prev_date":  previous.get("timestamp", "")[:10],
                "prev_stage": previous.get("stage", "N/A"),
                "prev_rev":   fmt(previous.get("annual_revenue")),
                "prev_val":   fmt(previous.get("valuation")),
                "prev_dil":   previous.get("dilution", "N/A"),
                "prev_fund":  fmt(previous.get("funding_asked")),
                "curr_date":  (current.get("timestamp") or "")[:10],
                "curr_stage": current.get("stage", "N/A"),
                "curr_rev":   fmt(current.get("annual_revenue")),
                "curr_val":   fmt(current.get("valuation")),
                "curr_dil":   current.get("dilution", "N/A"),
                "curr_fund":  fmt(current.get("funding_asked")),
            })
            return response.content.strip()
        except Exception as e:
            return f"(progress report unavailable: {e})"
