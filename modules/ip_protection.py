"""
Module Protection IP — 100% RAG, aucune donnée statique.
Toutes les informations viennent de ChromaDB (INNORPI + SPDX + JORT scrappés).
"""

from dataclasses import dataclass
from rag.pipeline import rag_pipeline, RAGRequest
from scrapers.innorpi import INNORPIScraper
from scrapers.spdx import check_saas_risk, check_stack_compatibility


async def answer(query: str, company_context: dict | None = None, language: str = "fr") -> dict:
    response = await rag_pipeline.run(RAGRequest(
        query=query, language=language, company_context=company_context,
    ))
    return {"answer": response.answer, "sources": response.sources, "requires_lawyer": response.requires_lawyer}


@dataclass
class TrademarkResult:
    candidate_name: str
    risk_level: str
    can_register: bool
    conflicts: list[dict]
    phonetic_matches: list[dict]
    recommendation: str
    legal_basis: str


@dataclass
class LicenseAuditResult:
    stack: list[str]
    overall_risk: str
    saas_compatible: bool
    conflicts: list[dict]
    dangerous_licenses: list[str]
    recommendations: list[str]


class IPProtectionModule:
    def __init__(self):
        self.scraper = INNORPIScraper()

    async def check_trademark(self, name: str, nice_classes: list[int]) -> TrademarkResult:
        matches = await self.scraper.search(name=name, nice_classes=nice_classes)
        conflicts = [m for m in matches if m.get("phonetic_similarity", 0.0) >= 0.75][:10]
        high = any(m.get("phonetic_similarity", 0.0) >= 0.85 for m in conflicts)
        medium = any(m.get("phonetic_similarity", 0.0) >= 0.75 for m in conflicts)

        risk_level = "ELEVE" if high else ("MOYEN" if medium else "FAIBLE")
        can_register = not high
        recommendation = (
            "Risque élevé: prévoir une variante de nom et vérifier avec un conseil IP."
            if high
            else "Risque modéré: lancer une vérification juridique finale avant dépôt."
            if medium
            else "Aucun conflit fort détecté sur ce scraping; vérification finale recommandée."
        )

        return TrademarkResult(
            candidate_name=name,
            risk_level=risk_level,
            can_register=can_register,
            conflicts=conflicts,
            phonetic_matches=matches[:10],
            recommendation=recommendation,
            legal_basis="Code de la propriété industrielle tunisien",
        )

    async def audit_software_licenses(self, stack: list[str], business_model: str = "saas") -> LicenseAuditResult:
        conflicts = check_stack_compatibility(stack)
        dangerous = []
        saas_ok = True

        for spdx in stack:
            info = check_saas_risk(spdx)
            if info.get("risk_level") in {"ELEVE", "CRITIQUE"}:
                dangerous.append(spdx)
            if business_model.lower() == "saas" and not info.get("compatible_saas", True):
                saas_ok = False

        if dangerous:
            overall = "CRITIQUE" if any("AGPL" in d or "SSPL" in d for d in dangerous) else "ELEVE"
        elif conflicts:
            overall = "MOYEN"
        else:
            overall = "FAIBLE"

        recos = [
            "Remplacer les licences à risque élevé (AGPL/SSPL) si possible",
            "Valider la compatibilité de la stack avant distribution",
            "Conserver un inventaire SPDX à jour",
        ]

        return LicenseAuditResult(
            stack=stack,
            overall_risk=overall,
            saas_compatible=saas_ok,
            conflicts=conflicts,
            dangerous_licenses=dangerous,
            recommendations=recos,
        )
