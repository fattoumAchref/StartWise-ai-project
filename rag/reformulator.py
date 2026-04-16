"""
Reformulateur de requêtes — décompose la question du fondateur
en sous-requêtes structurées ciblant les bonnes collections.

"Est-ce que je peux utiliser le nom TakwinTech ?"
→ [SubQuery(trademark_similarity), SubQuery(sector_restriction), SubQuery(registration_conditions)]
"""

import json
import httpx
from dataclasses import dataclass, field
from openai import AsyncOpenAI
from config import cfg

SYSTEM_PROMPT = """Tu es un juriste tunisien expert.
Décompose la question suivante en sous-requêtes de recherche documentaire.
Réponds UNIQUEMENT en JSON avec ce format :
{
  "intent": "type_principal" (creation / trademark / contract / fundraising / compliance / general),
  "language": "fr|ar|en",
  "sub_queries": [
    {
      "text": "requête optimisée pour recherche vectorielle",
      "collection": "legal_articles|trademarks|contract_clauses|court_decisions|tax_regulations|software_licenses",
      "filters": {"field": "value"},
      "priority": 1
    }
  ]
}

Collections disponibles :
- legal_articles : textes législatifs tunisiens (lois, décrets, circulaires)
- trademarks : marques déposées INNORPI
- contract_clauses : clauses de contrats (standards et dangereuses)
- court_decisions : jurisprudence tunisienne
- tax_regulations : barèmes fiscaux DGI/CNSS
- software_licenses : licences logicielles SPDX

Filtres possibles selon collection :
- legal_articles : status (EN_VIGUEUR/MODIFIE/ABROGE), domain (SOCIETES/TRAVAIL/FISCAL/COMMERCIAL), text_type
- trademarks : status (ACTIF), nice_classes (liste d'entiers 1-45)
- contract_clauses : risk_level (FAIBLE/MOYEN/ELEVE/CRITIQUE), contract_type, is_dangerous (true)
- court_decisions : domain (SOCIETES/TRAVAIL/COMMERCIAL/MARQUES/FISCAL), is_landmark (true)
- tax_regulations : tax_type (TVA/IS/IRPP/TFP/CNSS_PATRONAL/CNSS_SALARIAL)
- software_licenses : copyleft_level (none/weak/strong/network), osi_approved (true)"""


@dataclass
class SubQuery:
    text: str
    collection: str
    filters: dict = field(default_factory=dict)
    priority: int = 1


@dataclass
class ReformulatedQuery:
    intent: str
    language: str
    sub_queries: list[SubQuery]
    original_query: str


class QueryReformulator:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            http_client=httpx.AsyncClient(verify=False),
        )

    async def reformulate(
        self,
        query: str,
        company_context: dict | None = None,
        language: str = "fr",
    ) -> ReformulatedQuery:
        """
        Décompose la question utilisateur en sous-requêtes documentaires.
        Le contexte entreprise permet de personnaliser les filtres.
        """
        context_str = ""
        if company_context:
            context_str = (
                f"\nContexte entreprise : {json.dumps(company_context, ensure_ascii=False)}"
            )

        response = await self.client.chat.completions.create(
            model=cfg.llm_model,
            max_tokens=1000,
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question : {query}\nLangue : {language}{context_str}",
                },
            ],
        )

        raw = response.choices[0].message.content.strip()
        # Extraction du JSON (robuste si le LLM ajoute du texte avant/après)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end])

        sub_queries = [
            SubQuery(
                text=sq["text"],
                collection=sq["collection"],
                filters=sq.get("filters", {}),
                priority=sq.get("priority", 1),
            )
            for sq in parsed.get("sub_queries", [])
        ]

        # Fallback : si aucune sous-requête, générer une requête générale
        if not sub_queries:
            sub_queries = [SubQuery(text=query, collection="legal_articles")]

        return ReformulatedQuery(
            intent=parsed.get("intent", "general"),
            language=parsed.get("language", language),
            sub_queries=sorted(sub_queries, key=lambda x: x.priority),
            original_query=query,
        )
