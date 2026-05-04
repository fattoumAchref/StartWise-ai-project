"""
Progress comparator — compares current analysis against project history.
Generates LLM-powered progress narrative when history exists.
"""

from typing import Optional

from finagents.investment.llm_client import chat_completion
from finagents.investment.memory.store import get_project_history


class ProgressComparator:
    """Compares current analysis to previous sessions for the same project."""

    def __init__(self):
        pass

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

            user = (
                f"PREVIOUS SESSION ({previous.get('timestamp', '')[:10]}):\n"
                f"  Stage: {previous.get('stage', 'N/A')} | Revenue: {fmt(previous.get('annual_revenue'))} TND | "
                f"Valuation: {fmt(previous.get('valuation'))} TND | Dilution: {previous.get('dilution', 'N/A')}% | "
                f"Funding asked: {fmt(previous.get('funding_asked'))} TND\n\n"
                f"CURRENT SESSION ({(current.get('timestamp') or '')[:10]}):\n"
                f"  Stage: {current.get('stage', 'N/A')} | Revenue: {fmt(current.get('annual_revenue'))} TND | "
                f"Valuation: {fmt(current.get('valuation'))} TND | Dilution: {current.get('dilution', 'N/A')}% | "
                f"Funding asked: {fmt(current.get('funding_asked'))} TND"
            )
            text = chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a startup investment advisor tracking a startup's progress over time. "
                            "Compare the two analysis sessions and write a 3-sentence progress report. "
                            "Highlight what improved, what worsened, and what the key milestone is next. "
                            "Be specific with numbers. Currency is TND."
                        ),
                    },
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=350,
            )
            if not text:
                return "(progress report unavailable: empty LLM response)"
            return text
        except Exception as e:
            return f"(progress report unavailable: {e})"
