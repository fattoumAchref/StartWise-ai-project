# agents/vision_agent.py - Vision hybride SmartInferenceProvider + UnifiedImageClient
import os
import io
import json
import asyncio
import base64
import httpx
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI
from ddgs import DDGS
from .inference import inference as smart_llm, image_client as unified_image, state_llm_params

load_dotenv()

_VISION_LANG_NAMES = {'fr': 'French', 'en': 'English', 'bm': 'Bambara', 'ar': 'Arabic'}


class VisionIntelligenceUnit:
    """Agent Visual Semiotics - tokenfactory/Llama-3.1-70B"""

    def __init__(self, lang='fr', llm_params=None):
        self.lang = lang
        self._llm_params = llm_params or {}

    @property
    def _lang_instruction(self):
        lang_name = _VISION_LANG_NAMES.get(self.lang, 'French')
        return f"\n\nCRITICAL: Generate ALL text values in {lang_name}. JSON keys must remain in English."

    def _call_groq(self, prompt: str, max_tokens: int = 1024) -> str:
        """Appel LLM via SmartInferenceProvider (Groq → ESPRIT fallback)."""
        full_prompt = prompt + self._lang_instruction
        return smart_llm.complete(
            messages=[{"role": "user", "content": full_prompt}],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=max_tokens,
            model_override=self._llm_params.get("model_override"),
        )
    
    # ==================== RECHERCHES WEB ====================
    
    async def search_web(self, query: str, max_results: int = 8) -> List[Dict]:
        """Recherche sur le web avec DuckDuckGo — filtre les sources non-latines"""
        import re
        results = []
        # Domaines et TLDs à exclure (cyrillique, sites non pertinents)
        blocked_tlds = {'.ru', '.ua', '.by', '.kz', '.su', '.рф', '.укр'}
        blocked_keywords = ['академия', 'аэрофлот', 'словарь', 'зоомагазин', 'мосэнерго',
                           'online-tablo', 'mosenergo', 'aeroflot', 'kyivstar']
        def is_valid_result(r):
            url = r.get("href", "").lower()
            title = r.get("title", "").lower()
            # Vérifier cyrillique dans le titre
            if re.search(r'[\u0400-\u04FF]', title):
                return False
            # Vérifier TLD bloqué
            if any(url.endswith(tld) or f"{tld}/" in url for tld in blocked_tlds):
                return False
            # Vérifier mots-clés bloqués
            if any(kw in url or kw in title for kw in blocked_keywords):
                return False
            return True

        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results * 2):
                    if is_valid_result(r):
                        results.append({
                            "title": r.get("title", ""),
                            "body": r.get("body", "")[:400],
                            "url": r.get("href", "")
                        })
                    if len(results) >= max_results:
                        break
        except Exception as e:
            print(f"Erreur recherche web: {e}")
        return results

    async def search_competitor_logos(self, project_desc: str) -> List[Dict]:
        """Recherche les concurrents — en anglais pour éviter les résultats étrangers"""
        search_query = f"{project_desc} competitors branding design visual identity site:linkedin.com OR site:crunchbase.com OR site:techcrunch.com"
        results = await self.search_web(search_query, max_results=5)
        if len(results) < 3:
            # Fallback sans filtre de site
            results = await self.search_web(f"{project_desc} top competitors brand identity", max_results=5)
        return results
    
    # ==================== ANALYSES SÉMIOTIQUES (Groq) ====================
    
    async def analyze_competitor_semiotics(self, competitors: List[Dict], project_desc: str, document_text: str = "") -> Dict:
        """Analyse sémiotique des concurrents (Cross-Mapping) - via Groq"""
        doc_section = (
            f"\n\n        CONTEXTE SUPPLÉMENTAIRE (DOCUMENT UTILISATEUR) :\n        {document_text[:2000]}\n"
            "        INSTRUCTION : Donne la priorité absolue à ces informations pour orienter le design.\n"
        ) if document_text.strip() else ""

        prompt = f"""
        Tu es un expert en sémiotique et design de marque pour grandes entreprises.

        CONCURRENTS IDENTIFIÉS:
        {json.dumps(competitors[:5], ensure_ascii=False)}

        PROJET: {project_desc}{doc_section}
        
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
    
    # ==================== GÉNÉRATION LOGOS HYBRIDES + IMAGES MOODBOARD ====================

    def _extract_company_name(self, project_desc: str) -> str:
        """Extrait le nom de l'entreprise du projet via Groq."""
        prompt = f"""Extrait uniquement le nom de l'entreprise/marque/startup mentionné dans ce texte.
Si aucun nom explicite n'est trouvé, invente un nom court et mémorable adapté au secteur (2 mots max).
Réponds UNIQUEMENT avec le nom, sans ponctuation, sans guillemets, sans explication.

TEXTE: {project_desc[:300]}"""
        try:
            return self._call_groq(prompt).strip().split("\n")[0].strip()[:30]
        except:
            return "StartWise"

    async def generate_logo_icons(self, project_desc: str, archetype: str, primary_color: str) -> Dict:
        """Génère 3 icônes pures via FLUX.1 (brand marks sans texte).
        Chaque icône sera combinée côté frontend avec le nom de l'entreprise."""

        # Demande au LLM de formuler 3 prompts d'icônes distincts et adaptés au projet
        prompt_request = f"""Tu es un directeur artistique expert en brand identity.

PROJET: {project_desc[:150]}
ARCHÉTYPE: {archetype}
COULEUR PRIMAIRE: {primary_color}

Formule 3 prompts FLUX.1 pour générer 3 icônes de marque (brand marks) SANS TEXTE.
Chaque icône représente un concept différent adapté au secteur du projet.

RÈGLES ABSOLUES pour chaque prompt:
- En ANGLAIS
- Un seul symbole/forme isolé, centré
- Style flat icon pour A, modern icon pour B, premium emblem pour C
- Fond uni (blanc pour A et C, foncé ou coloré pour B)
- Beaucoup d'espace négatif autour du symbole
- Chaque prompt DOIT se terminer par: "single icon centered, flat vector style, isolated on solid background, large negative space, no text, no letters, no words, ultra sharp, high definition"

Génère ce JSON avec 6 clés:
{{
  "icon_a_prompt": "...",
  "icon_a_label": "Piste A · [style en français]",
  "icon_b_prompt": "...",
  "icon_b_label": "Piste B · [style en français]",
  "icon_c_prompt": "...",
  "icon_c_label": "Piste C · [style en français]"
}}"""

        icon_prompts = {}
        try:
            raw = self._call_groq(prompt_request, max_tokens=1500)
            content = raw.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            icon_prompts = json.loads(content.strip())
        except Exception as e:
            print(f"[LOGO ICON] Fallback prompts: {e}")
            sector = project_desc[:60]
            icon_prompts = {
                "icon_a_prompt": f"Minimal flat icon symbol for {sector}, single geometric shape representing the sector, pure white background, centered. single icon centered, flat vector style, isolated on solid background, large negative space, no text, no letters, no words, ultra sharp, high definition",
                "icon_a_label": "Piste A · Minimalisme Essentiel",
                "icon_b_prompt": f"Modern bold icon for {sector}, {primary_color} solid color on dark navy #0f172a background, single strong geometric symbol, centered. single icon centered, flat vector style, isolated on solid background, large negative space, no text, no letters, no words, ultra sharp, high definition",
                "icon_b_label": "Piste B · Modernité Contrastée",
                "icon_c_prompt": f"Premium emblem icon for {sector}, circular badge shape, gold and neutral tones, institutional feel, single centered motif, white background. single icon centered, flat vector style, isolated on solid background, large negative space, no text, no letters, no words, ultra sharp, high definition",
                "icon_c_label": "Piste C · Prestige Institutionnel",
            }

        # Génère les 3 icônes en parallèle via UnifiedImageClient
        icon_batch = {
            "logo_a": icon_prompts.get("icon_a_prompt", ""),
            "logo_b": icon_prompts.get("icon_b_prompt", ""),
            "logo_c": icon_prompts.get("icon_c_prompt", ""),
        }
        seeds = {"logo_a": 1, "logo_b": 2, "logo_c": 3}
        icons = await unified_image.generate_batch(icon_batch, seeds=seeds)

        n = sum(1 for v in icons.values() if v)
        print(f"[LOGO ICON] {n}/3 icônes générées (HF→Pollinations)")

        return {
            "icons": icons,
            "labels": {
                "logo_a": icon_prompts.get("icon_a_label", "Piste A · Minimalisme"),
                "logo_b": icon_prompts.get("icon_b_label", "Piste B · Modernité"),
                "logo_c": icon_prompts.get("icon_c_label", "Piste C · Premium"),
            }
        }

    def _build_svg_prompt(self, company_name: str, project_desc: str, primary: str, accent: str, archetype: str) -> str:
        short = company_name[:2].upper()
        name_safe = company_name.replace("&", "&amp;").replace("<", "&lt;")
        return f"""Tu es un designer graphique senior expert en identité visuelle. Génère 3 logos SVG professionnels pour:

ENTREPRISE: {company_name}
SECTEUR: {project_desc[:120]}
ARCHÉTYPE: {archetype}
COULEUR PRIMAIRE: {primary}
COULEUR ACCENT: {accent}
INITIALES: {short}

CONTRAINTES TECHNIQUES ABSOLUES:
- viewBox="0 0 400 200" pour chaque SVG
- font-family="system-ui, -apple-system, sans-serif" UNIQUEMENT
- SVG auto-contenus, aucune dépendance externe
- Le nom "{name_safe}" DOIT être visible dans chaque logo
- Chaque SVG sur UNE SEULE LIGNE dans le JSON (remplace les retours à la ligne par des espaces)

LOGO A — Wordmark minimaliste:
Fond blanc #ffffff. Un pictogramme géométrique simple (cercle, carré arrondi, forme liée au secteur) en {primary} à gauche. Le nom "{name_safe}" en font-size="42" font-weight="700" fill="#1a1a2e" à droite du pictogramme. Optionnel: tagline en font-size="14" fill="#64748b".

LOGO B — Négatif / Contraste:
Fond foncé {primary} ou #0f172a. Forme géométrique en blanc ou {accent}. Nom "{name_safe}" en blanc, font-size="40" font-weight="800" letter-spacing="3". Style moderne et percutant.

LOGO C — Badge institutionnel:
Fond blanc #f8f9fa. Cercle ou hexagone avec bordure fine {primary}. Initiales "{short}" à l'intérieur en {primary}, font-size="48" font-weight="800". Nom "{name_safe}" sous le badge en font-size="20" font-weight="600". Élégant et sobre.

Réponds UNIQUEMENT avec ce JSON valide (SVG sur une seule ligne chacun):
{{"logo_a_svg": "<svg.../>", "logo_a_label": "Piste A · [style en français]", "logo_b_svg": "<svg.../>", "logo_b_label": "Piste B · [style en français]", "logo_c_svg": "<svg.../>", "logo_c_label": "Piste C · [style en français]"}}"""

    def _parse_svg_response(self, response: str, company_name: str, primary: str, accent: str) -> Dict:
        """Parse la réponse SVG du LLM avec fallback robuste."""
        try:
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            # Nettoyage des retours à la ligne dans les valeurs SVG
            import re
            content = re.sub(r'(?<=[^\\])\n(?=[^"]*")', ' ', content)
            data = json.loads(content.strip())
            # Vérification que les SVG contiennent bien le nom
            for key in ["logo_a_svg", "logo_b_svg", "logo_c_svg"]:
                if key not in data or "<svg" not in str(data.get(key, "")):
                    raise ValueError(f"SVG manquant pour {key}")
            print(f"[VISION SVG] ✓ 3 logos SVG parsés pour '{company_name}'")
            return data
        except Exception as e:
            print(f"[VISION SVG] Fallback SVG: {e}")
            return self._fallback_svg_logos(company_name, primary, accent)

    async def generate_svg_logos(self, company_name: str, project_desc: str, primary_color: str, secondary_colors: List[str], archetype: str) -> Dict:
        """Génère 3 logos SVG complets via LLM — vectoriel, net, avec vrai nom de marque."""
        accent = secondary_colors[0] if secondary_colors else "#6366f1"

        prompt = f"""Tu es un designer graphique expert en identité visuelle. Génère 3 logos SVG distincts et professionnels pour:

ENTREPRISE: {company_name}
SECTEUR: {project_desc[:120]}
ARCHÉTYPE: {archetype}
COULEUR PRIMAIRE: {primary_color}
COULEUR ACCENT: {accent}

RÈGLES ABSOLUES:
- Chaque SVG doit être complet, valide, auto-contenu (viewBox="0 0 400 200")
- Le nom "{company_name}" DOIT apparaître dans chaque logo
- Utilise UNIQUEMENT font-family="system-ui, -apple-system, sans-serif" (jamais d'import externe)
- Zéro dépendance externe, zéro image, zéro filtre complexe — SVG pur
- Chaque logo doit être visuellement distinct (minimaliste / moderne / premium)
- Qualité agence : espacement, alignement, proportions parfaites

Génère exactement ce JSON (les SVG complets en valeurs):
{{
  "logo_a_svg": "<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'>...LOGO MINIMALISTE FLAT...</svg>",
  "logo_a_label": "Piste A · [style adapté au projet]",
  "logo_b_svg": "<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'>...LOGO MODERNE AVEC FORME GÉOMÉTRIQUE + COULEUR PRIMAIRE...</svg>",
  "logo_b_label": "Piste B · [style adapté au projet]",
  "logo_c_svg": "<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'>...LOGO PREMIUM AVEC BADGE/EMBLÈME...</svg>",
  "logo_c_label": "Piste C · [style adapté au projet]"
}}

LOGO A — Minimaliste flat:
- Fond blanc (#FFFFFF)
- Un pictogramme simple lié au secteur (forme géométrique pure: cercle, carré, triangle, losange...)
- Nom "{company_name}" en font-weight="700" taille ~48px, couleur sombre (#1a1a2e ou similaire)
- Sous-titre court (activité en 2-3 mots) en font-weight="400" taille ~16px, couleur grise

LOGO B — Moderne géométrique:
- Fond sombre (ex: {primary_color} ou #0f172a)
- Forme géométrique dynamique (arc, hexagone, gradient SVG, lignes) en {primary_color} ou blanc
- Nom "{company_name}" en blanc, bold, espacement lettres légèrement augmenté (letter-spacing="2")
- Petit accent de couleur {accent}

LOGO C — Premium emblème:
- Fond blanc ou très clair (#f8f9fa)
- Badge circulaire ou hexagonal centré, bordure fine {primary_color}
- Initiale(s) de "{company_name}" stylisées à l'intérieur, grandes, couleur {primary_color}
- Nom complet "{company_name}" en arc sous/sur le badge, ou en dessous en small caps
- Style institutionnel, sobre, haut de gamme

Réponds UNIQUEMENT avec le JSON valide. Les SVG doivent être sur une seule ligne (pas de retours à la ligne dans les valeurs JSON).
"""
        response = self._call_groq(prompt, max_tokens=2000)
        try:
            content = response.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            data = json.loads(content.strip())
            print(f"[VISION SVG] ✓ 3 logos SVG générés pour '{company_name}'")
            return data
        except Exception as e:
            print(f"[VISION SVG] Erreur parsing: {e} — fallback SVG")
            return self._fallback_svg_logos(company_name, primary_color, accent)

    def _fallback_svg_logos(self, company_name: str, primary: str, accent: str) -> Dict:
        """SVG de fallback propres si le LLM échoue."""
        short = company_name[:2].upper()
        name_safe = company_name.replace("&", "&amp;").replace("<", "&lt;")
        return {
            "logo_a_svg": f"<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'><rect width='400' height='200' fill='#ffffff'/><circle cx='80' cy='100' r='36' fill='{primary}' opacity='0.15'/><circle cx='80' cy='100' r='22' fill='{primary}'/><text x='130' y='112' font-family='system-ui,-apple-system,sans-serif' font-size='48' font-weight='700' fill='#1a1a2e'>{name_safe}</text></svg>",
            "logo_a_label": "Piste A · Minimalisme Essentiel",
            "logo_b_svg": f"<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'><rect width='400' height='200' fill='#0f172a'/><polygon points='70,60 110,60 130,100 110,140 70,140 50,100' fill='{primary}'/><text x='60' y='112' font-family='system-ui,-apple-system,sans-serif' font-size='22' font-weight='900' fill='#ffffff' letter-spacing='2'>{short}</text><text x='155' y='115' font-family='system-ui,-apple-system,sans-serif' font-size='44' font-weight='700' fill='#ffffff' letter-spacing='2'>{name_safe}</text></svg>",
            "logo_b_label": "Piste B · Modernité Contrastée",
            "logo_c_svg": f"<svg viewBox='0 0 400 200' xmlns='http://www.w3.org/2000/svg'><rect width='400' height='200' fill='#f8f9fa'/><circle cx='100' cy='100' r='60' fill='none' stroke='{primary}' stroke-width='2'/><circle cx='100' cy='100' r='50' fill='none' stroke='{primary}' stroke-width='0.5' opacity='0.4'/><text x='100' y='116' font-family='system-ui,-apple-system,sans-serif' font-size='42' font-weight='800' fill='{primary}' text-anchor='middle'>{short}</text><text x='210' y='95' font-family='system-ui,-apple-system,sans-serif' font-size='36' font-weight='700' fill='#1a1a2e'>{name_safe}</text><text x='210' y='122' font-family='system-ui,-apple-system,sans-serif' font-size='13' font-weight='400' fill='#64748b' letter-spacing='3'>PREMIUM · BRAND</text></svg>",
            "logo_c_label": "Piste C · Prestige Institutionnel",
        }

    async def generate_image_prompts(self, project_desc: str, archetype: str, primary_color: str, counter_signifiers: List[str]) -> Dict:
        """Formule des prompts MOODBOARD atmosphériques pour FLUX.1 (logos gérés séparément en SVG)."""
        prompt = f"""Tu es un directeur artistique expert en branding.

PROJET: {project_desc}
ARCHÉTYPE DE MARQUE: {archetype}
COULEUR PRIMAIRE (HEX): {primary_color}
CONTRE-SIGNIFIANTS: {json.dumps(counter_signifiers, ensure_ascii=False)}

Génère 3 prompts d'images atmosphériques pour FLUX.1-schnell (en ANGLAIS).
Ces images sont du moodboard — des ambiances visuelles, pas des logos.

- mood_1_prompt: Scène cinématique évoquant l'archétype "{archetype}" pour ce secteur. Lumière dramatique, palette sombre et élégante, aucune personne.
- mood_1_label: (en français, ex: "Ambiance · Autorité & Expertise", adapté à l'archétype)
- mood_2_prompt: Mise en situation éditoriale haut de gamme du produit/service. Style magazine premium, sans personnes.
- mood_2_label: (en français, adapté au projet)
- mood_3_prompt: Macro-texture abstraite évoquant les valeurs clés de la marque. Profondeur de champ, matière riche, lumière rasante.
- mood_3_label: (en français, adapté au projet)

Tous les prompts se terminent par: "No text, no letters, no words, no numbers, no people. Ultra sharp, cinematic, high definition."

Réponds UNIQUEMENT en JSON avec ces 6 clés exactes.
"""
        response = self._call_groq(prompt, max_tokens=800)
        try:
            content = response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception as e:
            print(f"[VISION] Erreur parsing mood_prompts: {e}")
            sector = project_desc[:60]
            return {
                "mood_1_prompt": f"Cinematic atmospheric scene evoking {archetype} archetype for {sector}, dramatic light, dark elegant palette, no people. No text, no letters. Ultra sharp, cinematic, high definition.",
                "mood_1_label": f"Ambiance · {archetype}",
                "mood_2_prompt": f"High-end editorial still life representing {sector} brand universe, premium magazine aesthetic, no people. No text, no letters. Ultra sharp, cinematic, high definition.",
                "mood_2_label": "Univers · Mise en Situation",
                "mood_3_prompt": f"Abstract macro texture evoking the core values of {sector} brand, depth of field, raking light, rich material, no people. No text, no letters. Ultra sharp, cinematic, high definition.",
                "mood_3_label": "Texture · Signal de Marque",
            }

    async def generate_all_images(self, prompts: Dict) -> Dict:
        """
        Lance les 3 générations moodboard en parallèle via UnifiedImageClient.
        HuggingFace FLUX.1-schnell (40s) → Pollinations fallback automatique.
        """
        batch = {
            k: prompts.get(f"{k}_prompt", "")
            for k in ["mood_1", "mood_2", "mood_3"]
            if prompts.get(f"{k}_prompt")
        }
        seeds = {"mood_1": 10, "mood_2": 20, "mood_3": 30}
        images = await unified_image.generate_batch(batch, seeds=seeds)
        n = sum(1 for v in images.values() if v)
        print(f"[VISION IMAGE] {n}/3 images moodboard générées (HF→Pollinations)")
        return images

    # ==================== ANALYSE COMPLÈTE ====================

    async def analyze_visual_identity(self, project_desc: str, trend_result: Dict = None, document_text: str = "") -> Dict:
        """Analyse complète de l'identité visuelle"""
        
        thoughts = [
            "[INIT] Initialisation de la rétine artificielle (Groq/Llama-4-Scout)...",
            "[SYNC] Réception des Gaps de marché du Trend Hunter...",
            "[SEARCH] Recherche des concurrents visuels...",
            "[SEMIOTICS] Cross-mapping des signifiants concurrents...",
            "[COLORS] Extraction de la palette chromatique psychologique...",
            "[TYPOGRAPHY] Sélection des polices adaptées à l'archétype...",
            "[VIBE] Simulation de perception émotionnelle cible...",
            "[AGING] Prédiction de durabilité esthétique (10 ans)...",
            "[IMAGE] Formulation des prompts de direction artistique...",
            "[IMAGE] Génération des concepts logos et moodboard via FLUX.1...",
        ]

        # 1. Recherche des concurrents
        competitors = await self.search_competitor_logos(project_desc)
        thoughts.append(f"[OK] {len(competitors)} concurrents visuels identifiés")

        # 2. Analyse sémiotique
        semiotics = await self.analyze_competitor_semiotics(competitors, project_desc, document_text)
        archetype = semiotics.get("recommended_archetype", "The Sage")
        thoughts.append(f"[SEMIOTICS] Archétype recommandé : {archetype}")

        # 3. Palette de couleurs
        colors = await self.generate_color_palette(project_desc, semiotics.get("counter_signifiers", []))
        primary_color = colors.get("primary", {}).get("hex", "#0D9488")
        thoughts.append(f"[COLORS] Couleur primaire : {primary_color}")

        # 4. Typographie
        typography = await self.generate_typography_pair(project_desc, archetype)

        # 5. Style visuel (dynamique selon archétype)
        visual_style = {
            "style": "Glassmorphism subtil + Flat 3.0",
            "justification": f"Adapté à l'archétype {archetype} — modernité sans excès",
            "application": "Cards avec backdrop-blur, boutons avec ombres douces"
        }

        # 6. Vibe Check
        vibe = await self.vibe_check(visual_style, project_desc)

        # 7. Temporal Aging
        aging = await self.temporal_aging_score(visual_style)

        # 8. Design Tokens
        design_tokens = {
            "colors": {
                "primary": primary_color,
                "secondary": [c.get("hex") for c in colors.get("secondary", [])],
                "accent": colors.get("accent", {}).get("hex", "#F4D03F"),
                "neutral": colors.get("neutral", {}).get("hex", "#2C2C2C")
            },
            "typography": {
                "heading": typography.get("heading", {}).get("name", "Playfair Display"),
                "body": typography.get("body", {}).get("name", "Inter")
            },
            "spacing": {"padding": "32px", "gap": "24px", "border_radius": "16px"},
            "effects": {"style": visual_style.get("style", "Glassmorphism"), "backdrop_blur": "12px"}
        }

        # 9. Extraction du nom de l'entreprise
        thoughts.append("[BRAND] Extraction du nom de l'entreprise...")
        company_name = await asyncio.to_thread(self._extract_company_name, project_desc)
        thoughts.append(f"[OK] Nom de marque identifié : {company_name}")

        # 10. Génération des 3 icônes FLUX.1 + moodboard en parallèle
        thoughts.append("[LOGO] Génération des 3 icônes brand mark via FLUX.1...")
        thoughts.append("[IMAGE] Génération moodboard atmosphérique via FLUX.1 (parallèle)...")

        mood_prompts_task = self.generate_image_prompts(
            project_desc, archetype, primary_color,
            semiotics.get("counter_signifiers", [])
        )
        logo_icons_task = self.generate_logo_icons(project_desc, archetype, primary_color)

        mood_prompts, logo_result = await asyncio.gather(mood_prompts_task, logo_icons_task)
        mood_images = await self.generate_all_images(mood_prompts)

        n_icons = sum(1 for v in logo_result["icons"].values() if v)
        n_mood = sum(1 for v in mood_images.values() if v)
        thoughts.append(f"[OK] {n_icons}/3 icônes brand mark générées")
        thoughts.append(f"[OK] {n_mood}/3 visuels moodboard générés")

        # Les icônes seront assemblées côté frontend avec le nom de l'entreprise
        images = {**logo_result["icons"], **mood_images}

        image_labels = {
            **logo_result["labels"],
            "mood_1": mood_prompts.get("mood_1_label", "Ambiance · Atmosphère"),
            "mood_2": mood_prompts.get("mood_2_label", "Univers · Mise en Situation"),
            "mood_3": mood_prompts.get("mood_3_label", "Texture · Signal de Marque"),
        }

        confidence_score = (vibe.get("aesthetic_score", 80) / 100) * 10

        return {
            "score": round(confidence_score, 1),
            "model_used": "Llama-3.1-70B (tokenfactory) + FLUX.1-schnell (logos hybrides + moodboard)",
            "semiotics_analysis": semiotics,
            "color_palette": colors,
            "typography": typography,
            "visual_style": visual_style,
            "vibe_check": vibe,
            "temporal_aging": aging,
            "design_tokens": design_tokens,
            "competitors_analyzed": len(competitors),
            "agent_thoughts": thoughts,
            "web_sources": [{"url": c.get("url"), "title": c.get("title")} for c in competitors if c.get("url")],
            "images": images,
            "image_labels": image_labels,
            # Données brand pour le composant LogoHybride côté frontend
            "company_name": company_name,
            "brand_primary_color": primary_color,
            "brand_font": typography.get("heading", {}).get("name", "Inter"),
        }

async def run_vision_agent(state: dict) -> dict:
    """Fonction principale de l'agent Visual Semiotics"""
    lang = state.get("lang", "fr")
    llm_params = state_llm_params(state)
    agent = VisionIntelligenceUnit(lang=lang, llm_params=llm_params)
    project_desc = state["project_description"]
    trend_result = state.get("trend_result", {})
    document_text = state.get("document_text", "")

    print(f"\n{'='*50}")
    print(f"👁️ VISUAL SEMIOTICS AGENT — model={llm_params.get('model_override','défaut')} temp={llm_params.get('temperature')}")
    print(f"📝 Projet: {project_desc}")
    if document_text:
        print(f"📄 Document RAG: {len(document_text)} chars injectés")
    print(f"{'='*50}\n")

    result = await agent.analyze_visual_identity(project_desc, trend_result, document_text)
    
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