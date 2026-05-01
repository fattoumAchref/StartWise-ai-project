import json
import asyncio
from dotenv import load_dotenv
from .inference import inference_pro as smart_llm_pro, image_client as unified_image, state_llm_params

load_dotenv()


LANG_NAMES_CREATIVE = {'fr': 'French', 'en': 'English', 'bm': 'Bambara', 'ar': 'Arabic'}


class CreativeDirectorUnit:
    def __init__(self, lang='fr'):
        # LLM : SmartInferenceProvider qualité (Groq 70B → ESPRIT fallback)
        # Images : UnifiedImageClient (HF FLUX.1 → Pollinations fallback)
        # Les deux sont des singletons importés depuis inference.py
        self.lang = lang

    @property
    def _lang_instruction(self):
        lang_name = LANG_NAMES_CREATIVE.get(self.lang, 'French')
        return f"\n\nCRITICAL: Generate ALL text values in {lang_name}. JSON keys must remain in English. image_prompt fields must always be in English (for FLUX.1)."

    def generate_strategy_sync(self, state: dict):
        trend = state.get("trend_result", {})
        vision = state.get("vision_result", {})
        emotion = state.get("emotion_result", {})

        visual_style = vision.get("visual_style", {})
        visual_archetype = vision.get("semiotics_analysis", {}).get("recommended_archetype", "")
        weak_signals = trend.get("weak_signals", [])
        cognitive_strategy = emotion.get("cognitive_strategy", {})

        context = {
            "visual_style": visual_style,
            "visual_archetype": visual_archetype,
            "weak_signals": weak_signals[:5] if weak_signals else [],
            "target_persona": cognitive_strategy.get("target_persona", {}),
            "key_differentiators": cognitive_strategy.get("key_differentiators", []),
            "sentiment_failles": [m.get("topic") for m in emotion.get("sentiment_mining", [])[:3]],
            "market_score": trend.get("score", "N/A")
        }

        prompt = f"""Tu es le Creative Director de StartWise. Synthétise les analyses des agents Trend, Visual et Emotion en un plan stratégique d'exécution monumental.

PROJET : {state["project_description"]}

CONTEXTE DES AGENTS PRÉCÉDENTS :
{json.dumps(context, ensure_ascii=False, indent=2)}

RÈGLES :
- Si l'archétype visuel détecté est identifiable (ex: Glassmorphism, Brutalism, Neumorphism), mentionne-le explicitement dans visual_style_integration de chaque phase.
- Identifie les vrais concurrents du secteur de ce projet.
- Les 4 phases doivent être logiquement ordonnées et spécifiques au projet.
- disruption_scores : scores de 0 à 100. "risque" = score de risque élevé = mauvais, donc si le projet est risqué, mets 70+.
- image_prompt : prompt anglais cinématique et descriptif pour FLUX.1 (pas de texte dans l'image, style photorealistic ou 3D render).

Réponds UNIQUEMENT en JSON valide :
{{
    "disruption_scores": {{
        "innovation": 0,
        "scalabilite": 0,
        "risque": 0,
        "cout": 0,
        "ux": 0
    }},
    "radical_pivot": {{
        "concept": "...",
        "why": "...",
        "market_signal": "..."
    }},
    "stress_test": [
        {{"scenario": "...", "impact": "...", "resilience": 0, "survival_tip": "..."}},
        {{"scenario": "...", "impact": "...", "resilience": 0, "survival_tip": "..."}},
        {{"scenario": "...", "impact": "...", "resilience": 0, "survival_tip": "..."}}
    ],
    "roadmap_phases": [
        {{
            "phase": "Phase 1",
            "title": "...",
            "duration": "...",
            "objective": "...",
            "milestones": ["...", "...", "..."],
            "visual_style_integration": "...",
            "image_prompt": "hyper-realistic 3D render, cinematic lighting, dramatic shadows, photorealistic materials, 8K ultra-sharp, unreal engine quality, [describe the specific product/service/concept of this phase in 3D], dark studio background, volumetric fog, neon accents, no text, no letters, no UI"
        }},
        {{
            "phase": "Phase 2",
            "title": "...",
            "duration": "...",
            "objective": "...",
            "milestones": ["...", "...", "..."],
            "visual_style_integration": "...",
            "image_prompt": "hyper-realistic 3D render, photorealistic, cinematic depth of field, dramatic rim lighting, 8K resolution, unreal engine render, [describe concept of this phase], dark gradient background, glowing edges, no text, no letters"
        }},
        {{
            "phase": "Phase 3",
            "title": "...",
            "duration": "...",
            "objective": "...",
            "milestones": ["...", "...", "..."],
            "visual_style_integration": "...",
            "image_prompt": "cinematic product shot, hyper-realistic 3D, studio lighting, dark moody background, photorealistic materials, sharp focus, 8K, [describe concept of this phase], volumetric light rays, premium aesthetic, no text, no letters"
        }},
        {{
            "phase": "Phase 4",
            "title": "...",
            "duration": "...",
            "objective": "...",
            "milestones": ["...", "...", "..."],
            "visual_style_integration": "...",
            "image_prompt": "epic wide shot, hyper-realistic 3D render, cinematic composition, dramatic lighting, photorealistic, 8K ultra quality, [describe the final vision/goal of this phase], futuristic atmosphere, deep shadows, glowing highlights, no text, no letters"
        }}
    ],
    "killer_features": [
        {{"name": "...", "description": "...", "competitor_gap": "...", "icon_type": "shield|rocket|zap|star|target|brain|eye|lock"}},
        {{"name": "...", "description": "...", "competitor_gap": "...", "icon_type": "..."}},
        {{"name": "...", "description": "...", "competitor_gap": "...", "icon_type": "..."}},
        {{"name": "...", "description": "...", "competitor_gap": "...", "icon_type": "..."}}
    ],
    "mvp_blueprint": [
        {{"feature": "...", "counter_attack": "...", "priority": "CRITICAL|HIGH|MEDIUM"}}
    ],
    "sources": ["Trend Hunter", "Visual Semiotics", "Emotional Unit"]
}}""" + self._lang_instruction

        llm_params = state_llm_params(state)
        content = smart_llm_pro.complete(
            messages=[{"role": "user", "content": prompt}],
            temperature=llm_params.get("temperature", 0.4),
            max_tokens=4096,
            model_override=llm_params.get("model_override"),
        ).strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        return json.loads(content.strip())


