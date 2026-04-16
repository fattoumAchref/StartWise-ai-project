"""
Générateur — appel LLM avec prompt structuré incluant les chunks et métadonnées.
Garant de la qualité juridique : toute affirmation doit être ancrée dans une source.
"""

import json
import httpx
from dataclasses import dataclass
from openai import AsyncOpenAI
from config import cfg
from rag.retriever import RetrievedChunk

# ─────────────────────────────────────────────
# PROMPT SYSTÈME
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """Tu es l'Agent Légal IA, conseiller juridique expert en droit tunisien des affaires.
Tu accompagnes les fondateurs de startups et PME tunisiennes sans qu'ils aient besoin de connaître le droit.

LANGUE DE RÉPONSE : {language}
NIVEAU D'EXPERTISE DE L'UTILISATEUR : {expertise_level}
(NOVICE = langage simple | INTERMEDIATE = quelques termes juridiques | ADVANCED = langage juridique complet)

CONTEXTE ENTREPRISE :
{company_context}

SOURCES RÉCUPÉRÉES — cite-les systématiquement :
{sources_block}

RÈGLES ABSOLUES — ne jamais les enfreindre :
1. Ne cite jamais une loi sans son numéro et sa date de publication au JORT
2. Si une source a le statut ABROGE, commence par signaler que ce texte est abrogé
3. Si une source date de plus de 2 ans, ajoute l'avertissement ⚠️ présent dans les métadonnées
4. Pour tout acte engageant définitivement (signature de statuts, pacte d'actionnaires,
   représentation en justice), recommande systématiquement la validation par un avocat
5. Ne génère jamais d'affirmation juridique sans base légale dans tes sources
6. Si tu n'as pas de source pour répondre, dis-le clairement

FORMAT DE RÉPONSE :
**Réponse directe**
[Réponse à la question en {n_sentences} phrases maximum selon la complexité]

**Base légale**
[Référence exacte : Texte — Numéro JORT — Article]

**Cas similaire** *(si jurisprudence disponible)*
[Décision de référence et ce qu'elle retient]

**À faire**
[Action concrète recommandée, étape par étape]

**⚖️ Validation avocat**
[obligatoire | recommandée | non nécessaire — et pourquoi]
"""


@dataclass
class GeneratorResponse:
    answer: str
    sources: list[str]
    intent: str
    requires_lawyer: bool
    generated_document: str | None = None


class Generator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            http_client=httpx.AsyncClient(verify=False),
        )

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        warnings: list[tuple[RetrievedChunk, str]],
        intent: str,
        language: str = "fr",
        expertise_level: str = "NOVICE",
        company_context: dict | None = None,
    ) -> GeneratorResponse:
        """
        Génère la réponse finale ancrée dans les sources récupérées.
        """
        sources_block = self._build_sources_block(warnings)
        company_str = json.dumps(company_context or {}, ensure_ascii=False, indent=2)

        system = SYSTEM_PROMPT.format(
            language=language,
            expertise_level=expertise_level,
            company_context=company_str,
            sources_block=sources_block,
            n_sentences="5-10",
        )

        response = await self.client.chat.completions.create(
            model=cfg.llm_model,
            max_tokens=2000,
            temperature=0.3,
            top_p=0.9,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ],
        )

        answer = response.choices[0].message.content
        source_labels = [c.source_label for c in chunks]
        requires_lawyer = self._needs_lawyer(intent, answer)

        return GeneratorResponse(
            answer=answer,
            sources=source_labels,
            intent=intent,
            requires_lawyer=requires_lawyer,
        )

    async def generate_document(
        self,
        template_type: str,
        variables: dict,
        legal_basis: str,
        language: str = "fr",
    ) -> str:
        """
        Génère un document juridique (contrat, statuts, etc.) depuis un template.
        """
        system = f"""Tu es un juriste tunisien spécialisé en droit des affaires.
Génère un {template_type} en {language}, conforme au droit tunisien.
Base légale : {legal_basis}
Variables : {json.dumps(variables, ensure_ascii=False)}

EXIGENCES :
- Document complet et directement utilisable
- Conforme au Code des sociétés commerciales / Code du Travail / COC tunisien
- Inclure toutes les clauses obligatoires
- Mentionner "À valider par un avocat avant signature définitive" en fin de document
- Droit applicable : droit tunisien | Juridiction : tribunaux tunisiens compétents"""

        response = await self.client.chat.completions.create(
            model=cfg.llm_model,
            max_tokens=4000,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Génère le {template_type}"},
            ],
        )
        return response.choices[0].message.content

    # ── Privé ─────────────────────────────────────────────────────

    def _build_sources_block(
        self, warnings: list[tuple[RetrievedChunk, str]]
    ) -> str:
        """Formate les sources avec leurs métadonnées pour le prompt."""
        if not warnings:
            return "Aucune source spécifique récupérée."

        parts = []
        for i, (chunk, warning) in enumerate(warnings, 1):
            meta = chunk.metadata
            status = meta.get("status", "")
            status_flag = "🔴 ABROGÉ — " if status == "ABROGE" else ("🟡 MODIFIÉ — " if status == "MODIFIE" else "")

            parts.append(
                f"[SOURCE {i}] {status_flag}{chunk.source_label}\n"
                f"{warning}\n"
                f"{chunk.content[:1500]}\n"
            )

        return "\n---\n".join(parts)

    def _needs_lawyer(self, intent: str, answer: str) -> bool:
        """Détermine si une validation avocat est requise."""
        high_risk_intents = {"corporate", "fundraising", "shareholders_pact"}
        keywords = ["pacte d'actionnaires", "statuts", "représentation en justice",
                    "cession de parts", "augmentation de capital", "dissolution"]
        if intent in high_risk_intents:
            return True
        return any(kw in answer.lower() for kw in keywords)
