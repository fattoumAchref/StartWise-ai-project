# backend/agents/notion_service.py
# ============================================================
#  Service Notion — StartWise Roadmap Export
# ============================================================
#  Prend les résultats de tous les agents, génère ~15 tâches
#  marketing actionnables via LLM, puis les crée dans la base
#  Notion "Roadmap StartWise" via l'API Notion REST.
# ============================================================

import json
import re
import os
import httpx
from dotenv import load_dotenv
from .inference import inference_pro as smart_llm_pro, state_llm_params

load_dotenv()

NOTION_API_VERSION = "2022-06-28"
NOTION_PAGES_URL   = "https://api.notion.com/v1/pages"


# ─────────────────────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────────────────────

def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    m = re.search(r'```\s*([\s\S]+?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return None


def _notion_headers() -> dict:
    api_key = os.getenv("api_notion", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def _notion_db_url(database_id: str) -> str:
    """Retourne l'URL directe de la base Notion."""
    clean_id = database_id.replace("-", "")
    return f"https://www.notion.so/{clean_id}"


# ─────────────────────────────────────────────────────────────
#  Génération des tâches par LLM
# ─────────────────────────────────────────────────────────────

def _generate_tasks(project_desc: str, all_results: dict, lang: str = "fr") -> list[dict]:
    """
    Utilise le LLM pour générer ~15 tâches marketing actionnables
    à partir des résultats de tous les agents.
    Retourne une liste de dicts avec : title, priority, agent_source.
    """
    trend    = all_results.get("trend_hunter", {})
    vision   = all_results.get("visual_semiotics", {})
    emotion  = all_results.get("emotional_intelligence", {})
    creative = all_results.get("creative_director", {})
    commercial = all_results.get("commercial_agent", {})

    # Résumé compact des insights clés
    trends_summary = [t.get("trend", "") for t in trend.get("market_trends", [])[:4]]
    opportunities  = [o.get("opportunity", o) if isinstance(o, dict) else str(o)
                      for o in trend.get("analysis", {}).get("recommendations", [])[:3]]
    brand_archetype = vision.get("semiotics_analysis", {}).get("recommended_archetype", "")
    tone_of_voice   = emotion.get("tone_of_voice", {}).get("primary_tone", "")
    killer_features = creative.get("killer_features", [])[:3]
    phases          = creative.get("execution_phases", [{}])
    phase1_tasks    = phases[0].get("killer_features", [])[:3] if phases else []
    prospects_count = len(commercial.get("prospects", []))

    prompt = f"""You are a startup marketing strategist. Based on the following AI-generated analysis of a startup project, create exactly 15 actionable marketing tasks for a Notion roadmap.

PROJECT: {project_desc[:500]}

KEY INSIGHTS:
- Market trends: {json.dumps(trends_summary, ensure_ascii=False)}
- Opportunities: {json.dumps(opportunities, ensure_ascii=False)}
- Brand archetype: {brand_archetype}
- Tone of voice: {tone_of_voice}
- Killer features: {json.dumps(killer_features, ensure_ascii=False)}
- Phase 1 tasks: {json.dumps(phase1_tasks, ensure_ascii=False)}
- Prospects identified: {prospects_count}

Create 15 tasks distributed across these 5 agents:
- "Trend Hunter" (3 tasks): competitor research, market trend monitoring, positioning
- "Visual Semiotics" (3 tasks): brand identity, logo, color palette, visual content
- "Emotional AI" (3 tasks): tone of voice, messaging, customer journey touchpoints
- "Creative Director" (3 tasks): campaign execution, content calendar, launch plan
- "The Dealmaker" (3 tasks): outreach, email sequences, social media publishing

Each task must be concrete and actionable (e.g. "Create 3 Instagram posts for launch week").
Vary priorities: assign High to 5 tasks, Medium to 6 tasks, Low to 4 tasks.

Return ONLY valid JSON array (no extra text):
[
  {{
    "title": "Actionable task title",
    "priority": "High" | "Medium" | "Low",
    "agent_source": "Trend Hunter" | "Visual Semiotics" | "Emotional AI" | "Creative Director" | "The Dealmaker"
  }}
]

Write all task titles in {"French" if lang == "fr" else "English"}."""

    try:
        raw = smart_llm_pro.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
            temperature=0.5,
        )
        data = _extract_json(raw)
        if isinstance(data, list):
            return data[:15]
        if isinstance(data, dict) and "tasks" in data:
            return data["tasks"][:15]
    except Exception as e:
        print(f"[NOTION] LLM task generation error: {e}")

    # Fallback minimal si LLM échoue
    return [
        {"title": "Définir le positionnement de marque",       "priority": "High",   "agent_source": "Trend Hunter"},
        {"title": "Créer la palette de couleurs officielle",    "priority": "High",   "agent_source": "Visual Semiotics"},
        {"title": "Rédiger le tone of voice de la marque",     "priority": "High",   "agent_source": "Emotional AI"},
        {"title": "Planifier le calendrier de contenu S1",     "priority": "High",   "agent_source": "Creative Director"},
        {"title": "Lancer la campagne de prospection B2B",     "priority": "High",   "agent_source": "The Dealmaker"},
        {"title": "Analyser les tendances concurrentes",        "priority": "Medium", "agent_source": "Trend Hunter"},
        {"title": "Créer 3 logos alternatifs",                  "priority": "Medium", "agent_source": "Visual Semiotics"},
        {"title": "Optimiser le parcours client digital",       "priority": "Medium", "agent_source": "Emotional AI"},
        {"title": "Produire 10 posts Instagram pour le lancement", "priority": "Medium", "agent_source": "Creative Director"},
        {"title": "Envoyer les emails de prospection (lot 1)", "priority": "Medium", "agent_source": "The Dealmaker"},
        {"title": "Surveiller les signaux faibles du marché",   "priority": "Medium", "agent_source": "Trend Hunter"},
        {"title": "Concevoir le kit de marque complet",        "priority": "Low",    "agent_source": "Visual Semiotics"},
        {"title": "A/B tester les accroches émotionnelles",    "priority": "Low",    "agent_source": "Emotional AI"},
        {"title": "Créer le plan de lancement produit V2",     "priority": "Low",    "agent_source": "Creative Director"},
        {"title": "Publier les posts Facebook hebdomadaires",  "priority": "Low",    "agent_source": "The Dealmaker"},
    ]


# ─────────────────────────────────────────────────────────────
#  Création des pages Notion
# ─────────────────────────────────────────────────────────────

def _create_notion_page(database_id: str, task: dict) -> dict:
    """
    Crée une page dans la base Notion avec les propriétés :
    Name (Title), Status (Select), Priority (Select), Agent (Select).
    Retourne le résultat de l'API Notion.
    """
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {
                "title": [{"text": {"content": task.get("title", "Tâche sans titre")}}]
            },
            "Status": {
                "select": {"name": "To Do"}
            },
            "Priority": {
                "select": {"name": task.get("priority", "Medium")}
            },
            "Agent": {
                "select": {"name": task.get("agent_source", "Creative Director")}
            },
        }
    }

    resp = httpx.post(
        NOTION_PAGES_URL,
        headers=_notion_headers(),
        json=payload,
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


# ─────────────────────────────────────────────────────────────
#  Point d'entrée principal
# ─────────────────────────────────────────────────────────────

def export_to_notion(project_desc: str, all_results: dict, lang: str = "fr") -> dict:
    """
    1. Génère ~15 tâches marketing via LLM
    2. Crée chaque tâche dans la base Notion
    3. Retourne { success, tasks_created, notion_url, tasks, errors }
    """
    api_key     = os.getenv("api_notion", "")
    database_id = os.getenv("database_id_notion", "")

    if not api_key or not database_id:
        return {
            "success": False,
            "error": "Notion credentials manquantes. Vérifiez api_notion et database_id_notion dans votre .env",
        }

    # Étape 1 : générer les tâches
    tasks = _generate_tasks(project_desc, all_results, lang)
    print(f"[NOTION] {len(tasks)} tâches générées via LLM")

    # Étape 2 : créer les pages Notion
    created = []
    errors  = []

    for task in tasks:
        try:
            page = _create_notion_page(database_id, task)
            created.append({
                "title":       task.get("title"),
                "priority":    task.get("priority"),
                "agent_source": task.get("agent_source"),
                "notion_page_id": page.get("id"),
            })
            print(f"[NOTION] ✓ Créé : {task.get('title')}")
        except httpx.HTTPStatusError as e:
            err_msg = f"{task.get('title')} — HTTP {e.response.status_code}: {e.response.text[:200]}"
            errors.append(err_msg)
            print(f"[NOTION] ✗ Erreur HTTP : {err_msg}")
        except Exception as e:
            err_msg = f"{task.get('title')} — {str(e)}"
            errors.append(err_msg)
            print(f"[NOTION] ✗ Erreur : {err_msg}")

    notion_url = _notion_db_url(database_id)

    return {
        "success":       len(created) > 0,
        "tasks_created": len(created),
        "tasks_total":   len(tasks),
        "notion_url":    notion_url,
        "tasks":         created,
        "errors":        errors,
    }
