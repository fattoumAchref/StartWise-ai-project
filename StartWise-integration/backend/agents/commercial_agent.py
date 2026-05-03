# backend/agents/commercial_agent.py
# ============================================================
#  AGENT COMMERCIAL — StartWise 5ème agent
# ============================================================
#  Pipeline :
#    1. Identifier 3 prospects cibles (LLM + Hunter.io si dispo)
#    2. Rédiger 1 mail personnalisé par prospect
#    3. Rédiger 1 post Facebook
#    4. Rédiger 1 post Instagram
#  Tout reste en statut "pending" → validation fondateur obligatoire
#  avant exécution (send_email / schedule_post).
# ============================================================

import json
import re
import asyncio
import os
import httpx
from dotenv import load_dotenv
from .inference import inference_pro as smart_llm_pro, state_llm_params

load_dotenv()

LANG_NAMES = {'fr': 'French', 'en': 'English', 'bm': 'Bambara', 'ar': 'Arabic'}


# ─────────────────────────────────────────────────────────────
#  Hunter.io — recherche de contacts réels sur un domaine
# ─────────────────────────────────────────────────────────────

def _hunter_find_email(domain: str) -> str | None:
    """Retourne le premier email trouvé sur le domaine via Hunter.io (gratuit 25/mois)."""
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key or not domain:
        return None
    try:
        resp = httpx.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 1},
            timeout=8.0,
        )
        data = resp.json()
        emails = data.get("data", {}).get("emails", [])
        if emails:
            e = emails[0]
            return e.get("value")
    except Exception:
        pass
    return None


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
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────
#  CommercialAgent
# ─────────────────────────────────────────────────────────────

