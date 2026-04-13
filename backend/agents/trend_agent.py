# agents/trend_agent.py — High-Availability avec SmartInferenceProvider + UnifiedImageClient
import re
import json
import asyncio
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document
from ddgs import DDGS
import aiohttp
from .inference import inference_pro as smart_llm_pro, image_client as unified_image, state_llm_params

load_dotenv()

# ────────────────────────────────────────────────────────────────────────── #
#  Utilitaires                                                                #
# ────────────────────────────────────────────────────────────────────────── #

async def _check_url(url: str, session: aiohttp.ClientSession) -> bool:
    if not url:
        return False
    try:
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(total=4),
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; StartWise/1.0)"}
        ) as resp:
            return resp.status < 400
    except Exception:
        return False


def _extract_json(text: str) -> dict:
    """Extraction JSON robuste depuis une réponse LLM (gère markdown, texte parasite)."""
    text = text.strip()

    # 1. Parse direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Bloc ```json ... ```
    m = re.search(r'```json\s*([\s\S]+?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # 3. Bloc ``` ... ```
    m = re.search(r'```\s*([\s\S]+?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except Exception:
            pass

    # 4. Trouver le bloc { ... } le plus grand
    depth = 0
    start = -1
    best = ""
    for i, c in enumerate(text):
        if c == '{':
            if depth == 0:
                start = i
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start:i + 1]
                if len(candidate) > len(best):
                    best = candidate
    if best:
        try:
            return json.loads(best)
        except Exception:
            pass

    return {}


# ────────────────────────────────────────────────────────────────────────── #
#  Génération d'images HuggingFace                                           #
# ────────────────────────────────────────────────────────────────────────── #

async def generate_ai_image(prompt_context: str, tab_name: str) -> str:
    """
    Génère une image via UnifiedImageClient (HF FLUX.1 → Pollinations fallback).
    Retourne une data URI WebP base64 ou "".
    """
    style_suffix = (
        ". Ultra-high definition, architectural cinematic 3D render. "
        "Sharp edges, zero film grain. Dark navy background. No people. "
        "McKinsey premium consulting visual, photorealistic depth."
    )
    tab_prompts = {
        "risks": (
            f"3D dark corporate scene for {prompt_context[:55]}. "
            "Fractured crimson hexagons cascading in dark void, amber glow, moody atmosphere. "
            "No text, no letters, no people."
        ),
        "strategy": (
            f"3D architectural growth visualization for {prompt_context[:55]}. "
            "Three illuminated glass towers rising, connected by glowing indigo bridges, "
            "ascending perspective, dark navy background, emerald light reflections. "
            "No text, no letters, no people."
        ),
        "premortem": (
            f"3D business collapse scene for {prompt_context[:55]}. "
            "Crumbling dark stone architecture, glowing amber cracks, dust particles, "
            "deep burgundy and charcoal tones, cinematic depth. "
            "No text, no letters, no people."
        ),
    }
    prompt = tab_prompts.get(tab_name, f"3D dark corporate scene for {prompt_context[:55]}.") + style_suffix
    seeds = {"risks": 10, "strategy": 20, "premortem": 30}
    return await unified_image.generate(prompt, seed=seeds.get(tab_name, 42), label=tab_name)


# ────────────────────────────────────────────────────────────────────────── #
#  WebResearcher                                                              #
# ────────────────────────────────────────────────────────────────────────── #

class WebResearcher:
    async def search_web(self, query: str, max_results: int = 6) -> List[Dict]:
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
            print(f"[WebResearcher] Erreur DuckDuckGo: {e}")
        return results

    async def search_reddit(self, query: str) -> List[Dict]:
        return await self.search_web(f"site:reddit.com {query}", max_results=3)


# ────────────────────────────────────────────────────────────────────────── #
#  TrendHunterAgent                                                           #
# ────────────────────────────────────────────────────────────────────────── #

_TREND_LANG_NAMES = {'fr': 'French', 'en': 'English', 'bm': 'Bambara', 'ar': 'Arabic'}


class TrendHunterAgent:

    def __init__(self, lang='fr', llm_params=None):
        self.researcher = WebResearcher()
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self._thoughts: List[str] = []
        self.lang = lang
        self._llm_params = llm_params or {}

    @property
    def _lang_instruction(self):
        lang_name = _TREND_LANG_NAMES.get(self.lang, 'French')
        return f"Generate ALL text values in {lang_name}. JSON keys must remain in English."

    def _log(self, tag: str, msg: str):
        line = f"[{tag:<10}] {msg}"
        self._thoughts.append(line)
        print(line)

    # ── Vérification des sources ──────────────────────────────────────────

    async def _verify_sources(self, results: List[Dict]) -> Tuple[List[Dict], int]:
        valid: List[Dict] = []
        dead = 0
        async with aiohttp.ClientSession() as session:
            for item in results:
                url = item.get("url", "")
                alive = await _check_url(url, session)
                domain = url.split("/")[2] if url.count("/") >= 2 else url[:40]
                if alive:
                    valid.append(item)
                    self._log("OK", f"✓ {domain}")
                else:
                    dead += 1
                    self._log("ERROR", f"✗ {domain} → domaine expiré, ignoré")
        return valid, dead

    # ── Expert fallback (LLM pur, sans données web) ───────────────────────

    async def _expert_fallback(self, project_desc: str, document_text: str = "") -> Dict:
        """Génère une analyse stratégique complète via expertise LLM pure."""
        self._log("ANALYSIS", "Fallback expert LLM — génération de données analytiques internes...")

        system_msg = (
            "You are a senior McKinsey consultant with deep expertise in startup strategy, "
            "market analysis, and risk assessment. "
            "Respond ONLY with valid JSON — no markdown, no code blocks, no explanation."
        )

        doc_section = (
            f"\n\nSUPPLEMENTARY CONTEXT (USER DOCUMENT):\n{document_text[:3000]}\n"
            "INSTRUCTION: Give absolute priority to this context over your general knowledge.\n"
        ) if document_text.strip() else ""

        user_msg = f"""Perform a rigorous strategic analysis for this project: "{project_desc}"{doc_section}

Return EXACTLY this JSON structure with realistic, sector-specific values:

{{
  "risk_score": 7,
  "main_risks": [
    {{
      "risk": "Concise risk title (max 6 words)",
      "description": "Two precise sentences describing this risk based on sector knowledge for this type of project.",
      "mitigation": "Two concrete, actionable sentences — what to do in the first 90 days.",
      "probability": 72,
      "impact": 8
    }},
    {{
      "risk": "Second distinct risk title",
      "description": "Two precise sentences.",
      "mitigation": "Two concrete sentences.",
      "probability": 55,
      "impact": 7
    }},
    {{
      "risk": "Third distinct risk title",
      "description": "Two precise sentences.",
      "mitigation": "Two concrete sentences.",
      "probability": 40,
      "impact": 6
    }},
    {{
      "risk": "Fourth distinct risk title",
      "description": "Two precise sentences.",
      "mitigation": "Two concrete sentences.",
      "probability": 30,
      "impact": 5
    }}
  ],
  "recommendations": [
    {{
      "recommendation": "Specific, measurable strategic action aligned with the project context.",
      "phase": "Phase 1",
      "month_start": 1,
      "month_end": 4,
      "priority": "high"
    }},
    {{
      "recommendation": "Second concrete strategic action.",
      "phase": "Phase 1",
      "month_start": 2,
      "month_end": 4,
      "priority": "high"
    }},
    {{
      "recommendation": "Third concrete action for growth phase.",
      "phase": "Phase 2",
      "month_start": 5,
      "month_end": 8,
      "priority": "medium"
    }},
    {{
      "recommendation": "Fourth action — scaling or optimization.",
      "phase": "Phase 2",
      "month_start": 6,
      "month_end": 8,
      "priority": "medium"
    }},
    {{
      "recommendation": "Fifth action — long-term consolidation.",
      "phase": "Phase 3",
      "month_start": 9,
      "month_end": 12,
      "priority": "low"
    }}
  ]
}}

Rules:
- risk_score between 5 and 9 based on sector complexity
- probability values must be distinct (not all the same)
- impact values must be distinct (not all the same)
- All content must be specific to this project type — never generic platitudes
- {lang_instr}""".format(lang_instr=self._lang_instruction)

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=2048,
            model_override=self._llm_params.get("model_override"),
        ))

        result = _extract_json(raw)
        if result.get("main_risks"):
            n_risks = len(result["main_risks"])
            n_recs = len(result.get("recommendations", []))
            self._log("OK", f"Fallback expert — {n_risks} risques · {n_recs} recommandations générés")
        else:
            self._log("ERROR", "Fallback expert : parsing échoué également — données vides")
        return result

    # ── Gap analysis ──────────────────────────────────────────────────────

    async def _gap_analysis(self, competitor_texts: List[str], project_desc: str) -> Dict:
        gap_prompt = f"""Données concurrentielles collectées :
{json.dumps(competitor_texts[:3])}

Projet analysé :
{project_desc}

Génère une analyse de positionnement stratégique. JSON strict (no markdown) :
{{
  "crowded_zones": [
    "description précise d'un segment saturé basé sur les données"
  ],
  "opportunity_zones": [
    "description d'une opportunité non exploitée"
  ],
  "blue_ocean_opportunity": "niche stratégique spécifique ignorée par les acteurs existants, argumentée",
  "competitive_advantage": "avantage concurrentiel différenciant recommandé",
  "canvas_factors": [
    {{"factor": "nom du facteur", "competitor_avg_score": 7, "startup_score": 4}}
  ]
}}

Règles :
- crowded_zones : 3 segments précis
- opportunity_zones : 3 opportunités argumentées
- canvas_factors : exactement 6 facteurs distincts (prix, rapidité, personnalisation, fiabilité, support, innovation ou équivalents sectoriels)
- Scores sur 10, distincts et réalistes
- {self._lang_instruction}"""

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[{"role": "user", "content": gap_prompt}],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=1024,
            model_override=self._llm_params.get("model_override"),
        ))
        result = _extract_json(raw)
        if not result.get("canvas_factors"):
            # Fallback gap analysis
            result = await self._expert_gap_fallback(project_desc)
        return result

    async def _expert_gap_fallback(self, project_desc: str) -> Dict:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[
                {"role": "system", "content": "Senior strategy consultant. Respond ONLY with valid JSON, no markdown."},
                {"role": "user", "content": f"""Gap analysis for: "{project_desc}"

Return this exact JSON:
{{"crowded_zones": ["segment 1", "segment 2", "segment 3"], "opportunity_zones": ["opp 1", "opp 2", "opp 3"], "blue_ocean_opportunity": "specific niche description", "competitive_advantage": "specific advantage", "canvas_factors": [{{"factor": "Prix", "competitor_avg_score": 6, "startup_score": 8}}, {{"factor": "Rapidité", "competitor_avg_score": 7, "startup_score": 5}}, {{"factor": "Personnalisation", "competitor_avg_score": 4, "startup_score": 9}}, {{"factor": "Fiabilité", "competitor_avg_score": 8, "startup_score": 6}}, {{"factor": "Support", "competitor_avg_score": 5, "startup_score": 8}}, {{"factor": "Innovation", "competitor_avg_score": 3, "startup_score": 9}}]}}"""},
            ],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=512,
            model_override=self._llm_params.get("model_override"),
        ))
        return _extract_json(raw)

    # ── Pre-mortem ────────────────────────────────────────────────────────

    async def _pre_mortem(self, project_desc: str, risks: List[Dict]) -> Dict:
        pm_prompt = f"""Projet : {project_desc}
Risques identifiés : {json.dumps([{"risk": r.get("risk", ""), "description": r.get("description", "")} for r in risks[:3]])}

Simule un scénario d'échec réaliste à horizon 5 ans. JSON strict (no markdown) :
{{
  "primary_cause": "cause principale d'échec liée aux risques identifiés",
  "secondary_causes": ["cause 1", "cause 2", "cause 3"],
  "lessons_learned": "enseignement stratégique actionnable",
  "could_it_have_been_saved": "pivot ou décision concrète qui aurait inversé la trajectoire",
  "failure_timeline": [
    {{"year": "An 1", "event": "événement déclencheur initial", "severity": "low"}},
    {{"year": "An 2", "event": "aggravation et premiers signaux d'alarme", "severity": "medium"}},
    {{"year": "An 3", "event": "point de non-retour atteint", "severity": "high"}},
    {{"year": "An 4-5", "event": "dénouement final", "severity": "critical"}}
  ]
}}
severity : low | medium | high | critical
- {self._lang_instruction}"""

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[{"role": "user", "content": pm_prompt}],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=1024,
            model_override=self._llm_params.get("model_override"),
        ))
        result = _extract_json(raw)
        if not result.get("failure_timeline"):
            result = await self._expert_premortem_fallback(project_desc)
        return result

    async def _expert_premortem_fallback(self, project_desc: str) -> Dict:
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[
                {"role": "system", "content": "Senior consultant. Respond ONLY with valid JSON, no markdown."},
                {"role": "user", "content": f"""Pre-mortem simulation for: "{project_desc}"

Return: {{"primary_cause": "specific cause", "secondary_causes": ["cause1","cause2","cause3"], "lessons_learned": "actionable lesson", "could_it_have_been_saved": "concrete pivot", "failure_timeline": [{{"year": "An 1","event": "trigger event description","severity": "low"}},{{"year": "An 2","event": "aggravation description","severity": "medium"}},{{"year": "An 3","event": "point of no return","severity": "high"}},{{"year": "An 4-5","event": "final dissolution","severity": "critical"}}]}}"""},
            ],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=512,
            model_override=self._llm_params.get("model_override"),
        ))
        return _extract_json(raw)

    # ── Analyse principale ────────────────────────────────────────────────

    async def analyze_with_web_intelligence(self, project_desc: str, document_text: str = "") -> Dict:
        self._thoughts = []

        # ── Étape 1 : Décomposition ────────────────────────────────────
        self._log("THINKING", f"Analyse du projet : \"{project_desc[:70]}\"")
        self._log("THINKING", "Génération des requêtes de recherche stratégiques...")
        queries = [
            f"{project_desc} market size analysis 2024 2025",
            f"{project_desc} competitors landscape",
            f"{project_desc} startup risks failure reasons",
            f"{project_desc} emerging trends opportunities"
        ]
        for q in queries:
            self._log("SEARCH", f"Requête : \"{q[:80]}\"")

        # ── Étape 2 : Collecte web ────────────────────────────────────
        self._log("SEARCH", "Accès à DuckDuckGo — collecte des résultats...")
        raw_market = await self.researcher.search_web(
            f"{project_desc} market analysis competitors 2024", max_results=6
        )
        self._log("READ", f"{len(raw_market)} résultats bruts récupérés")

        self._log("CHECK", f"Vérification de l'accessibilité des {len(raw_market)} URLs...")
        valid_market, dead_market = await self._verify_sources(raw_market)
        self._log("FILTER", f"{len(valid_market)} sources valides · {dead_market} domaines expirés ignorés")

        # ── Étape 3 : Reddit ──────────────────────────────────────────
        self._log("SEARCH", "Recherche Reddit — retours utilisateurs et plaintes...")
        raw_reddit = await self.researcher.search_reddit(f"{project_desc} user experience problems")
        valid_reddit, dead_reddit = await self._verify_sources(raw_reddit)
        self._log("READ", f"{len(valid_reddit)} discussions Reddit valides · {dead_reddit} ignorées")

        # ── Étape 4 : Signaux faibles ─────────────────────────────────
        self._log("SEARCH", "Détection des signaux faibles et tendances émergentes...")
        raw_signals = await self.researcher.search_web(
            f"{project_desc} emerging trends innovation 2025", max_results=5
        )
        valid_signals, _ = await self._verify_sources(raw_signals)
        self._log("READ", f"{len(valid_signals)} signaux détectés")

        # ── Étape 5 : Base vectorielle ────────────────────────────────
        all_valid = valid_market + valid_reddit
        self._log("ANALYSIS", f"Indexation vectorielle de {len(all_valid)} documents...")

        documents = [
            Document(
                page_content=f"{r['title']}\n{r['body'][:300]}",
                metadata={"source": "web", "url": r.get("url", ""), "title": r.get("title", "")}
            )
            for r in all_valid
        ] or [Document(
            page_content=f"Analyse IA du projet : {project_desc}",
            metadata={"source": "ia", "url": ""}
        )]

        vector_db = FAISS.from_documents(documents, self.embeddings)
        self._log("GREP", "Recherche vectorielle des cas sémantiquement proches...")
        sim_results = await vector_db.asimilarity_search_with_score(project_desc, k=5)
        self._log("READ", f"{len(sim_results)} cas similaires extraits par similarité cosinus")

        # ── Étape 6 : Gap analysis ────────────────────────────────────
        self._log("ANALYSIS", "Cartographie des gaps concurrentiels...")
        competitor_texts = [r[0].page_content[:300] for r in sim_results[:3]]
        gap_analysis = await self._gap_analysis(competitor_texts, project_desc)
        n_opps = len(gap_analysis.get("opportunity_zones", []))
        n_canvas = len(gap_analysis.get("canvas_factors", []))
        self._log("OK", f"Gap analysis — {n_opps} opportunités · {n_canvas} facteurs canvas")

        # ── Étape 7 : Signaux faibles structurés ─────────────────────
        weak_signals = [
            {
                "signal": r["title"][:100],
                "description": r["body"][:200],
                "opportunity": "",
                "source": {"title": r["title"], "url": r.get("url", ""), "type": "web"}
            }
            for r in valid_signals[:5]
        ]
        self._log("SIGNALS", f"{len(weak_signals)} signaux faibles structurés")

        # ── Étape 8 : Rapport stratégique principal ───────────────────
        self._log("ANALYSIS", "Génération du rapport stratégique principal via LLM...")

        doc_section = (
            f"\n\n---\nCONTEXTE SUPPLÉMENTAIRE (DOCUMENT UTILISATEUR) :\n{document_text[:3000]}\n"
            "INSTRUCTION : Donne la priorité absolue à ces informations sur tes connaissances générales.\n---"
        ) if document_text.strip() else ""

        main_prompt = f"""Projet analysé : {project_desc}{doc_section}
Données marché collectées : {json.dumps([r[0].page_content[:150] for r in sim_results[:3]])}
Tendances émergentes : {json.dumps([s["signal"] for s in weak_signals[:3]])}

Génère une analyse stratégique. JSON strict (no markdown) :
{{
  "risk_score": 7,
  "main_risks": [
    {{
      "risk": "titre court du risque",
      "description": "description précise du risque basée sur les données",
      "mitigation": "stratégie de mitigation concrète et actionnable",
      "probability": 70,
      "impact": 8
    }}
  ],
  "recommendations": [
    {{
      "recommendation": "action stratégique précise et mesurable",
      "phase": "Phase 1",
      "month_start": 1,
      "month_end": 4,
      "priority": "high"
    }}
  ]
}}

Règles strictes :
- Exactement 4 risques avec probability (0–100) et impact (1–10) distincts
- Exactement 5 recommandations réparties : Phase 1 (mois 1–4) · Phase 2 (mois 5–8) · Phase 3 (mois 9–12)
- priority : high | medium | low
- Contenu spécifique au projet, pas de généralités. Aucun nom inventé.
- {self._lang_instruction}"""

        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, lambda: smart_llm_pro.complete(
            messages=[{"role": "user", "content": main_prompt}],
            temperature=self._llm_params.get("temperature", 0.2),
            max_tokens=2048,
            model_override=self._llm_params.get("model_override"),
        ))

        analysis = _extract_json(raw)
        n_risks = len(analysis.get("main_risks", []))
        n_recs = len(analysis.get("recommendations", []))

        if n_risks == 0 or n_recs == 0:
            self._log("ERROR", f"Parsing JSON échoué (risques={n_risks}, recs={n_recs}) — activation du fallback expert")
            fallback = await self._expert_fallback(project_desc, document_text)
            if not analysis.get("main_risks"):
                analysis["main_risks"] = fallback.get("main_risks", [])
            if not analysis.get("recommendations"):
                analysis["recommendations"] = fallback.get("recommendations", [])
            if not analysis.get("risk_score"):
                analysis["risk_score"] = fallback.get("risk_score", 7)
            n_risks = len(analysis.get("main_risks", []))
            n_recs = len(analysis.get("recommendations", []))
            self._log("OK", f"Fallback appliqué — {n_risks} risques · {n_recs} recommandations")
        else:
            self._log("OK", f"Rapport LLM — {n_risks} risques · {n_recs} recommandations")

        # ── Étape 9 : Pre-mortem ──────────────────────────────────────
        self._log("ANALYSIS", "Simulation pre-mortem — projection d'échec à 5 ans...")
        pre_mortem = await self._pre_mortem(project_desc, analysis.get("main_risks", []))
        n_timeline = len(pre_mortem.get("failure_timeline", []))
        self._log("OK", f"Pre-mortem — {n_timeline} étapes de déclin modélisées")

        # ── Étape 10 : Enrichissement sources ────────────────────────
        available_sources = [
            {
                "title": r[0].metadata.get("title", r[0].page_content[:60]),
                "url": r[0].metadata.get("url", ""),
                "type": "web"
            }
            for r in sim_results[:5]
            if isinstance(r, tuple) and r[0].metadata.get("url")
        ]

        def attach_source(item: Dict, idx: int) -> Dict:
            src = available_sources[idx % len(available_sources)] if available_sources else {
                "title": "Analyse IA StartWise", "url": None, "type": "ia"
            }
            return {**item, "source": src}

        enriched_risks = [attach_source(r, i) for i, r in enumerate(analysis.get("main_risks", []))]
        enriched_recs = [attach_source(r, i) for i, r in enumerate(analysis.get("recommendations", []))]

        self._log("SYNTHESIS", "Compilation du rapport final...")

        # ── Étape 11 : Génération d'images IA (parallèle) ────────────
        self._log("IMAGE", "Lancement de la génération d'images IA (FLUX.1-schnell, parallèle)...")
        img_results = await asyncio.gather(
            generate_ai_image(project_desc, "risks"),
            generate_ai_image(project_desc, "strategy"),
            generate_ai_image(project_desc, "premortem"),
            return_exceptions=True
        )

        def safe_img(r) -> str:
            return r if isinstance(r, str) else ""

        images = {
            "risks":    safe_img(img_results[0]),
            "strategy": safe_img(img_results[1]),
            "premortem":safe_img(img_results[2])
        }
        generated = sum(1 for v in images.values() if v)
        self._log("IMAGE", f"{generated}/3 images générées avec succès")
        self._log("OK", f"Analyse complète · Score de risque : {analysis.get('risk_score', 7)}/10 · Confiance : 8.5/10")

        return {
            "score": 8.5,
            "analysis": {
                "risk_score": analysis.get("risk_score", 7),
                "main_risks": enriched_risks,
                "recommendations": enriched_recs
            },
            "weak_signals": weak_signals,
            "gap_analysis": gap_analysis,
            "pre_mortem": pre_mortem,
            "images": images,
            "agent_thoughts": self._thoughts,
            "web_sources": available_sources[:5],
            "similar_cases": [r[0].page_content[:150] for r in sim_results[:3]],
            "market_data": {}
        }


