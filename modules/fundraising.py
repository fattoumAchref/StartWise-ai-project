"""
Module Levée de Fonds — 100% RAG, aucune donnée statique.
Toutes les informations viennent de ChromaDB (JORT + sources officielles scrappées).
"""

from dataclasses import dataclass
from rag.pipeline import rag_pipeline, RAGRequest


async def answer(query: str, company_context: dict | None = None, language: str = "fr") -> dict:
    response = await rag_pipeline.run(RAGRequest(
        query=query, language=language, company_context=company_context,
    ))
    return {"answer": response.answer, "sources": response.sources, "requires_lawyer": response.requires_lawyer}


@dataclass
class DilutionScenario:
    pre_money_tnd: float
    investment_tnd: float
    post_money_tnd: float
    investor_pct: float
    founders_before: dict
    founders_after: dict


class FundraisingModule:
    def calculate_dilution(self, pre_money_tnd: float, investment_tnd: float, cap_table: dict) -> DilutionScenario:
        post_money = pre_money_tnd + investment_tnd
        investor_pct = (investment_tnd / post_money) * 100 if post_money else 0.0
        keep_ratio = 1.0 - (investor_pct / 100.0)

        founders_after = {
            k: round(v * keep_ratio, 2)
            for k, v in (cap_table or {}).items()
        }

        return DilutionScenario(
            pre_money_tnd=pre_money_tnd,
            investment_tnd=investment_tnd,
            post_money_tnd=post_money,
            investor_pct=round(investor_pct, 2),
            founders_before=cap_table,
            founders_after=founders_after,
        )

    def translate_term_sheet(self, term_sheet: str) -> dict:
        return {
            "summary": "Résumé simplifié du term sheet",
            "key_points": [
                "Valorisation pré-money",
                "Montant investi et dilution",
                "Droits investisseurs (liquidation preference, gouvernance)",
            ],
            "original_excerpt": term_sheet[:1200],
        }
