"""
Stage detector - classifies startup maturity stage.
"""

from agents.investment.config import STAGE_THRESHOLDS


class StageDetector:
    """Detects startup stage based on revenue."""

    # Ordered list for threshold comparison
    _STAGES = ["idea", "pre-seed", "seed", "early", "growth", "scale"]

    def detect(self, annual_revenue: float) -> str:
        """
        Classify startup stage by annual revenue (TND).

        Thresholds:
            idea      : 0
            pre-seed  : > 0
            seed      : > 50k
            early     : > 200k
            growth    : > 500k
            scale     : > 2M
        """
        stage = "idea"
        for s in self._STAGES:
            if annual_revenue >= STAGE_THRESHOLDS[s]:
                stage = s
        return stage

    def get_target_funding_type(self, stage: str) -> str:
        """Map stage to typical funding source."""
        mapping = {
            "idea":     "incubator",
            "pre-seed": "angel",
            "seed":     "accelerator",
            "early":    "seed_vc",
            "growth":   "vc",
            "scale":    "growth_equity",
        }
        return mapping.get(stage, "vc")