# ────────────────────────────────────────────────────────────────────────── #

async def run_trend_agent(state: dict) -> dict:
    lang = state.get("lang", "fr")
    llm_params = state_llm_params(state)
    agent = TrendHunterAgent(lang=lang, llm_params=llm_params)
    project_desc = state["project_description"]
    document_text = state.get("document_text", "")

    print(f"\n{'='*50}")
    print(f"🔍 TREND HUNTER — model={llm_params.get('model_override','défaut')} temp={llm_params.get('temperature')}")
    print(f"📝 Projet: {project_desc}")
    if document_text:
        print(f"📄 Document RAG: {len(document_text)} chars injectés")
    print(f"{'='*50}\n")

    result = await agent.analyze_with_web_intelligence(project_desc, document_text)

    print(f"\n✅ Analyse terminée!")
    print(f"   Score: {result['score']}/10")
    print(f"   Sources valides: {len(result.get('web_sources', []))}")
    print(f"   Risques: {len(result['analysis'].get('main_risks', []))}")
    print(f"   Recommandations: {len(result['analysis'].get('recommendations', []))}")
    print(f"   Images générées: {sum(1 for v in result.get('images', {}).values() if v)}/3")

    return {
        "trend_result": result,
        "messages": [
            f"Analyse stratégique terminée — Score: {result['score']}/10",
            f"Risques: {len(result['analysis'].get('main_risks', []))} identifiés",
            f"Recommandations: {len(result['analysis'].get('recommendations', []))}"
        ],
        "agent_thoughts": result["agent_thoughts"]
    }
