"""
Strategy selector - scores scenarios and explains the optimal choice with LLM.
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from finagents.investment.models import FundingScenario
from finagents.investment.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME


class StrategySelector:
    """Scores scenarios, selects the best, and generates an LLM explanation."""

    DILUTION_TARGETS = {
        "idea":     15,
        "pre-seed": 15,
        "seed":     20,
        "early":    25,
        "growth":   30,
        "scale":    20,
    }

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.3,
            max_tokens=250,
        )

    def select_optimal(self, scenarios: list, stage: str = "seed") -> FundingScenario:
        """
        Score each scenario, pick the best, attach an LLM rationale.
        """
        if not scenarios:
            # Fallback: return a minimal placeholder scenario so the pipeline never crashes
            return FundingScenario(
                name="bootstrap",
                raise_amount=0,
                equity=0,
                debt=0,
                grants=0,
                dilution_pct=0.0,
                score=0.0,
                rationale="Données insuffisantes pour générer des scénarios de financement.",
            )

        target_dilution = self.DILUTION_TARGETS.get(stage, 25)

        for s in scenarios:
            score = 100.0

            diff = s.dilution_pct - target_dilution
            score += -diff * 5 if diff > 0 else abs(diff) * 2

            grants_ratio = s.grants / s.raise_amount if s.raise_amount > 0 else 0
            score += grants_ratio * 20

            if s.name == "optimal":
                score += 10

            debt_ratio = s.debt / s.raise_amount if s.raise_amount > 0 else 0
            if stage in ("idea", "pre-seed", "seed") and debt_ratio > 0.20:
                score -= 10

            s.score = round(score, 1)

        scenarios.sort(key=lambda s: s.score, reverse=True)
        best = scenarios[0]

        # LLM explains why this scenario was selected
        best.rationale = self._explain(best, scenarios, stage)
        return best

    def _explain(self, best: FundingScenario, all_scenarios: list, stage: str) -> str:
        """Generate a short LLM rationale for the selected scenario."""
        try:
            others = [s for s in all_scenarios if s.name != best.name]
            others_text = " | ".join(
                f"{s.name}: raise={s.raise_amount:,.0f} TND, dilution={s.dilution_pct:.1f}%, score={s.score}"
                for s in others
            )
            prompt = ChatPromptTemplate.from_messages([
                ("system",
                 "Tu es un conseiller en investissement spécialisé dans les startups tunisiennes. "
                 "Explique en 2-3 phrases pourquoi le scénario de financement sélectionné est optimal "
                 "pour ce stade de startup. Sois précis sur la dilution, les subventions et le risque. "
                 "La devise est le TND. Sois concis."),
                ("user",
                 "Stade: {stage}\n"
                 "Sélectionné: {name} — levée {raise_amt} TND, subventions {grants} TND, "
                 "equity {equity} TND, dette {debt} TND, dilution {dilution}%, score {score}\n"
                 "Alternatives: {others}")
            ])
            chain = prompt | self.llm
            response = chain.invoke({
                "stage":     stage,
                "name":      best.name,
                "raise_amt": f"{best.raise_amount:,.0f}",
                "grants":    f"{best.grants:,.0f}",
                "equity":    f"{best.equity:,.0f}",
                "debt":      f"{best.debt:,.0f}",
                "dilution":  f"{best.dilution_pct:.1f}",
                "score":     best.score,
                "others":    others_text,
            })
            return response.content.strip()
        except Exception as e:
            return f"(rationale unavailable: {e})"
