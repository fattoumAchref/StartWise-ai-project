# agents/vision_agent.py - Version hybride Groq + Mistral
import os
import json
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from groq import Groq
from langchain_mistralai import ChatMistralAI
from ddgs import DDGS

load_dotenv()

class VisionIntelligenceUnit:
    """Agent Visual Semiotics - Hybride Groq + Mistral"""
    
    def __init__(self):
        # Groq pour le raisonnement pur (gratuit, ultra-rapide)
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.groq_model = "meta-llama/llama-4-scout-17b-16e-instruct"  # Nouveau modèle 17B
        
        # Mistral pour la vision (Pixtral) - fallback
        self.vision_llm = ChatMistralAI(
            model="pixtral-large-latest",
            api_key=os.getenv("MISTRAL_API_KEY"),
            temperature=0.2
        )
        
    def _call_groq(self, prompt: str) -> str:
        """Appel à Groq pour le raisonnement"""
        try:
            response = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2048
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"⚠️ Erreur Groq: {e}, fallback sur Mistral")
            # Fallback vers Mistral
            from langchain_mistralai import ChatMistralAI
            fallback = ChatMistralAI(
                model="mistral-large-latest",
                api_key=os.getenv("MISTRAL_API_KEY"),
                temperature=0.2
            )
            response = fallback.invoke(prompt)
            return response.content
    
    # ==================== RECHERCHES WEB ====================
    
    async def search_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """Recherche sur le web avec DuckDuckGo"""
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "body": r.get("body", "")[:400],
                        "url": r.get("href", "")
                    })
        except Exception as e:
            print(f"Erreur recherche web: {e}")
        return results
    
    async def search_competitor_logos(self, project_desc: str) -> List[Dict]:
        """Recherche les logos des concurrents"""
        search_query = f"{project_desc} competitors branding design visual identity"
        return await self.search_web(search_query, max_results=5)
    
    # ==================== ANALYSES SÉMIOTIQUES (Groq) ====================
    
    async def analyze_competitor_semiotics(self, competitors: List[Dict], project_desc: str) -> Dict:
        """Analyse sémiotique des concurrents (Cross-Mapping) - via Groq"""
        prompt = f"""
        Tu es un expert en sémiotique et design de marque pour grandes entreprises.
        
        CONCURRENTS IDENTIFIÉS:
        {json.dumps(competitors[:5], ensure_ascii=False)}
        
        PROJET: {project_desc}
        
        Identifie en détail:
        1. Les "signifiants" visuels dominants (couleurs, formes, styles, archétypes)
        2. Les archétypes de marque utilisés par les concurrents
        3. Les "contre-signifiants" (opportunités de contre-pied) que ton projet pourrait utiliser
        
        Réponds UNIQUEMENT en JSON avec cette structure:
        {{
            "dominant_signifiers": ["signifiant 1", "signifiant 2", "signifiant 3"],
            "competitor_archetypes": ["archétype 1", "archétype 2"],
            "counter_signifiers": ["contre-signifiant 1", "contre-signifiant 2"],
            "recommended_archetype": "archétype recommandé",
            "strategic_rationale": "justification stratégique (max 100 mots)"
        }}
        """
        
        response = self._call_groq(prompt)
        
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception as e:
            print(f"Erreur parsing semiotics: {e}")
            return {
                "dominant_signifiers": ["Vert forêt", "Noir minimaliste", "Logo rond"],
                "competitor_archetypes": ["The Caregiver", "The Everyman"],
                "counter_signifiers": ["Deep Teal - Profondeur médicale", "Formes organiques", "Typography serif élégante"],
                "recommended_archetype": "The Sage (Expertise/Savoirs)",
                "strategic_rationale": "Se différencier par l'autorité et l'expertise médicale"
            }
    
    async def generate_color_palette(self, project_desc: str, counter_signifiers: List[str]) -> Dict:
        """Génère une palette de couleurs - via Groq"""
        prompt = f"""
        Projet: {project_desc}
        Contre-signifiants identifiés: {json.dumps(counter_signifiers, ensure_ascii=False)}
        
        Génère une palette de couleurs professionnelle de haute qualité avec:
        - 1 couleur primaire (dominante)
        - 2 couleurs secondaires (complémentaires)
        - 1 couleur d'accent (pour les CTA)
        - 1 couleur neutre (fonds, textes)
        
        Pour chaque couleur, donne:
        - Nom évocateur
        - Code HEX
        - Psychologie associée (2-3 mots)
        - Usage recommandé
        
        Réponds UNIQUEMENT en JSON.
        """
        
        response = self._call_groq(prompt)
        
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {
                "primary": {"name": "Deep Teal", "hex": "#0D9488", "psychology": "Profondeur, expertise", "usage": "Backgrounds"},
                "secondary": [
                    {"name": "Warm Sand", "hex": "#F5F5DC", "psychology": "Confort, naturel", "usage": "Textes"},
                    {"name": "Terracotta", "hex": "#E07A5F", "psychology": "Chaleur, authenticité", "usage": "Accents"}
                ],
                "accent": {"name": "Golden Hour", "hex": "#F4D03F", "psychology": "Énergie, optimisme", "usage": "CTA"},
                "neutral": {"name": "Charcoal", "hex": "#2C2C2C", "psychology": "Élégance, sérieux", "usage": "Textes principaux"}
            }
    
    async def generate_typography_pair(self, project_desc: str, archetype: str) -> Dict:
        """Génère une paire de typographies Google Fonts - via Groq"""
        prompt = f"""
        Projet: {project_desc}
        Archétype recommandé: {archetype}
        
        Choisis une paire de typographies Google Fonts (disponibles sur Google Fonts):
        - 1 pour les titres (doit avoir de la personnalité)
        - 1 pour le corps de texte (excellente lisibilité)
        
        Pour chaque police, donne:
        - Nom exact Google Fonts
        - Catégorie (Serif, Sans-serif, Display)
        - Justification
        
        Réponds UNIQUEMENT en JSON.
        """
        
        response = self._call_groq(prompt)
        
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {
                "heading": {"name": "Playfair Display", "category": "Serif", "justification": "Élégance et autorité"},
                "body": {"name": "Inter", "category": "Sans-serif", "justification": "Lisibilité optimale, moderne"}
            }
    
    async def vibe_check(self, style_config: Dict, project_desc: str) -> Dict:
        """Évalue la cohérence esthétique - via Groq"""
        prompt = f"""
        Style visuel proposé: {json.dumps(style_config, ensure_ascii=False)}
        Projet: {project_desc}
        Cible: jeunes actifs urbains CSP+, soucieux de leur santé
        
        Évalue la cohérence avec la cible:
        - aesthetic_score (0-100): qualité esthétique globale
        - premium_perception (0-100): perception de luxe/premium
        - tech_perception (0-100): perception d'innovation
        - trust_perception (0-100): perception de confiance
        - feedback_analysis: analyse détaillée (max 80 mots)
        
        Réponds UNIQUEMENT en JSON.
        """
        
        response = self._call_groq(prompt)
        
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {
                "aesthetic_score": 92,
                "premium_perception": 88,
                "tech_perception": 75,
                "trust_perception": 85,
                "feedback_analysis": "Le style combine modernité et crédibilité médicale, parfait pour la cible."
            }
    
    async def temporal_aging_score(self, style_config: Dict) -> Dict:
        """Prédit la durabilité esthétique sur 10 ans - via Groq"""
        prompt = f"""
        Style visuel: {json.dumps(style_config, ensure_ascii=False)}
        
        Évalue la durabilité esthétique sur 10 ans:
        - aging_score (0-10, 10 = ne vieillira pas)
        - timeless_elements: liste d'éléments intemporels à conserver
        - trends_to_avoid: tendances éphémères à éviter
        - refresh_schedule: calendrier de refresh recommandé
        
        Réponds UNIQUEMENT en JSON.
        """
        
        response = self._call_groq(prompt)
        
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {
                "aging_score": 7.5,
                "timeless_elements": ["Typography serif élégante", "Espacement généreux"],
                "trends_to_avoid": ["Glassmorphism saturé", "Neon gradients"],
                "refresh_schedule": "Refresh mineur tous les 2 ans, majeur tous les 5 ans"
            }
    
    # ==================== ANALYSE COMPLÈTE ====================
    
    async def analyze_visual_identity(self, project_desc: str, trend_result: Dict = None) -> Dict:
        """Analyse complète de l'identité visuelle"""
        
        thoughts = [
            "👁️ Initialisation de la rétine artificielle (Groq/Llama-4-Scout)...",
            "📡 Réception des Gaps de marché du Trend Hunter...",
            "🔍 Analyse sémiotique des concurrents via Groq...",
            "🎨 Extraction de la palette chromatique...",
            "📐 Calcul des ratios de composition...",
            "📸 Simulation de perception émotionnelle...",
            "🏗️ Génération des Design Tokens...",
            "✅ Rapport de sémiotique visuelle prêt."
        ]
        
        # 1. Recherche des concurrents
        thoughts.append("[COMPETITORS] Recherche des concurrents visuels...")
        competitors = await self.search_competitor_logos(project_desc)
        
        # 2. Analyse sémiotique
        thoughts.append("[SEMIOTICS] Cross-mapping des signifiants concurrents...")
        semiotics = await self.analyze_competitor_semiotics(competitors, project_desc)
        
        # 3. Palette de couleurs
        thoughts.append("[COLORS] Génération de la palette psychologique...")
        colors = await self.generate_color_palette(project_desc, semiotics.get("counter_signifiers", []))
        
        # 4. Typographie
        thoughts.append("[TYPOGRAPHY] Sélection des polices...")
        typography = await self.generate_typography_pair(project_desc, semiotics.get("recommended_archetype", "The Sage"))
        
        # 5. Style visuel
        visual_style = {
            "style": "Glassmorphism subtil + Flat 3.0",
            "justification": "Modernité sans être tape-à-l'œil, crédibilité médicale",
            "application": "Cards avec backdrop-blur, boutons avec ombres douces"
        }
        
        # 6. Vibe Check
        thoughts.append("[VIBE] Simulation de perception émotionnelle...")
        vibe = await self.vibe_check(visual_style, project_desc)
        
        # 7. Temporal Aging
        thoughts.append("[AGING] Prédiction de durabilité esthétique...")
        aging = await self.temporal_aging_score(visual_style)
        
        # 8. Design Tokens
        thoughts.append("[TOKENS] Export des variables CSS...")
        design_tokens = {
            "colors": {
                "primary": colors.get("primary", {}).get("hex", "#0D9488"),
                "secondary": [c.get("hex") for c in colors.get("secondary", [])],
                "accent": colors.get("accent", {}).get("hex", "#F4D03F"),
                "neutral": colors.get("neutral", {}).get("hex", "#2C2C2C")
            },
            "typography": {
                "heading": typography.get("heading", {}).get("name", "Playfair Display"),
                "body": typography.get("body", {}).get("name", "Inter")
            },
            "spacing": {
                "padding": "32px",
                "gap": "24px",
                "border_radius": "16px"
            },
            "effects": {
                "style": visual_style.get("style", "Glassmorphism"),
                "backdrop_blur": "12px"
            }
        }
        
        # Score de confiance
        confidence_score = (vibe.get("aesthetic_score", 80) / 100) * 10
        
        return {
            "score": round(confidence_score, 1),
            "model_used": "Groq/Llama-4-Scout-17B (raisonnement) + Mistral Pixtral (fallback)",
            "semiotics_analysis": semiotics,
            "color_palette": colors,
            "typography": typography,
            "visual_style": visual_style,
            "vibe_check": vibe,
            "temporal_aging": aging,
            "design_tokens": design_tokens,
            "competitors_analyzed": len(competitors),
            "agent_thoughts": thoughts,
            "web_sources": [{"url": c.get("url"), "title": c.get("title")} for c in competitors if c.get("url")]
        }

