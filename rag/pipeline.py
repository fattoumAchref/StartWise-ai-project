"""
Pipeline RAG orchestré — point d'entrée unique pour toutes les questions.

Flux :
  Question → Reformulateur → Retriever (parallel) → Reranker → Générateur → Réponse
"""

from dataclasses import dataclass
from rag.reformulator import QueryReformulator
from rag.retriever import Retriever
from rag.reranker import Reranker
from rag.generator import Generator, GeneratorResponse
import structlog

log = structlog.get_logger("rag.pipeline")


@dataclass
class RAGRequest:
    query: str
    language: str = "fr"
    expertise_level: str = "NOVICE"
    company_context: dict | None = None
    top_k_retrieve: int = 20
    top_n_rerank: int = 5


class RAGPipeline:
    """
    Pipeline RAG complet pour l'agent légal tunisien.

    Chaque étape est séparée pour permettre l'observabilité et le debug.
    """

    def __init__(self):
        self.reformulator = QueryReformulator()
        self.retriever = Retriever()
        self.reranker = Reranker()
        self.generator = Generator()

    async def run(self, request: RAGRequest) -> GeneratorResponse:
        """Exécute le pipeline RAG complet."""

        log.info("pipeline_start", query=request.query[:80], lang=request.language)

        # 1. Reformulation : question → sous-requêtes structurées
        reformulated = await self.reformulator.reformulate(
            query=request.query,
            company_context=request.company_context,
            language=request.language,
        )
        log.info(
            "reformulated",
            intent=reformulated.intent,
            sub_queries=len(reformulated.sub_queries),
        )

        # 2. Retrieval parallèle dans les collections vectorielles
        raw_chunks = await self.retriever.retrieve(
            sub_queries=reformulated.sub_queries,
            top_k=request.top_k_retrieve,
        )
        log.info("retrieved", chunks=len(raw_chunks))

        # 3. Reranking cross-encoder + ajustements légaux
        reranked = await self.reranker.rerank(
            query=request.query,
            chunks=raw_chunks,
            domain=self._extract_domain(reformulated.intent),
            top_n=request.top_n_rerank,
        )

        # 4. Ajout des avertissements de fraîcheur
        with_warnings = self.reranker.add_staleness_warnings(reranked)

        log.info("reranked", final_chunks=len(reranked))

        # 5. Génération de la réponse
        response = await self.generator.generate(
            query=request.query,
            chunks=reranked,
            warnings=with_warnings,
            intent=reformulated.intent,
            language=request.language,
            expertise_level=request.expertise_level,
            company_context=request.company_context,
        )

        log.info("generated", intent=reformulated.intent, requires_lawyer=response.requires_lawyer)
        return response

    async def generate_document(
        self,
        document_type: str,
        variables: dict,
        legal_basis: str,
        language: str = "fr",
    ) -> str:
        """Génère un document juridique directement utilisable."""
        return await self.generator.generate_document(
            template_type=document_type,
            variables=variables,
            legal_basis=legal_basis,
            language=language,
        )

    def _extract_domain(self, intent: str) -> str:
        mapping = {
            "creation": "SOCIETES",
            "trademark": "MARQUES",
            "contract": "COMMERCIAL",
            "fundraising": "SOCIETES",
            "compliance": "FISCAL",
            "labor": "TRAVAIL",
        }
        return mapping.get(intent, "")


# Singleton
rag_pipeline = RAGPipeline()
