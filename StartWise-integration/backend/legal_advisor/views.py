"""
Django async views — port exact de chat_ui.py (FastAPI → Django).
Toutes les fonctionnalités préservées : ChromaDB RAG, session memory,
startup card, audit déterministe, TTS-ready responses.
"""
import re
import json
import time
import asyncio
from difflib import SequenceMatcher

import httpx
import structlog
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from openai import AsyncOpenAI
try:
    from tavily import AsyncTavilyClient
    _TAVILY_OK = True
except ImportError:
    AsyncTavilyClient = None  # type: ignore
    _TAVILY_OK = False

from .state import collection, embedding_service

log = structlog.get_logger("api_django")

# ── Prompt système ────────────────────────────────────────────────────────────
STRICT_SYSTEM = """Tu es StartWise AI, conseiller juridique spécialisé en droit tunisien des affaires et en écosystème startup.

RÈGLE ABSOLUE : Tu utilises UNIQUEMENT les informations des sources fournies.
Si une information précise manque, utilise ce que tu as pour donner une réponse utile et partielle — ne commence jamais par "je suis désolé" ou "je n'ai pas trouvé".
Langue : réponds dans la langue de la question.

STYLE DE RÉPONSE :
Écris comme un conseiller qui parle à son client — naturel, professionnel, humain.
Pas de listes à puces mécaniques. Utilise des paragraphes courts et fluides.
Tu peux utiliser **gras** pour les termes clés, chiffres, dates importantes.
Maximum 220 mots. Pas d'introduction générique, va droit au sujet.

STRUCTURE SELON LE TYPE DE QUESTION :

Si question sur une startup :
→ Commence par présenter la startup en 2-3 phrases naturelles (ce qu'elle fait, quand créée, par qui).
→ Ensuite mentionne le label Startup Act et ce que ça implique concrètement.
→ Termine par 1-2 points de conseil juridique pertinents (protection IP, obligations légales, avantages fiscaux…).

Si question juridique / procédurale :
→ Réponds directement à la question en expliquant la procédure ou la règle.
→ Cite les références légales entre parenthèses quand elles sont dans les sources.
→ Termine par une recommandation concrète et l'organisme compétent.

Si question fiscale / sociale :
→ Donne les chiffres et taux exacts depuis les sources.
→ Explique brièvement les obligations et délais.

Toujours terminer par : 📎 Source : [nom de la source]
Si décision engageante → recommander un avocat spécialisé.

SOURCES :
{context}"""

# ── Session memory ────────────────────────────────────────────────────────────
MAX_HISTORY = 20
_SESSION_TTL = 3600  # 1 hour — sessions auto-expire to prevent memory leak
_sessions: dict[str, list[dict]] = {}
_sessions_ts: dict[str, float] = {}


def _cleanup_sessions():
    now = time.time()
    expired = [sid for sid, ts in list(_sessions_ts.items()) if now - ts > _SESSION_TTL]
    for sid in expired:
        _sessions.pop(sid, None)
        _sessions_ts.pop(sid, None)


def get_history(session_id: str) -> list[dict]:
    _cleanup_sessions()
    return _sessions.get(session_id, [])


def append_history(session_id: str, role: str, content: str):
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})
    _sessions_ts[session_id] = time.time()
    if len(_sessions[session_id]) > MAX_HISTORY:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY:]


def clear_history(session_id: str):
    _sessions.pop(session_id, None)
    _sessions_ts.pop(session_id, None)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def embed_query(text: str) -> list[float]:
    return await embedding_service.embed_query(text)


# Domaines tunisiens fiables pour la recherche web
_TN_DOMAINS = [
    "legislation.tn", "investir.tn", "innorpi.nat.tn",
    "impots.finances.gov.tn", "cnss.nat.tn", "registre.tn",
    "apii.tn", "startup.gov.tn", "jort.jo.tn", "douane.gov.tn",
]