async def run_creative_agent(state: dict):
    llm_params = state_llm_params(state)
    print("\n" + "⚡" * 5 + f" CREATIVE DIRECTOR — model={llm_params.get('model_override','défaut')} temp={llm_params.get('temperature')} " + "⚡" * 5)
    lang = state.get("lang", "fr")
    unit = CreativeDirectorUnit(lang=lang)

    thoughts = [
        "Extraction des insights critiques des 3 unités...",
        "Calcul des scores de disruption sur 5 axes...",
        "Construction de la Roadmap dynamique en 4 phases...",
        "Génération des visuels FLUX pour chaque phase...",
        "Identification des Killer Features anti-concurrentielles...",
        "Génération du Radical Pivot stratégique..."
    ]

    try:
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(None, unit.generate_strategy_sync, state)

        print(f"✅ Stratégie Creative générée via SmartInferenceProvider ({smart_llm_pro.active_provider})")

        # Génération images en parallèle via UnifiedImageClient (HF → Pollinations)
        roadmap_phases = analysis.get("roadmap_phases", [])
        if roadmap_phases:
            print(f"🎨 Génération de {len(roadmap_phases)} images en parallèle (HF FLUX.1 → Pollinations)...")
            batch = {
                f"phase_{idx}": phase.get("image_prompt", "")
                for idx, phase in enumerate(roadmap_phases)
                if phase.get("image_prompt")
            }
            seeds = {f"phase_{idx}": idx * 100 for idx in range(len(roadmap_phases))}
            images = await unified_image.generate_batch(batch, seeds=seeds)

            for idx, phase in enumerate(roadmap_phases):
                phase["image"] = images.get(f"phase_{idx}", "")

            n_ok = sum(1 for p in roadmap_phases if p.get("image"))
            print(f"   ✅ {n_ok}/{len(roadmap_phases)} images roadmap générées")
            analysis["roadmap_phases"] = roadmap_phases
        return {
            "creative_result": {
                **analysis,
                "agent_thoughts": thoughts
            },
            "messages": ["Creative Director : Plan de bataille prêt."]
        }
    except Exception as e:
        print(f"❌ Erreur critique Creative Agent : {e}")
        return {
            "creative_result": {
                "error": str(e),
                "agent_thoughts": ["Échec de la synthèse stratégique."]
            }
        }
