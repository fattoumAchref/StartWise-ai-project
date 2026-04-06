import json
import asyncio
from dotenv import load_dotenv
from .inference import inference as smart_llm, state_llm_params

load_dotenv()


LANG_NAMES = {'fr': 'French', 'en': 'English', 'bm': 'Bambara', 'ar': 'Arabic'}


class EmotionalIntelligenceUnit:
    def __init__(self, lang='fr'):
        # LLM : SmartInferenceProvider (Groq 8B → ESPRIT fallback)
        self.lang = lang

    @property
    def _lang_instruction(self):
        lang_name = LANG_NAMES.get(self.lang, 'French')
        return f"\n\nCRITICAL: Generate ALL text values in {lang_name}. JSON keys must remain in English."

    def generate_full_emotional_intelligence(self, project_desc, context_json, llm_params=None):
        prompt = f"""Tu es un expert en psychologie comportementale et intelligence concurrentielle.

PROJET : {project_desc}

CONTEXTE (données des agents Trend + Vision) :
{context_json}

Analyse ce projet en profondeur. Identifie les vrais concurrents du secteur, leurs failles réelles observables, et construis une stratégie cognitive complète et originale adaptée à ce projet spécifique.
Chaque donnée doit être déduite du projet — aucune valeur générique, aucun copier-coller.

Réponds UNIQUEMENT en JSON valide avec cette structure exacte :
{{
  "sentiment_velocity": [
    {{"competitor": "...", "prev_score": 0.0, "current_score": 0.0, "trend": "up|down|stable", "key_issue": "...", "source_label": "...", "source_url": "..."}}
  ],
  "sentiment_mining": [
    {{"topic": "...", "competitor": "...", "source": "...", "source_url": "...", "verbatim": "...", "opportunity": "...", "severity": "critical|high|medium"}}
  ],
  "hall_of_shame_html": "<div style='font-family:system-ui,sans-serif'>...</div>",
  "voice_matching": {{
    "scenario": "...",
    "competitor_name": "...",
    "source_url": "...",
    "bad_reply": "...",
    "good_reply": "...",
    "personality_gap": "..."
  }},
  "loyalty_audit": {{
    "cold_system": {{"name": "...", "desc": "...", "visual": "..."}},
    "warm_system": {{"name": "...", "desc": "...", "visual": "..."}}
  }},
  "customer_journey": [
    {{"step": "...", "persona_action": "...", "desc": "...", "icon": "...", "type": "neutral|friction|delight", "emotion": "...", "emotion_score": 0, "color": "#...", "competitor_mistake": "...", "our_advantage": "...", "duration": "...", "kpi": "..."}}
  ],
  "cognitive_strategy": {{
    "insight_summary": "...",
    "target_persona": {{
      "name": "...",
      "archetype": "...",
      "pain_points": ["...", "...", "..."],
      "desires": ["...", "...", "..."],
      "trigger_words": ["...", "...", "...", "...", "...", "..."]
    }},
    "key_differentiators": ["...", "...", "..."]
  }},
  "ocean_profile": {{
    "openness": {{"score": 0, "rationale": "...", "ux_recommendation": "..."}},
    "conscientiousness": {{"score": 0, "rationale": "...", "ux_recommendation": "..."}},
    "extraversion": {{"score": 0, "rationale": "...", "ux_recommendation": "..."}},
    "agreeableness": {{"score": 0, "rationale": "...", "ux_recommendation": "..."}},
    "neuroticism": {{"score": 0, "rationale": "...", "ux_recommendation": "..."}}
  }},
  "ethical_hook": {{
    "trigger": "...",
    "action": "...",
    "variable_reward": "...",
    "investment": "..."
  }},
  "cognitive_load": {{
    "max_steps": 3,
    "recommendation": "...",
    "complexity_level": "minimal|moderate|complex",
    "ux_principles": ["...", "...", "...", "..."]
  }}
}}""" + self._lang_instruction

        params = llm_params or {}
        content = smart_llm.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=params.get("temperature", 0.4),
            max_tokens=2800,
            model_override=params.get("model_override"),
        ).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())


async def run_emotion_agent(state: dict):
    print("\n" + "="*50)
    print("🧠 EMOTIONAL INTELLIGENCE AGENT - DÉMARRAGE")
    print("="*50)

    lang = state.get("lang", "fr")
    unit = EmotionalIntelligenceUnit(lang=lang)
    project_desc = state["project_description"]
    llm_params = state_llm_params(state)
    print(f"[EMOTION] model={llm_params.get('model_override','défaut')} temp={llm_params.get('temperature')}")
    trend_data = state.get("trend_result", {})
    vision_data = state.get("vision_result", {})

    # Contexte enrichi depuis les agents précédents
    context = {
        "weak_signals": trend_data.get("weak_signals", []),
        "main_risks": trend_data.get("analysis", {}).get("main_risks", []),
        "recommendations": trend_data.get("analysis", {}).get("recommendations", []),
        "market_score": trend_data.get("score", "N/A"),
        "visual_style": vision_data.get("visual_style", {}),
        "recommended_archetype": vision_data.get("semiotics_analysis", {}).get("recommended_archetype", ""),
        "vibe_check": vision_data.get("vibe_check", {}),
        "temporal_aging": vision_data.get("temporal_aging", {})
    }

    thoughts = [
        "Croisement des signaux de marché avec la psychologie client...",
        "Analyse Sentiment Velocity sur Trustpilot, Reddit et Google Reviews...",
        "Extraction des frustrations VIP — construction du Mur des Lamentations...",
        "Génération du Customer Journey Map basé sur les erreurs concurrentes...",
        "Synthèse de la Cognitive Strategy depuis les données Trend + Vision...",
        "Calibration OCEAN Profile, Tone of Voice et Behavioral Nudges..."
    ]

    try:
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            None,
            unit.generate_full_emotional_intelligence,
            project_desc,
            json.dumps(context, ensure_ascii=False, indent=2),
            llm_params,
        )

        print("✅ EQ Agent : Analyse réussie.")
        print(f"   Concurrents analysés: {len(analysis.get('sentiment_velocity', []))}")
        print(f"   Frustrations identifiées: {len(analysis.get('sentiment_mining', []))}")
        print(f"   Étapes du parcours: {len(analysis.get('customer_journey', []))}")
        print(f"   A/B Tests générés: {len(analysis.get('cognitive_strategy', {}).get('ab_tests', []))}")
        print("="*50 + "\n")

    except Exception as e:
        print(f"❌ Erreur critique dans Emotion Agent : {e}")
        analysis = {
            "sentiment_velocity": [], "sentiment_mining": [],
            "hall_of_shame_html": f"<p>Erreur: {str(e)}</p>",
            "voice_matching": {}, "loyalty_audit": {}, "customer_journey": [],
            "cognitive_strategy": {}, "ocean_profile": {}, "tone_of_voice": {},
            "behavioral_nudges": [], "ethical_hook": {}, "cognitive_load": {}
        }

    return {
        "emotion_result": {
            **analysis,
            "agent_thoughts": thoughts
        },
        "messages": ["EQ Agent : Intelligence stratégique et parcours client finalisés."]
    }
