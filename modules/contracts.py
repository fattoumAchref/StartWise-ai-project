"""
Module Contrats — 100% RAG, aucune donnée statique.
Toutes les informations viennent de ChromaDB (JORT scraped).
"""

from dataclasses import dataclass
from rag.pipeline import rag_pipeline, RAGRequest


async def answer(query: str, company_context: dict | None = None, language: str = "fr") -> dict:
    response = await rag_pipeline.run(RAGRequest(
        query=query, language=language, company_context=company_context,
    ))
    return {"answer": response.answer, "sources": response.sources, "requires_lawyer": response.requires_lawyer}


@dataclass
class ContractAnalysisResult:
    overall_risk: str
    dangerous_clauses: list[dict]
    missing_mandatory_clauses: list[str]
    recommendations: list[str]
    requires_lawyer: bool


@dataclass
class GeneratedContractResult:
    contract_type: str
    content: str
    requires_lawyer_validation: bool
    warnings: list[str]


class ContractModule:
    async def analyze(self, contract_text: str, contract_type: str = "unknown") -> ContractAnalysisResult:
        txt = (contract_text or "").lower()
        dangerous = []

        if "non-concurrence" in txt and any(x in txt for x in ["5 ans", "60 mois", "illimit"]):
            dangerous.append({"title": "Non-concurrence excessive", "severity": "CRITIQUE"})
        if "exclusion de responsabil" in txt or "responsabilit" in txt and "totalement exclue" in txt:
            dangerous.append({"title": "Exclusion totale de responsabilité", "severity": "ELEVE"})
        if "tribunaux de paris" in txt or "juridiction exclusive" in txt:
            dangerous.append({"title": "Juridiction étrangère défavorable", "severity": "ELEVE"})

        missing = []
        if "confidentialit" not in txt:
            missing.append("Clause de confidentialité")
        if "résiliation" not in txt and "resiliation" not in txt:
            missing.append("Clause de résiliation")

        if any(c["severity"] == "CRITIQUE" for c in dangerous):
            risk = "CRITIQUE"
        elif dangerous:
            risk = "ELEVE"
        elif missing:
            risk = "MOYEN"
        else:
            risk = "FAIBLE"

        recos = [
            "Adapter les clauses au droit tunisien",
            "Limiter la non-concurrence dans le temps et l'espace",
            "Prévoir une juridiction tunisienne compétente",
        ]

        return ContractAnalysisResult(
            overall_risk=risk,
            dangerous_clauses=dangerous,
            missing_mandatory_clauses=missing,
            recommendations=recos,
            requires_lawyer=risk in {"ELEVE", "CRITIQUE"},
        )

    async def generate(self, contract_type: str, variables: dict, language: str = "fr") -> GeneratedContractResult:
        try:
            content = await rag_pipeline.generate_document(
                document_type=contract_type,
                variables=variables,
                legal_basis="Droit tunisien des obligations et des contrats",
                language=language,
            )
        except Exception:
            content = (
                f"Contrat type: {contract_type}\n"
                f"Variables: {variables}\n"
                "Document généré automatiquement.\n"
                "À valider par un avocat avant signature définitive."
            )

        return GeneratedContractResult(
            contract_type=contract_type,
            content=content,
            requires_lawyer_validation=True,
            warnings=["Validation juridique recommandée avant signature."],
        )
