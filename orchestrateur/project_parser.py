"""
Parse le projet user avec le LLM.
"""

import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from orchestrateur.config import TOKENFACTORY_API_KEY, BASE_URL, MODEL_NAME
from orchestrateur.models import StartupProject


class ProjectParser:
    """Parse user text into StartupProject."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL_NAME,
            base_url=BASE_URL,
            api_key=TOKENFACTORY_API_KEY,
            temperature=0.1,
            max_tokens=2000,
        )
    
    def parse(self, raw_text: str, project_id: str, user_id: str) -> StartupProject:
        """Parse text into StartupProject."""
        
        print(f"\n[Parser] Parsing project {project_id}...")
        
        # Extract data with LLM
        extracted = self._extract_with_llm(raw_text)
        
        # Build project
        project = StartupProject(
            project_id=project_id,
            user_id=user_id,
            raw_text=raw_text,
            business_model=extracted.get("business_model"),
            industry=extracted.get("industry"),
            annual_revenue=extracted.get("annual_revenue"),
            growth_rate=extracted.get("growth_rate"),
            monthly_burn_rate=extracted.get("monthly_burn_rate"),
            funding_needed=extracted.get("funding_needed"),
            team_size=extracted.get("team_size"),
            tam=extracted.get("tam"),
        )
        
        print(f"[Parser] ✓ Extracted: revenue={project.annual_revenue}, "
              f"burn={project.monthly_burn_rate}, funding={project.funding_needed}")
        
        return project
    
    def _extract_with_llm(self, raw_text: str) -> dict:
        """Extract structured data with LLM."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Tu es un expert en analyse de projets startup.
Extrait les informations structurées du texte ci-dessous.

IMPORTANT: Retourne UNIQUEMENT du JSON valide, pas de markdown, pas de texte.

Format:
{{
    "business_model": "SaaS/Marketplace/Ecommerce/...",
    "industry": "fintech/edtech/artisanat/...",
    "annual_revenue": number or null,
    "growth_rate": number or null (1.5 = 150%),
    "monthly_burn_rate": number or null,
    "funding_needed": number or null,
    "team_size": number or null,
    "tam": number or null
}}

Utilise null pour les données manquantes."""),
            ("user", "{text}")
        ])
        
        chain = prompt | self.llm
        response = chain.invoke({"text": raw_text})
        content = response.content.strip()
        
        # Clean markdown
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"[Parser] ✗ JSON parse error: {e}")
            print(f"[Parser] Raw: {content[:200]}")
            return {}