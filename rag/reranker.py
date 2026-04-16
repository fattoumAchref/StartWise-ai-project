"""
Reranker cross-encoder — réduit top-20 cosine → top-3 fiable.

Pénalités légales critiques :
- Statut ABROGE : -0.8 (un texte abrogé ne doit jamais être cité comme source)
- Texte > 2 ans sans vérification : -0.2
- Domaine correct : +0.3

Sans reranking, un article abrogé très similaire sémantiquement au texte en vigueur
qui l'a remplacé remonterait en premier — erreur fatale pour un conseiller juridique.
"""

from datetime import datetime
import cohere
from config import cfg
from rag.retriever import RetrievedChunk


class Reranker:
    def __init__(self):
        self.client = cohere.AsyncClientV2(api_key=cfg.cohere_api_key)
        self.model = "rerank-multilingual-v3.0"

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        domain: str = "",
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """
        Reranking cross-encoder + ajustements légaux spécifiques.
        Retourne les top_n chunks les plus pertinents et fiables.
        """
        if not chunks:
            return []

        # 1. Cross-encoder Cohere (multilingue ar/fr/en)
        documents = [c.content[:2000] for c in chunks]
        try:
            response = await self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=len(chunks),
            )
            # Scores du cross-encoder
            ce_scores = {r.index: r.relevance_score for r in response.results}
        except Exception:
            # Fallback sur les scores cosine si Cohere indisponible
            ce_scores = {i: c.score for i, c in enumerate(chunks)}

        # 2. Ajustements légaux
        scored = []
        for i, chunk in enumerate(chunks):
            score = ce_scores.get(i, 0.0)
            score += self._legal_adjustments(chunk, domain)
            scored.append((chunk, score))

        # 3. Tri et retour top_n
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top_n]]

    def _legal_adjustments(self, chunk: RetrievedChunk, domain: str) -> float:
        """Pénalités et bonus spécifiques au domaine juridique tunisien."""
        adj = 0.0
        meta = chunk.metadata

        status = meta.get("status", "EN_VIGUEUR")

        # CRITIQUE : pénalité forte sur texte abrogé
        if status == "ABROGE":
            adj -= 0.8

        # Pénalité sur texte modifié (peut être périmé)
        if status == "MODIFIE":
            adj -= 0.2

        # Pénalité si texte non vérifié depuis 2 ans
        pub_date_str = meta.get("publication_date") or meta.get("effective_from") or ""
        if pub_date_str:
            try:
                pub_date = datetime.fromisoformat(pub_date_str[:10])
                years_old = (datetime.now() - pub_date).days / 365
                if years_old > 2:
                    adj -= 0.2
            except (ValueError, TypeError):
                pass

        # Bonus si le domaine correspond à la requête
        chunk_domain = meta.get("domain", "")
        if domain and chunk_domain and domain.upper() == chunk_domain.upper():
            adj += 0.3

        # Bonus sur les décisions de principe (jurisprudence)
        if meta.get("is_landmark"):
            adj += 0.2

        return adj

    def add_staleness_warnings(
        self, chunks: list[RetrievedChunk]
    ) -> list[tuple[RetrievedChunk, str]]:
        """
        Ajoute un avertissement si un texte date de plus de 2 ans.
        Ces avertissements sont injectés dans la réponse finale.
        """
        result = []
        for chunk in chunks:
            warning = ""
            pub_date_str = chunk.metadata.get("publication_date") or chunk.metadata.get("effective_from") or ""
            if pub_date_str:
                try:
                    pub_date = datetime.fromisoformat(pub_date_str[:10])
                    years_old = (datetime.now() - pub_date).days / 365
                    if years_old > 2:
                        warning = (
                            f"⚠️ Ce texte date de {pub_date.year} "
                            f"— vérifier qu'il n'a pas été modifié depuis."
                        )
                except (ValueError, TypeError):
                    pass
            result.append((chunk, warning))
        return result
