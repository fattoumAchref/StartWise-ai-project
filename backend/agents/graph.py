# graph.py - Version finale corrigée

from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List
import operator
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .trend_agent import run_trend_agent
from .vision_agent import run_vision_agent
from .emotion_agent import run_emotion_agent
from .creative_agent import run_creative_agent
from .self_correct import run_self_correction

def safe_convert_to_string(obj):
    """Convertit n'importe quel objet en string de manière sécurisée"""
    if obj is None:
        return "None"
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except:
        return str(obj)

def ensure_string_list(data):
    """Garantit que la donnée est une liste de strings"""
    if data is None:
        return []
    if not isinstance(data, list):
        logger.warning(f"Expected list, got {type(data)}")
        return [safe_convert_to_string(data)]
    
    result = []
    for item in data:
        try:
            result.append(safe_convert_to_string(item))
        except Exception as e:
            logger.error(f"Error converting item: {e}")
            result.append(f"[Error: {e}]")
    return result

class AgentState(TypedDict):
    project_description: str
    trend_result: dict
    vision_result: dict
    emotion_result: dict
    creative_result: dict
    self_correction_score: float
    correction_attempts: int
    messages: Annotated[list, operator.add]
    current_thoughts: Annotated[list, operator.add]

async def supervisor_node(state: AgentState) -> AgentState:
    return {
        "messages": ["Supervisor: Protocole StartWise activé."],
        "current_thoughts": ["Initialisation du système..."]
    }

async def trend_node(state: AgentState) -> AgentState:
    try:
        res = await run_trend_agent(state)
        
        trend_result = res.get("trend_result", {})
        messages = ensure_string_list(res.get("messages", []))
        agent_thoughts = ensure_string_list(trend_result.get("agent_thoughts", []))
        
        return {
            "trend_result": trend_result,
            "messages": messages,
            "current_thoughts": agent_thoughts
        }
    except Exception as e:
        logger.error(f"Trend node error: {e}")
        return {
            "trend_result": {"error": str(e)},
            "messages": [f"Erreur dans trend_agent: {str(e)}"],
            "current_thoughts": [f"Erreur: {str(e)}"]
        }

async def vision_node(state: AgentState) -> AgentState:
    try:
        res = await run_vision_agent(state)
        
        vision_result = res.get("vision_result", {})
        messages = ensure_string_list(res.get("messages", []))
        agent_thoughts = ensure_string_list(vision_result.get("agent_thoughts", []))
        
        return {
            "vision_result": vision_result,
            "messages": messages,
            "current_thoughts": agent_thoughts
        }
    except Exception as e:
        logger.error(f"Vision node error: {e}")
        return {
            "vision_result": {"error": str(e)},
            "messages": [f"Erreur dans vision_agent: {str(e)}"],
            "current_thoughts": [f"Erreur: {str(e)}"]
        }

async def emotion_node(state: AgentState) -> AgentState:
    try:
        res = await run_emotion_agent(state)
        
        emotion_result = res.get("emotion_result", {})
        messages = ensure_string_list(res.get("messages", []))
        agent_thoughts = ensure_string_list(emotion_result.get("agent_thoughts", []))
        
        return {
            "emotion_result": emotion_result,
            "messages": messages,
            "current_thoughts": agent_thoughts
        }
    except Exception as e:
        logger.error(f"Emotion node error: {e}")
        return {
            "emotion_result": {"error": str(e)},
            "messages": [f"Erreur dans emotion_agent: {str(e)}"],
            "current_thoughts": [f"Erreur: {str(e)}"]
        }

async def self_correct_node(state: AgentState) -> AgentState:
    try:
        res = await run_self_correction(state)
        
        # Récupération sécurisée des données
        score = res.get("self_correction_score", 0)
        attempts = state.get("correction_attempts", 0) + 1
        
        # Gestion des messages et thoughts
        messages = ensure_string_list(res.get("messages", []))
        
        # Ici, les agent_thoughts peuvent être dans res directement
        agent_thoughts = ensure_string_list(res.get("agent_thoughts", []))
        
        return {
            "self_correction_score": score,
            "correction_attempts": attempts,
            "messages": messages,
            "current_thoughts": agent_thoughts
        }
    except Exception as e:
        logger.error(f"Self-correct node error: {e}")
        return {
            "self_correction_score": 0,
            "correction_attempts": state.get("correction_attempts", 0) + 1,
            "messages": [f"Erreur dans self_correct: {str(e)}"],
            "current_thoughts": [f"Erreur: {str(e)}"]
        }

async def creative_node(state: AgentState) -> AgentState:
    try:
        res = await run_creative_agent(state)
        
        creative_result = res.get("creative_result", {})
        messages = ensure_string_list(res.get("messages", []))
        agent_thoughts = ensure_string_list(creative_result.get("agent_thoughts", []))
        
        return {
            "creative_result": creative_result,
            "messages": messages,
            "current_thoughts": agent_thoughts
        }
    except Exception as e:
        logger.error(f"Creative node error: {e}")
        return {
            "creative_result": {"error": str(e)},
            "messages": [f"Erreur dans creative_agent: {str(e)}"],
            "current_thoughts": [f"Erreur: {str(e)}"]
        }

# Modifie ta fonction dans graph.py ainsi :
def should_continue(state: AgentState):
    # On force le retour vers 'creative' directement
    # Cela évite de reboucler et de surcharger ta connexion
    logger.info("Passage direct à l'unité créative (Mode Stabilité)")
    return "creative"


# qui oblige chaque agent à s'afficher l'un après l'autre.

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("trend_hunter", trend_node)
    workflow.add_node("visual_semiotics", vision_node)
    workflow.add_node("emotional_intelligence", emotion_node)
    workflow.add_node("creative_director", creative_node)

    workflow.set_entry_point("supervisor")

    # CHAINE STRICTE : 1 -> 2 -> 3 -> 4 -> FIN
    workflow.add_edge("supervisor", "trend_hunter")
    workflow.add_edge("trend_hunter", "visual_semiotics")
    workflow.add_edge("visual_semiotics", "emotional_intelligence")
    workflow.add_edge("emotional_intelligence", "creative_director")
    workflow.add_edge("creative_director", END)

    return workflow.compile()

compiled_graph = build_graph()