async def web_search_fallback(question: str, intents: set, entity: str) -> list[dict]:
    """Recherche web Tavily — activée uniquement si RAG insuffisant.
    Construit une requête ciblée selon l'intent détecté pour éviter des résultats génériques.
    """
    if not _TAVILY_OK:
        return []
    try:
        # Construire une requête précise selon le domaine
        if "trademark" in intents:
            q = f"INNORPI Tunisie dépôt marque procédure enregistrement {entity}".strip()
            domains = ["innorpi.nat.tn", "legislation.tn", "investir.tn"]
        elif "tax" in intents:
            keywords = re.sub(r"\b(comment|est-ce|que|quoi|quel|quelle|les|des|une|un)\b", "", question.lower()).strip()
            q = f"Tunisie fiscalité 2024 {keywords} CNSS TVA IRPP taux officiel"
            domains = ["impots.finances.gov.tn", "cnss.nat.tn", "legislation.tn"]
        elif "startup_act" in intents:
            q = f"Startup Act Tunisie décret-loi 2018-20 avantages label {entity}".strip()
            domains = ["startup.gov.tn", "investir.tn", "legislation.tn", "apii.tn"]
        elif "legal" in intents:
            keywords = re.sub(r"\b(comment|créer|faire|est-ce|que|quoi|quel|quelle)\b", "", question.lower()).strip()
            q = f"Tunisie création société SARL SUARL {keywords} RNE procédure capital"
            domains = ["registre.tn", "apii.tn", "legislation.tn", "investir.tn"]
        elif "license" in intents:
            q = f"licence open source {question} SaaS obligations compatibilité"
            domains = []  # pas de restriction — SPDX, GitHub, etc.
        elif "jurisprudence" in intents:
            q = f"jurisprudence tunisienne {question} tribunal décision"
            domains = ["legislation.tn", "jort.jo.tn"]
        else:
            q = f"{question} Tunisie droit des affaires startup loi"
            domains = _TN_DOMAINS

        client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
        response = await client.search(
            query=q,
            search_depth="advanced",
            max_results=3,
            **({"include_domains": domains} if domains else {}),
        )

        results = []
        for r in response.get("results", []):
            content = (r.get("content") or "").strip()
            if len(content) < 80:  # ignorer les résultats trop courts
                continue
            results.append({
                "content": content,
                "url": r.get("url", ""),
                "title": r.get("title", ""),
            })
        log.info("tavily_results", query=q, count=len(results))
        return results

    except Exception as e:
        log.error("tavily_error", exc=str(e))
        return []


# How many top results to send to the LLM
CONTEXT_LIMIT = 12

# Generic words that extract_named_entity can wrongly return as "named entities"
_ENTITY_BLACKLIST = {
    "tunisie", "tunis", "startup", "startups", "sarl", "suarl", "jort", "rne",
    "apii", "cnss", "tva", "spdx", "wipo", "innorpi", "entreprise", "societe",
    "société", "fondateur", "label", "acte", "loi", "décret", "code",
}


def _is_name_lookup(q: str) -> bool:
    """Return True when the user is asking specifically about a named entity."""
    low = q.lower()
    return any(k in low for k in [
        "existe", "disponible", "déjà utilisé", "deja utilisé", "enregistré",
        "vérifier", "verifier", "cherche", "trouver", "marque", "nom",
        "startup", "entreprise", "société", "connais", "c'est quoi",
        "c est quoi", "qui est", "parle de", "info sur", "information sur",
        "détail sur", "fiche", "présente", "labellisée", "fondée", "fondateur",
        "secteur", "description", "site web",
    ])


