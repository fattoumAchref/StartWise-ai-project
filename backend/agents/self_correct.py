# agents/self_correct.py - Version améliorée
import json
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatMistralAI(model="mistral-large-latest", temperature=0)

class SelfCorrectionUnit:
    def __init__(self):
        self.threshold = 8.0

    async def audit_internal_logic(self, state: dict):
        trend = state.get("trend_result", {})
        
        # Vérifie si l'agent a utilisé des sources web
        sources = trend.get("sources", [])
        web_sources = trend.get("web_sources", [])
        
        prompt = ChatPromptTemplate.from_template("""
        Tu es l'AUDITEUR CRITIQUE de StartWise.
        
        ANALYSE DU TREND HUNTER:
        - Score de confiance: {confidence_score}
        - Sources utilisées: {sources}
        - Cas similaires trouvés: {similar_cases}
        - Web sources: {web_sources}
        
        Critères d'évaluation:
        1. Qualité des sources (0-5): A-t-il utilisé des sources récentes et pertinentes?
        2. Profondeur d'analyse (0-5): L'analyse est-elle suffisamment détaillée?
        3. Pertinence (0-5): Les cas trouvés sont-ils réellement similaires au projet?
        
        Réponds en JSON avec: score_global, critique_majeure, corrections_requises, approved
        """)
        
        chain = prompt | llm
        response = await chain.ainvoke({
            "confidence_score": trend.get("score", 0),
            "sources": ", ".join(sources),
            "similar_cases": json.dumps(trend.get("similar_cases", [])[:3]),
            "web_sources": json.dumps(web_sources[:3])
        })
        
        try:
            return json.loads(response.content.replace("```json", "").replace("```", "").strip())
        except:
            return {"score_global": 5.0, "approved": False, "critique_majeure": "Erreur de formatage"}

async def run_self_correction(state: dict):
    auditor = SelfCorrectionUnit()
    thoughts = ["⚖️ Lancement de l'Audit Qualité..."]
    
    audit_report = await auditor.audit_internal_logic(state)
    score = audit_report.get("score_global", 0)
    
    thoughts.append(f"Score de qualité: {score}/10")
    
    if score < auditor.threshold:
        thoughts.append(f"❌ Critique: {audit_report.get('critique_majeure')}")
    else:
        thoughts.append("✅ Validation finale approuvée")
    
    return {
        "self_correction_score": score,
        "self_correction_feedback": audit_report,
        "agent_thoughts": thoughts,
        "messages": [f"Audit: {score}/10 - {'Approuvé' if score >= 8 else 'Nécessite corrections'}"]
    }