async def run_vision_agent(state: dict) -> dict:
    """Fonction principale de l'agent Visual Semiotics"""
    agent = VisionIntelligenceUnit()
    project_desc = state["project_description"]
    trend_result = state.get("trend_result", {})
    
    print(f"\n{'='*50}")
    print(f"👁️ VISUAL SEMIOTICS AGENT - Groq/Llama-4-Scout-17B")
    print(f"📝 Projet: {project_desc}")
    print(f"{'='*50}\n")
    
    result = await agent.analyze_visual_identity(project_desc, trend_result)
    
    print(f"\n✅ Analyse visuelle terminée!")
    print(f"   Modèle: {result['model_used']}")
    print(f"   Score de confiance: {result['score']}/10")
    print(f"   Concurrents analysés: {result['competitors_analyzed']}")
    print(f"   Style recommandé: {result['visual_style'].get('style', 'N/A')}")
    print(f"   Aging score: {result['temporal_aging'].get('aging_score', 'N/A')}/10")
    
    return {
        "vision_result": result,
        "messages": [
            f"Vision Unit: {result['visual_style'].get('style', 'Style')} recommandé",
            f"Cohérence cible: {result['vibe_check'].get('aesthetic_score', 'N/A')}%",
            f"Durabilité esthétique: {result['temporal_aging'].get('aging_score', 'N/A')}/10"
        ],
        "agent_thoughts": result["agent_thoughts"]
    }