import os
import json
import asyncio
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

class EmotionalIntelligenceUnit:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"

    # On retire le 'async' ici car le client Groq standard ne l'est pas
    def generate_full_emotional_intelligence(self, project_desc, market_trends):
        prompt = f"""
        Tu es l'Expert Senior en Psychologie du Luxe et Intelligence Concurrentielle pour StartWise.
        PROJET : {project_desc}
        CONTEXTE : {market_trends}

        MISSION : Analyse le marché de manière impitoyable et stratégique. Ne sois pas générique. Cite de vrais acteurs (ex: Vestiaire Collective, The RealReal, Rebag, Vinted Luxury).

        TU DOIS GÉNÉRER 6 MODULES DANS TON JSON :
        1. SENTIMENT VELOCITY
        2. SOCIAL SENTIMENT MINING
        3. HALL OF SHAME (HTML)
        4. VOICE-MATCHING
        5. LOYALTY AUDIT
        6. CUSTOMER JOURNEY MAP

        RÉPONDS UNIQUEMENT EN JSON :
        {{
          "sentiment_velocity": [],
          "sentiment_mining": [],
          "hall_of_shame_html": "",
          "voice_matching": {{}},
          "loyalty_audit": {{}},
          "customer_journey": []
        }}
        """
        
        # L'appel à l'API se fait ici
        response = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

async def run_emotion_agent(state: dict):
    # AJOUT DE LOGS POUR DEBUG VISUEL
    print("\n" + "="*50)
    print("🧠 EMOTIONAL INTELLIGENCE AGENT - DÉMARRAGE")
    print("="*50)

    unit = EmotionalIntelligenceUnit()
    project_desc = state["project_description"]
    trend_data = state.get("trend_result", {})
    
    thoughts = [
        "Analyse de la 'Sentiment Velocity'...",
        "Extraction des frustrations VIP...",
        "Génération de la 'Customer Journey Map'...",
        "Codage du 'Hall of Shame' en format HTML..."
    ]

    try:
        # Lancement de l'appel API
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            None, 
            unit.generate_full_emotional_intelligence, 
            project_desc, 
            str(trend_data.get("weak_signals", ""))
        )
        
        # --- PETIT BLOC D'AFFICHAGE (NEW) ---
        print("✅ EQ Agent : Analyse réussie.")
        
        # On affiche le nombre de leaders analysés
        leaders = len(analysis.get('sentiment_velocity', []))
        print(f"   Leaders analysés: {leaders}")
        
        # On affiche le titre des frustrations pour voir si c'est pertinent
        frustrations = [f.get('topic', 'N/A') for f in analysis.get('sentiment_mining', [])]
        if frustrations:
            print(f"   Focus Frustrations: {', '.join(frustrations[:3])}")
            
        # On affiche le parcours client en une ligne d'emojis
        journey = analysis.get('customer_journey', [])
        if journey:
            steps = " -> ".join([f"{s.get('icon', '📍')} {s.get('step', '')}" for s in journey])
            print(f"   Parcours: {steps}")
        print("="*50 + "\n")
        # ------------------------------------

    except Exception as e:
        print(f"❌ Erreur critique dans Emotion Agent : {e}")
        analysis = {
            "sentiment_velocity": [], "sentiment_mining": [],
            "hall_of_shame_html": f"<p>Erreur: {str(e)}</p>",
            "voice_matching": {}, "loyalty_audit": {}, "customer_journey": []
        }

    return {
        "emotion_result": {
            **analysis,
            "agent_thoughts": thoughts
        },
        "messages": ["EQ Agent : Intelligence stratégique et parcours client finalisés."]
    }
