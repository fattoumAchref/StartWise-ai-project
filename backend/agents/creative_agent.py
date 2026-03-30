import os
import json
import asyncio
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

# 1. Activation du .env
load_dotenv()

class CreativeDirectorUnit:
    def __init__(self):
        # 2. On place le LLM ICI avec la clé API pour plus de sécurité
        self.llm = ChatMistralAI(
            model="mistral-large-latest", 
            temperature=0.8,
            api_key=os.getenv("MISTRAL_API_KEY")
        )
        self.api_url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

    async def craft_expert_prompt(self, state: dict, variant: str):
        # Sécurité sur l'extraction des données
        emotion = state.get("emotion_result", {}).get("recommendation", {"primary_trigger": "Innovation"})
        vision = state.get("vision_result", {}).get("strategy", {"recommended_archetype": "Minimalist"})
        trends = state.get("trend_result", {"key_risks": "Market saturation"})

        prompt_genius = ChatPromptTemplate.from_template("""
        Tu es un Directeur Artistique de classe mondiale. 
        PROJET : {project}
        EMOTION CIBLE : {emotion}
        ARCHETYPE VISUEL : {archetype}
        RISQUES À ÉVITER : {risks}
        VARIANT : {variant}

        Rédige un PROMPT de 100 mots pour Stable Diffusion XL. 
        Inclus des détails sur : la lumière, la texture, la composition et l'ambiance.
        Réponds UNIQUEMENT avec le prompt en anglais.
        """)
        
        chain = prompt_genius | self.llm
        response = await chain.ainvoke({
            "project": state["project_description"],
            "emotion": emotion.get("primary_trigger", "Innovation"),
            "archetype": vision.get("recommended_archetype", "Minimalist"),
            "risks": trends.get("key_risks", "None"),
            "variant": variant
        })
        return response.content

async def run_creative_agent(state: dict):
    director = CreativeDirectorUnit()
    thoughts = [
        "Récupération des directives de la Matrice Émotionnelle...",
        "Calcul des contraintes de différenciation visuelle (Anti-Trend Logic)..."
    ]

    variants = ["Social Media Ad", "Futuristic Billboard", "Premium Print"]
    ads = []

    for variant in variants:
        thoughts.append(f"Scénarisation du concept pour le variant : {variant}...")
        
        # 1. Prompt artistique
        expert_prompt = await director.craft_expert_prompt(state, variant)
        
        # 2. Accroche courte
        copy_prompt = f"Génère une accroche de 5 mots max pour une pub {variant} sur {state['project_description']}. Réponds juste l'accroche."
        copy_res = await director.llm.ainvoke(copy_prompt)
        headline = copy_res.content.strip('"')

        thoughts.append(f"Génération du visuel conceptuel ({variant})...")
        
        ads.append({
            "type": variant,
            "headline": headline,
            "prompt": expert_prompt,
            "image_url": "https://picsum.photos/1024/1024", 
            "vibe_score": 9.8
        })

    thoughts.append("Campagne créative finalisée. Exportation des prototypes.")

    return {
        "creative_result": {
            "ads": ads,
            "agent_thoughts": thoughts
        },
        "messages": [f"Creative Unit : {len(ads)} concepts générés."]
    }