class CommercialAgent:

    def generate_sync(self, state: dict) -> dict:
        project      = state.get("project_description", "")
        lang         = state.get("lang", "fr")
        lang_name    = LANG_NAMES.get(lang, "French")
        trend        = state.get("trend_result", {})
        creative     = state.get("creative_result", {})
        llm_params   = state_llm_params(state)

        thoughts = []

        # ── ÉTAPE 1 : Identifier 3 prospects ─────────────────────────────
        prospect_prompt = f"""You are a B2B sales expert. Analyze this startup and identify exactly 3 ideal prospect profiles.

PROJECT: {project}

MARKET TRENDS: {json.dumps([t.get('trend', '') for t in trend.get('market_trends', [])[:4]], ensure_ascii=False)}

Return ONLY valid JSON (no extra text):
{{
  "prospects": [
    {{
      "name": "Realistic full name",
      "role": "Specific job title",
      "company": "Real-sounding company name",
      "company_domain": "domain.com",
      "sector": "Industry sector",
      "why_fit": "One sentence explaining why they are a perfect lead"
    }}
  ]
}}

IMPORTANT: Generate ALL text values in {lang_name}. Keep JSON keys in English."""

        prospects = []
        try:
            raw = smart_llm_pro.complete(
                messages=[{"role": "user", "content": prospect_prompt}],
                max_tokens=700,
                **llm_params,
            )
            data = _extract_json(raw) or {}
            prospects = data.get("prospects", [])[:3]
        except Exception as e:
            thoughts.append(f"Prospect identification error: {e}")

        # Enrichir avec Hunter.io si disponible
        for p in prospects:
            domain = p.get("company_domain", "")
            real_email = _hunter_find_email(domain)
            if real_email:
                p["email"] = real_email
                p["email_source"] = "hunter.io"
            else:
                # Email généré de façon réaliste
                first = (p.get("name", "contact").split()[0]).lower()
                p["email"] = f"{first}@{domain}" if domain else "contact@example.com"
                p["email_source"] = "generated"

        thoughts.append(f"{len(prospects)} prospect(s) identified")

        # ── ÉTAPE 2 : Rédiger un mail personnalisé par prospect ───────────
        key_features = []
        phases = creative.get("execution_phases", [])
        if phases:
            key_features = phases[0].get("killer_features", [])[:3]

        email_drafts = []
        for p in prospects:
            email_prompt = f"""You are a B2B sales copywriter. Write a short, personalized prospecting email.

PROJECT: {project}
PROSPECT: {p.get('name')} — {p.get('role')} at {p.get('company')}
WHY THEY FIT: {p.get('why_fit', '')}
KEY VALUE PROPOSITIONS: {', '.join(key_features) if key_features else 'innovative solution'}

Rules:
- Max 120 words total (subject + body)
- Start with a personalized opening referencing their company or role
- Present ONE clear benefit (not a list)
- ONE call-to-action: suggest a 15-minute call
- Sign off as "The {project[:30]}... team"
- No attachments, no buzzwords

Return ONLY valid JSON:
{{
  "subject": "Email subject line",
  "body": "Full email body (greeting → value → CTA → sign-off)"
}}

Write ALL text in {lang_name}."""

            try:
                raw = smart_llm_pro.complete(
                    messages=[{"role": "user", "content": email_prompt}],
                    max_tokens=450,
                    **llm_params,
                )
                draft = _extract_json(raw) or {}
                email_drafts.append({
                    "prospect": p,
                    "subject": draft.get("subject", ""),
                    "body": draft.get("body", ""),
                    "status": "pending",  # attend validation fondateur
                })
            except Exception as e:
                email_drafts.append({
                    "prospect": p,
                    "subject": "",
                    "body": "",
                    "status": "error",
                    "error": str(e),
                })

        thoughts.append(f"{len(email_drafts)} email draft(s) generated")

        # ── ÉTAPE 3 : Post Facebook ───────────────────────────────────────
        market_trends_text = ', '.join([
            t.get('trend', '') for t in trend.get('market_trends', [])[:3]
        ])
        fb_prompt = f"""You are a social media manager for a startup. Write an engaging Facebook post.

PROJECT: {project}
MARKET CONTEXT: {market_trends_text}

Rules:
- 150–200 words
- Hook in the first line (question or bold statement)
- Story-driven, human and warm tone
- Explain the problem + hint at solution
- End with a clear call-to-action (visit website, comment, DM)
- 3–5 relevant hashtags at the end
- 1–2 relevant emojis placed naturally

Return ONLY valid JSON:
{{"post": "full Facebook post text including hashtags"}}

Write in {lang_name}."""

        fb_post = ""
        try:
            raw = smart_llm_pro.complete(
                messages=[{"role": "user", "content": fb_prompt}],
                max_tokens=400,
                **llm_params,
            )
            fb_data = _extract_json(raw) or {}
            fb_post = fb_data.get("post", "")
        except Exception as e:
            thoughts.append(f"Facebook post error: {e}")

        # ── ÉTAPE 4 : Post Instagram ──────────────────────────────────────
        ig_prompt = f"""You are an Instagram content strategist. Write a high-engagement Instagram caption.

PROJECT: {project}

Rules:
- Max 90 words for the caption (Instagram sweet spot)
- Punchy first line — no "We are..." or "Introducing..."
- Make it visual: describe a scene or feeling
- 1 call-to-action (link in bio, comment below, tag a friend)
- 8–12 relevant hashtags on a SEPARATE line at the end
- Maximum 2 emojis

Return ONLY valid JSON:
{{
  "caption": "Instagram caption text (no hashtags here)",
  "hashtags": ["hashtag1", "hashtag2", ...]
}}

Write caption in {lang_name}. Hashtags in English."""

        ig_caption = ""
        ig_hashtags = []
        try:
            raw = smart_llm_pro.complete(
                messages=[{"role": "user", "content": ig_prompt}],
                max_tokens=350,
                **llm_params,
            )
            ig_data = _extract_json(raw) or {}
            ig_caption  = ig_data.get("caption", "")
            ig_hashtags = ig_data.get("hashtags", [])
        except Exception as e:
            thoughts.append(f"Instagram post error: {e}")

        thoughts.append("Facebook + Instagram drafts ready")

        # ── Résultat final ────────────────────────────────────────────────
        return {
            "commercial_result": {
                "prospects":    prospects,
                "email_drafts": email_drafts,
                "social_posts": {
                    "facebook": {
                        "post":   fb_post,
                        "status": "pending",
                    },
                    "instagram": {
                        "caption":  ig_caption,
                        "hashtags": ig_hashtags,
                        "status":   "pending",
                    },
                },
                "agent_thoughts": thoughts,
            },
            "messages": [
                f"Commercial Agent: {len(prospects)} prospects | "
                f"{len(email_drafts)} emails | Facebook + Instagram — awaiting validation"
            ],
        }

    async def run(self, state: dict) -> dict:
        return await asyncio.to_thread(self.generate_sync, state)


# ─────────────────────────────────────────────────────────────
#  Singleton + fonction appelée par le graph
# ─────────────────────────────────────────────────────────────
_agent = CommercialAgent()


async def run_commercial_agent(state: dict) -> dict:
    return await _agent.run(state)