async def search_docs(query: str, top_k: int = 5) -> tuple[list[dict], str, set, str]:
    count = collection.count()
    if count == 0:
        return [], "", set(), ""

    def detect_intents(q: str) -> set[str]:
        low = q.lower()
        intents: set[str] = set()

        if any(k in low for k in [
            "marque", "innorpi", "déposer", "deposer", "nice", "nom commercial",
            "trademark", "propriété industrielle", "brevet", "logotype",
            "enregistrement marque", "dépôt marque",
        ]):
            intents.add("trademark")

        if any(k in low for k in [
            "cnss", "tva", "fiscal", "impot", "impôt", "is", "irpp",
            "cotisation", "taxe", "déclaration fiscale", "tfp", "foprolos",
        ]):
            intents.add("tax")

        if any(k in low for k in [
            "jurisprudence", "jugement", "arrêt", "arret", "tribunal", "cour",
            "décision judiciaire", "cassation",
        ]):
            intents.add("jurisprudence")

        if any(k in low for k in [
            "licence", "spdx", "agpl", "gpl", "mit", "apache-2.0", "open source",
            "licence logiciel", "bsd", "mozilla", "creative commons",
        ]):
            intents.add("license")

        if any(k in low for k in [
            "startup act", "label startup", "labellisation", "smart gov",
            "droit à l'échec", "congé entrepreneuriat", "avantages startup",
            "décret-loi 2018-20", "2018-20",
        ]):
            intents.add("startup_act")

        if any(k in low for k in [
            "sarl", "suarl", "forme juridique", "creation", "création", "societe",
            "société", "statuts", "rne", "immatriculation", "associé", "actionnaire",
            "capital social", "apii", "startup", "entreprendre", "capital minimum",
        ]):
            intents.add("legal")

        if any(k in low for k in [
            "fondateur", "fondé par", "fondée par", "créé par", "créée par",
            "fondateurs", "co-fondateur", "cofondateur", "founder",
        ]):
            intents.add("startup_founders")

        if any(k in low for k in [
            "année de création", "créé en", "créée en", "fondé en", "fondée en",
            "depuis", "année", "date de création", "quand", "en quelle année",
        ]) or re.search(r"\b(19|20)\d{2}\b", q):
            intents.add("startup_year")

        if any(k in low for k in [
            "secteur", "domaine", "industrie", "activité", "domaine d'activité",
            "spécialisé", "spécialisée", "spécialité", "type d'entreprise",
        ]):
            intents.add("startup_sector")

        if not intents:
            intents.add("general")
        return intents

    def extract_named_entity(q: str) -> str:
        m = re.search(r'["«‘’“”]([^"\'«»‘’“”]{2,80})["»‘’“”]', q)
        if m:
            return m.group(1).strip()

        m2 = re.search(r"«\s*([^»]{2,80})\s*»", q)
        if m2:
            return m2.group(1).strip()

        m3 = re.search(
            r"(?:marque|startup|société|societe|entreprise|nom(?:\s+commercial)?|label)\s+([A-Z][A-Za-z0-9\-]{1,40}(?:\s+[A-Z][A-Za-z0-9]{1,20})?)",
            q,
        )
        if m3:
            return m3.group(1).strip()

        FR_STOP = {
            "est", "une", "les", "des", "son", "pas", "que", "qui", "pour",
            "dans", "sur", "avec", "par", "mais", "non", "oui", "déjà",
            "existe", "quel", "quels", "comment", "peut", "elle", "il",
        }
        tokens = re.findall(r"[A-Z][A-Za-z0-9]{2,}", q)
        candidates = [t for t in tokens if t.lower() not in FR_STOP]
        if candidates:
            return candidates[0]

        all_toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{3,}", q)
        meaningful = [t for t in all_toks if t.lower() not in FR_STOP]
        return meaningful[-1] if meaningful else ""

    def extract_year_from_query(q: str) -> str:
        m = re.search(r"\b(19[89]\d|20[0-2]\d)\b", q)
        return m.group(1) if m else ""

    def keyword_boost(result: dict, entity: str, intents: set, year: str = "") -> float:
        content = (result.get("content") or "").lower()
        meta = result.get("meta") or {}
        source_type = (meta.get("source_type") or "").upper()
        boost = 0.0

        if entity and entity.lower() in content:
            boost += 0.35

        if "trademark" in intents:
            if source_type == "INNORPI":
                boost += 0.15
            if source_type in ("F6S", "F6S_LINK", "STARTUPS_DB"):
                boost += 0.10
            if any(k in content for k in ["dépôt", "depot", "innorpi", "classe nice", "marque"]):
                boost += 0.10
        if "startup_act" in intents:
            if source_type in ("STARTUP_ACT", "STARTUPS_DB", "DROIT_SOCIETES"):
                boost += 0.30
            if any(k in content for k in ["startup act", "label", "2018-20", "labellisé", "avantages"]):
                boost += 0.15
        if "startup_name" in intents or entity:
            if source_type == "STARTUPS_DB":
                boost += 0.25
            if source_type in ("F6S", "F6S_LINK", "DROIT_SOCIETES"):
                boost += 0.12
        if "legal" in intents:
            if source_type in ("RNE", "APII", "DROIT_SOCIETES", "STARTUP_ACT", "JORT", "STARTUPS_DB"):
                boost += 0.10
        if "tax" in intents:
            if any(k in content for k in ["cnss", "tva", "cotisation", "impôt", "fiscal"]):
                boost += 0.10

        if "startup_year" in intents:
            if source_type == "STARTUPS_DB":
                boost += 0.20
            if year and year in content:
                boost += 0.25
            if any(k in content for k in ["année de création", "creation_year", "fondé en", "créée en"]):
                boost += 0.08
        if "startup_founders" in intents:
            if source_type == "STARTUPS_DB":
                boost += 0.20
            if any(k in content for k in ["fondateurs", "fondateur", "founder", "co-fondateur"]):
                boost += 0.10
        if "startup_sector" in intents:
            if source_type == "STARTUPS_DB":
                boost += 0.20
            if any(k in content for k in ["secteur", "domaine", "industrie"]):
                boost += 0.08

        return min(boost, 0.65)

    intents = detect_intents(query)
    entity = extract_named_entity(query)
    year = extract_year_from_query(query)
    if entity:
        log.info("entity_detected", entity=entity, intents=list(intents))
    if year:
        log.info("year_detected", year=year)

    vector = await embed_query(query)

    query_plan: list[dict | None] = []

    if "trademark" in intents:
        query_plan.append({"domain": {"$eq": "MARQUES"}})
        query_plan.append({"source_type": {"$eq": "INNORPI"}})
        query_plan.append({"source_type": {"$eq": "STARTUPS_DB"}})
    if "startup_act" in intents:
        query_plan.append({"source_type": {"$eq": "STARTUP_ACT"}})
        query_plan.append({"source_type": {"$eq": "STARTUPS_DB"}})
        query_plan.append({"domain": {"$eq": "LEGAL"}})
    if entity:
        query_plan.append({"source_type": {"$eq": "STARTUPS_DB"}})
        query_plan.append({"domain": {"$eq": "ENTREPRISES"}})
    if "tax" in intents:
        query_plan.append({"domain": {"$eq": "FISCAL"}})
    if "jurisprudence" in intents:
        query_plan.append({"domain": {"$eq": "JURISPRUDENCE"}})
    if "license" in intents:
        query_plan.append({"source_type": {"$eq": "SPDX"}})
    if "legal" in intents:
        query_plan.append({"domain": {"$eq": "LEGAL"}})
        query_plan.append({"domain": {"$eq": "ENTREPRISES"}})
    if any(i in intents for i in ("startup_year", "startup_founders", "startup_sector")):
        query_plan.append({"source_type": {"$eq": "STARTUPS_DB"}})
        query_plan.append({"domain": {"$eq": "ENTREPRISES"}})

    query_plan.append(None)

    raw: list[dict] = []
    for where in query_plan:
        n = min(max(top_k, 10), count)
        kwargs: dict = dict(
            query_embeddings=[vector],
            n_results=n,
            include=["metadatas", "documents", "distances"],
        )
        if where:
            kwargs["where"] = where
        try:
            results = collection.query(**kwargs)
        except Exception:
            continue

        docs  = results.get("documents") or [[]]
        metas = results.get("metadatas") or [[]]
        dists = results.get("distances") or [[]]
        for i, doc in enumerate(docs[0] if docs else []):
            meta = metas[0][i] if (metas and metas[0]) else {}
            dist = dists[0][i] if (dists and dists[0]) else 1.0
            score = 1.0 - (dist / 2.0)
            raw.append({"content": doc, "meta": meta, "score": score})

    deduped: list[dict] = []
    seen: set = set()
    for r in raw:
        m = r.get("meta") or {}
        key = (
            m.get("source") or m.get("source_label") or "",
            r.get("content", "")[:200],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    for r in deduped:
        r["_final_score"] = min(r["score"] + keyword_boost(r, entity, intents, year), 1.0)

    deduped.sort(key=lambda x: x["_final_score"], reverse=True)

    return deduped[:20], entity, intents, year


# ── HTML (identique à chat_ui.py) ────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Agent Legal IA — Tunisie</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:sans-serif;background:#0f1117;color:#e2e8f0;display:flex;flex-direction:column;height:100vh}
header{background:#1a1d2e;padding:12px 20px;border-bottom:1px solid #2d3748;display:flex;align-items:center;gap:12px}
header h1{font-size:17px;font-weight:600}
header .sub{font-size:11px;color:#718096;margin-top:2px}
.badge{margin-left:auto;background:#742a2a;color:#fc8181;font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600}
#chat{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:14px}
.msg{max-width:820px;padding:12px 16px;border-radius:10px;font-size:14px;line-height:1.75;white-space:pre-wrap;word-break:break-word}
.user{background:#2a4365;align-self:flex-end;max-width:600px}
.bot{background:#1a1d2e;border:1px solid #2d3748;align-self:flex-start}
.error{background:#742a2a;border:1px solid #fc8181;align-self:flex-start;font-size:13px}
.thinking{color:#718096;font-style:italic;align-self:flex-start;padding:10px 16px}
.src{font-size:11px;color:#4a5568;margin-top:8px;border-top:1px solid #2d3748;padding-top:6px}
.bar{background:#1a1d2e;border-top:1px solid #2d3748;padding:12px 20px;display:flex;gap:10px}
textarea{flex:1;background:#2d3748;color:#e2e8f0;border:1px solid #4a5568;border-radius:8px;padding:10px;font-size:14px;font-family:sans-serif;resize:none;height:50px}
textarea:focus{outline:none;border-color:#63b3ed}
button{background:#2b6cb0;color:#fff;border:none;border-radius:8px;padding:0 18px;font-size:18px;cursor:pointer}
button:disabled{background:#4a5568;cursor:not-allowed}
#info{background:#1a1d2e;border-bottom:1px solid #2d3748;padding:6px 20px;font-size:11px;color:#718096}
</style>
</head>
<body>
<header>
  <div>
    <h1>⚖️ Agent Légal IA — Tunisie</h1>
    <div class="sub">Droit tunisien des affaires · ar / fr / en</div>
  </div>
  <div class="badge">🔒 Strict — sources scrappées uniquement</div>
</header>
<div id="info">Chargement…</div>
<div id="chat">
  <div class="msg bot">Bonjour. Posez votre question juridique. Je réponds uniquement depuis les données scrappées (JORT, DGI, CNSS, INNORPI, SPDX).</div>
</div>
<div class="bar">
  <textarea id="q" placeholder="Votre question juridique…" onkeydown="onKey(event)"></textarea>
  <button id="btn" onclick="send()">↑</button>
</div>
<script>
const chat=document.getElementById('chat'),q=document.getElementById('q'),btn=document.getElementById('btn');
function onKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function fmt(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/\n/g,'<br>');}
function add(html,cls,raw=false){const d=document.createElement('div');d.className='msg '+cls;if(raw)d.innerHTML=html;else d.textContent=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;return d;}
async function updateInfo(){try{const r=await fetch('/stats');const d=await r.json();document.getElementById('info').textContent=d.chunks+' chunks indexés dans ChromaDB';}catch(e){}}
async function send(){
  const text=q.value.trim();if(!text)return;
  add(text,'user');q.value='';btn.disabled=true;
  const th=add('Recherche dans les sources scrappées…','thinking');
  try{
    const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text})});
    const d=await r.json();th.remove();
    if(d.error){add('Erreur : '+d.detail,'error');}
    else{let html=fmt(d.answer);if(d.sources&&d.sources.length){html+='<div class="src">📎 '+d.sources.join(' · ')+'</div>';}add(html,'bot',true);}
  }catch(e){th.remove();add('Erreur réseau : '+e.message,'error');}
  finally{btn.disabled=false;q.focus();}
}
updateInfo();
</script>
</body>
</html>"""


# ── Views ─────────────────────────────────────────────────────────────────────

async def index(request):
    return HttpResponse(HTML, content_type="text/html; charset=utf-8")


async def stats(request):
    return JsonResponse({"chunks": collection.count()})


async def favicon(request):
    return HttpResponse(status=204)


@csrf_exempt
async def session_clear(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}
    sid = body.get("session_id", "")
    if sid:
        clear_history(sid)
    return JsonResponse({"ok": True})


@csrf_exempt
async def ask(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": True, "detail": "JSON invalide."})

    question        = (body.get("question") or "").strip()
    session_id      = body.get("session_id", "")
    startup_context = (body.get("startup_context") or "").strip()

    if not question:
        return JsonResponse({"error": True, "detail": "Question vide."})

    results, entity, _intents, _year = await search_docs(question)

    # Neutralise generic words wrongly extracted as named entities
    if entity and entity.lower() in _ENTITY_BLACKLIST:
        entity = ""

    # ── Fallback Tavily si RAG insuffisant ────────────────────────────────────
    good_rag = [r for r in results if r.get("score", 0) >= 0.45]
    entity_found = bool(entity) and any(
        entity.lower() in (r.get("content") or "").lower()
        for r in good_rag
    )
    need_web = len(good_rag) < 2 or (entity and not entity_found)
    web_results: list[dict] = []
    if need_web:
        log.info("tavily_triggered", good_count=len(good_rag), entity=entity, entity_found=entity_found)
        web_results = await web_search_fallback(question, _intents, entity)

    # ── Court-circuit : entité introuvable nulle part → réponse fixe sans LLM ──
    web_entity_found = bool(entity) and any(
        entity.lower() in (w.get("content") or "").lower()
        for w in web_results
    )
    if entity and _is_name_lookup(question) and not entity_found and not web_entity_found:
        return JsonResponse({
            "error": False,
            "answer": (
                f"Je n'ai trouvé aucune information sur **{entity}** "
                f"dans mes sources (base startups tunisiennes, INNORPI, JORT, WIPO) "
                f"ni via la recherche web. "
                f"Cela ne signifie pas que ce nom est libre — "
                f"pour une vérification officielle, consultez directement "
                f"**[RNE](https://www.registre-entreprises.tn)** pour les sociétés "
                f"et **[INNORPI](https://www.innorpi.nat.tn)** pour les marques."
            ),
            "sources": [],
            "web_used": bool(web_results),
        })

    # ── Helper functions (scoped inside the view, same as chat_ui.py) ─────────

    def is_trademark_query(q: str) -> bool:
        low = q.lower()
        return any(k in low for k in ["marque", "innorpi", "déposer", "deposer", "nice", "nom commercial"])

    def is_multi_domain_check(q: str) -> bool:
        low = q.lower()
        keys = [
            ["marque", "innorpi"],
            ["cnss", "tva", "fiscal"],
            ["licence", "spdx", "agpl", "gpl", "mit"],
            ["jurisprudence", "jugement", "tribunal", "cour"],
            ["sarl", "sa", "statuts", "forme juridique", "creation", "création"],
        ]
        hits = sum(1 for g in keys if any(k in low for k in g))
        return hits >= 2

    def extract_candidate_mark(q: str) -> str:
        m = re.search(r"[\"']([^\"']{2,80})[\"']", q)
        if m:
            return m.group(1).strip()
        m2 = re.search(r"marque\s+([A-Za-z0-9\-]{3,80})", q, re.I)
        if m2:
            return m2.group(1).strip()
        toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{2,}", q)
        return toks[-1].strip() if toks else ""

    def extract_mark_names_from_results(items: list[dict]) -> list[str]:
        names: list[str] = []
        for it in items:
            content = it.get("content", "") or ""
            meta    = it.get("meta") or {}
            label   = meta.get("source_label") or ""
            m = re.search(r"Marque\s*:\s*(.+)", content, re.I)
            if m:
                n = m.group(1).split("\n", 1)[0].strip()
                if n:
                    names.append(n)
            m2 = re.search(r"Marque\s*'([^']+)'", label, re.I)
            if m2:
                n2 = m2.group(1).strip()
                if n2:
                    names.append(n2)
        out, seen = [], set()
        for n in names:
            k = n.lower()
            if k not in seen:
                seen.add(k)
                out.append(n)
        return out

    def has_close_match(candidate: str, names: list[str]) -> bool:
        if not candidate:
            return bool(names)
        c = candidate.lower()
        for n in names:
            nl = n.lower()
            if c in nl or nl in c:
                return True
            if SequenceMatcher(None, c, nl).ratio() >= 0.72:
                return True
        return False

    if is_trademark_query(question) and not is_multi_domain_check(question):
        has_wipo_f6s = any((r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"] for r in results)
        has_innorpi  = any((r.get("meta") or {}).get("source_type") == "INNORPI" for r in results)

        procedural_query = any(k in question.lower() for k in [
            "comment", "procedure", "procédure", "déposer", "deposer",
            "protection", "protéger", "proteger", "enregistrer", "dépôt", "loi", "réglementation",
        ])

        if not procedural_query and not has_wipo_f6s:
            return JsonResponse({
                "error": False,
                "answer": (
                    "Je n'ai pas trouvé de source WIPO ou F6S pertinente pour vérifier cette marque spécifique. "
                    "Relancez l'ingestion WIPO/F6S et reformulez avec le nom exact entre guillemets."
                ),
                "sources": [],
            })
        elif procedural_query and not has_innorpi:
            return JsonResponse({
                "error": False,
                "answer": (
                    "Je n'ai pas trouvé de source INNORPI pertinente pour les procédures de dépôt de marque. "
                    "Relancez l'ingestion INNORPI pour obtenir les informations procédurales."
                ),
                "sources": [],
            })

    def source_label(item: dict) -> str:
        m = item.get("meta") or {}
        return m.get("source_label") or m.get("source") or m.get("filename") or "source"

    def deterministic_audit(q: str, items: list[dict]) -> str:
        legal_form_re = re.compile(r"\b(sarl|suarl|s\.a\.|\bsa\b|forme\s+juridique|code\s+des\s+soci[eé]t[eé]s)\b", re.I)
        low = q.lower()
        has_legal_need     = any(k in low for k in ["forme juridique", "sarl", "sa", "statuts", "creation", "création", "societe", "société"])
        has_trademark_need = any(k in low for k in ["marque", "innorpi", "deposer", "déposer", "nice"])
        has_license_need   = any(k in low for k in ["licence", "spdx", "agpl", "gpl", "mit", "apache-2.0"])
        has_tax_need       = any(k in low for k in ["cnss", "tva", "fiscal", "impot", "impôt", "irpp", "is"])
        has_case_need      = any(k in low for k in ["jurisprudence", "jugement", "arrêt", "arret", "tribunal", "cour"])

        def pick(pred):
            return [r for r in items if pred(r)]

        def text_of(r: dict) -> str:
            return (r.get("content") or "").lower()

        legal_hits     = pick(lambda r: ((r.get("meta") or {}).get("domain") == "LEGAL") and bool(legal_form_re.search(text_of(r))))
        trademark_hits = pick(lambda r: ((r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"]) or ((r.get("meta") or {}).get("source_type") == "INNORPI"))
        license_hits   = pick(lambda r: ((r.get("meta") or {}).get("source_type") == "SPDX"))
        tax_hits       = pick(lambda r: ((r.get("meta") or {}).get("domain") == "FISCAL") and any(k in text_of(r) for k in ["cnss", "tva", "taxe", "fiscal", "impot", "impôt"]))
        case_hits      = pick(lambda r: ((r.get("meta") or {}).get("domain") == "JURISPRUDENCE") and any(k in text_of(r) for k in ["jugement", "arrêt", "arret", "tribunal", "cour", "affaire"]))

        candidate  = extract_candidate_mark(q)
        names      = extract_mark_names_from_results(trademark_hits)
        procedural = any(k in q.lower() for k in ["comment", "procedure", "procédure", "déposer", "deposer", "protection", "protéger", "proteger", "enregistrer", "dépôt"])

        rows = []
        if has_legal_need:
            state = "VÉRIFIÉ" if legal_hits else "INSUFFISANT"
            ev    = "; ".join(source_label(x) for x in legal_hits[:3]) or "Aucune source LEGAL pertinente"
            rows.append(("Forme juridique / création", state, ev))

        if has_trademark_need:
            wipo_f6s = [r for r in trademark_hits if (r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"]]
            innorpi  = [r for r in trademark_hits if (r.get("meta") or {}).get("source_type") == "INNORPI"]
            if wipo_f6s or innorpi:
                state   = "VÉRIFIÉ"
                sources = []
                if wipo_f6s: sources.append("WIPO/F6S (vérification marques)")
                if innorpi:  sources.append("INNORPI (procédures/lois)")
                ev = "; ".join(sources)
            else:
                state = "DONNÉES PARTIELLES"
                ev    = "Certaines sources manquantes - compléter l'ingestion WIPO/F6S et INNORPI"
            rows.append(("Marques (vérification + procédures)", state, ev))

        if has_license_need:
            state = "VÉRIFIÉ" if license_hits else "INSUFFISANT"
            ev    = "; ".join(source_label(x) for x in license_hits[:3]) or "Aucune source SPDX pertinente"
            rows.append(("Licences open source", state, ev))

        if has_tax_need:
            state = "VÉRIFIÉ" if tax_hits else "INSUFFISANT"
            ev    = "; ".join(source_label(x) for x in tax_hits[:3]) or "Aucune source fiscale/CNSS/TVA pertinente"
            rows.append(("CNSS / TVA / Fiscal", state, ev))

        if has_case_need:
            state = "VÉRIFIÉ" if case_hits else "INSUFFISANT"
            ev    = "; ".join(source_label(x) for x in case_hits[:3]) or "Aucune source de jurisprudence pertinente"
            rows.append(("Jurisprudence", state, ev))

        if not rows:
            return ""

        verified    = sum(1 for _, s, _ in rows if s == "VÉRIFIÉ")
        insufficient = sum(1 for _, s, _ in rows if s != "VÉRIFIÉ")
        lines = ["**Vérifications factuelles (mode audit déterministe)**"]
        for topic, state, ev in rows:
            lines.append(f"- {topic} : {state} | Preuve: {ev}")
        lines.append("\n**Synthèse**")
        lines.append(f"- Domaines vérifiés: {verified}")
        lines.append(f"- Domaines insuffisants: {insufficient}")
        lines.append("\n**Actions**")
        lines.append("- Compléter l'ingestion des domaines insuffisants, puis relancer la vérification.")
        lines.append("- Pour un dépôt de marque, effectuer une vérification officielle INNORPI avant décision finale.")
        lines.append("- Validation avocat recommandée pour toute décision engageante (statuts, pactes, contentieux).")
        return "\n".join(lines)

    # ── Startup card direct lookup ─────────────────────────────────────────────
    def build_startup_card(ent: str, items: list[dict]) -> str | None:
        if not ent:
            return None
        for r in items:
            meta = r.get("meta") or {}
            if (meta.get("source_type") or "").upper() != "STARTUPS_DB":
                continue
            content = r.get("content") or ""
            if ent.lower() not in content.lower():
                continue
            NEXT = r"(?=\s+(?:Startup|Secteur|Année de création|Label Startup Act|Fondateurs|Site web|Description|Région|Services|Source)\s*:|\Z)"

            def field(label: str) -> str:
                m = re.search(rf"{re.escape(label)}\s*:\s*(.+?){NEXT}", content, re.I | re.S)
                return m.group(1).strip() if m else "non renseigné"

            name     = field("Startup")
            sector   = field("Secteur")
            year_f   = field("Année de création")
            label_d  = field("Label Startup Act")
            founders = field("Fondateurs")
            website  = field("Site web")
            desc_raw = field("Description")
            desc     = desc_raw[:220] if desc_raw != "non renseigné" else "non renseigné"

            lines = [f"**Startup :** {name}"]
            if sector   != "non renseigné": lines.append(f"**Secteur :** {sector}")
            if year_f   != "non renseigné": lines.append(f"**Année de création :** {year_f}")
            if label_d  != "non renseigné": lines.append(f"**Label Startup Act :** {label_d}")
            if founders != "non renseigné": lines.append(f"**Fondateurs :** {founders}")
            if website  != "non renseigné": lines.append(f"**Site web :** {website}")
            if desc     != "non renseigné": lines.append(f"**Description :** {desc}")
            lines.append("\n📎 Source : Base Startup Tunisia (STARTUPS_DB)")
            return "\n".join(lines)
        return None

    def is_startup_lookup(q: str) -> bool:
        low = q.lower()
        lookup_triggers = [
            "startup", "entreprise", "société", "c'est quoi", "c est quoi",
            "info", "information", "détail", "fiche", "présente", "connais",
            "existe", "labellisée", "label", "créée", "fondée", "fondateur",
            "secteur", "site web", "description",
        ]
        has_trigger = any(t in low for t in lookup_triggers)
        is_short    = len(q.split()) <= 6
        return bool(entity) and (has_trigger or is_short)

    startup_card_prefix = ""
    if is_startup_lookup(question):
        card = build_startup_card(entity, results)
        if card:
            startup_card_prefix = f"FICHE STARTUP TROUVÉE DANS LA BASE :\n{card}\n\n"

    audit_prefix = ""
    if is_multi_domain_check(question):
        audit_prefix = deterministic_audit(question, results)

    # ── Build context ──────────────────────────────────────────────────────────
    context_results: list[dict] = results[:CONTEXT_LIMIT]  # defined early for rag_sources below
    if not results and not web_results:
        context = "AUCUN DOCUMENT CHARGÉ"
    else:
        parts = []
        for i, r in enumerate(context_results, 1):
            meta  = r.get("meta") or {}
            label = meta.get("source_label") or meta.get("source") or meta.get("filename") or "document"
            parts.append(f"[SOURCE {i} — {label} — pertinence {r['score']:.2f}]\n{r['content']}")

        # Ajouter les résultats web Tavily à la suite des sources RAG
        offset = len(context_results) + 1
        for j, w in enumerate(web_results, offset):
            title = w.get("title") or w.get("url") or "Web"
            parts.append(f"[SOURCE {j} — WEB : {title}]\n{w['content']}")

        context = "\n\n---\n\n".join(parts)


    if startup_card_prefix:
        context = startup_card_prefix + context

    # Injecte le projet client comme source RAG prioritaire (SOURCE 0)
    # → le LLM peut l'utiliser librement car c'est dans les "sources fournies"
    if startup_context:
        client_source = (
            f"[SOURCE 0 — PROJET CLIENT (idéation) — priorité maximale]\n"
            f"{startup_context[:1500]}"
        )
        context = client_source + "\n\n---\n\n" + context

    system = STRICT_SYSTEM.format(context=context)

    # ── LLM call ──────────────────────────────────────────────────────────────
    try:
        llm = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            http_client=httpx.AsyncClient(verify=False, timeout=90.0),
        )
        history  = get_history(session_id) if session_id else []
        messages = [{"role": "system", "content": system}]
        messages.extend(history)
        messages.append({"role": "user", "content": question})

        resp   = await llm.chat.completions.create(
            model=settings.LLM_MODEL,
            max_tokens=600,
            temperature=0.1,
            messages=messages,
        )
        answer = resp.choices[0].message.content

        if audit_prefix:
            answer = answer.rstrip() + "\n\n---\n\n" + audit_prefix

        if session_id:
            append_history(session_id, "user", question)
            append_history(session_id, "assistant", answer)

        rag_sources = list({
            (r.get("meta") or {}).get("source_label")
            or (r.get("meta") or {}).get("source")
            or (r.get("meta") or {}).get("filename")
            or "?"
            for r in context_results
        } - {None, "?"})
        web_sources = [w.get("url") or w.get("title") or "Web" for w in web_results]
        sources = rag_sources + web_sources
        return JsonResponse({
            "error": False,
            "answer": answer,
            "sources": sources,
            "web_used": bool(web_results),
        })

    except Exception as e:
        log.error("llm_error", exc=str(e))
        return JsonResponse({"error": True, "detail": str(e)}, status=500)


async def domains(request):
    try:
        counts = {}
        for domain in ["LEGAL", "FISCAL", "MARQUES", "ENTREPRISES", "JURISPRUDENCE"]:
            counts[domain.lower()] = len(collection.get(where={"domain": {"$eq": domain}})["ids"])
        return JsonResponse({"domains": counts, "total": collection.count()})
    except Exception:
        return JsonResponse({"domains": {}, "total": collection.count()})
