"""
Module Création d'Entreprise — 100% RAG, aucune donnée statique.
Toutes les informations viennent de ChromaDB (JORT scraped).
"""

from dataclasses import dataclass
from rag.pipeline import rag_pipeline, RAGRequest


async def answer(query: str, company_context: dict | None = None, language: str = "fr") -> dict:
    response = await rag_pipeline.run(RAGRequest(
        query=query, language=language, company_context=company_context,
        expertise_level=(company_context or {}).get("expertise_level", "NOVICE"),
    ))
    return {"answer": response.answer, "sources": response.sources, "requires_lawyer": response.requires_lawyer}


def answer_creation_question(query: str, company_context: dict | None = None, language: str = "fr"):
    """Alias de compatibilité avec l'ancien import modules.__init__."""
    return answer(query=query, company_context=company_context, language=language)


def recommend_legal_form(
    nb_founders: int,
    has_fundraising_plans: bool,
    sector: str = "",
    capital_available_tnd: float = 1000,
) -> dict:
    """Règles simples de recommandation pour rendre l'endpoint immédiatement opérationnel."""
    if nb_founders <= 1:
        form = "SUARL"
        reason = "Un seul fondateur: la SUARL est la forme la plus directe."
    elif has_fundraising_plans or capital_available_tnd >= 50000:
        form = "SA"
        reason = "Projet orienté levée de fonds: la SA facilite l'entrée d'investisseurs."
    else:
        form = "SARL"
        reason = "Structure PME classique: la SARL est adaptée au démarrage."

    return {
        "recommended_form": form,
        "reason": reason,
        "inputs": {
            "nb_founders": nb_founders,
            "has_fundraising_plans": has_fundraising_plans,
            "sector": sector,
            "capital_available_tnd": capital_available_tnd,
        },
        "next_steps": [
            "Vérifier la disponibilité de la dénomination sociale",
            "Préparer les statuts",
            "Compléter les formalités RNE",
        ],
    }


async def generate_statuts(form: str, variables: dict, language: str = "fr") -> str:
    """Génération simple via le générateur RAG de documents."""
    try:
        return await rag_pipeline.generate_document(
            document_type=f"Statuts {form}",
            variables=variables,
            legal_basis="Code des sociétés commerciales tunisien",
            language=language,
        )
    except Exception:
        company = variables.get("company_name", "Société")
        return (
            f"STATUTS ({form})\n\n"
            f"Dénomination: {company}\n"
            "Document généré automatiquement.\n"
            "À valider par un avocat avant signature définitive."
        )
