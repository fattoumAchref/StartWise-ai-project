"""
Interface Agent Legal IA — Tunisie
- Upload PDF → indexé dans ChromaDB
- Questions → réponses UNIQUEMENT depuis les documents chargés
- Le LLM ne répond jamais depuis sa propre connaissance
Lance : python chat_ui.py
Ouvre  : http://localhost:5050
"""

import uuid
import asyncio
import re
from difflib import SequenceMatcher
import httpx
import chromadb
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

log = structlog.get_logger("chat_ui")

# Charger les variables d'environnement
load_dotenv()

# ── Config LLM ────────────────────────────────────────────────────────────────
LLM_API_KEY  = os.getenv("LLM_API_KEY", "sk-af700b35e54c4b98a460eb42d2f6064c")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://tokenfactory.esprit.tn/api")
LLM_MODEL    = os.getenv("LLM_MODEL", "hosted_vllm/Llama-3.1-70B-Instruct")
CHROMA_PATH  = os.getenv("CHROMA_PATH", "./chroma_db")

STRICT_SYSTEM = """Tu es l'Agent Légal IA, conseiller juridique expert en droit tunisien des affaires.

RÈGLE ABSOLUE :
Tu ne peux répondre QUE sur la base des SOURCES FOURNIES ci-dessous.
Si les sources ne contiennent pas l'information nécessaire, explique clairement pourquoi et oriente l'utilisateur.
Tu n'as PAS le droit d'utiliser tes connaissances internes.

DOMAINES COUVERTS PAR LA BASE DE CONNAISSANCES :
• MARQUES / PI : INNORPI (procédures, tarifs, délais, classes Nice, textes légaux), WIPO Lex (loi tunisienne PI)
• STARTUP ACT : startup.gov.tn (procédure, critères, avantages, liste startups labellisées, FAQ, formulaires, textes juridiques)
• CRÉATION D'ENTREPRISE : RNE (immatriculation), APII (guide création), formes juridiques SARL/SA/SUARL/GIE
• FISCAL / CNSS : DGI, Jibaya, Douane, cotisations sociales
• LICENCES OPEN SOURCE : SPDX (MIT, GPL, Apache, AGPL…)
• TEXTES LÉGAUX : JORT (Journal Officiel), legislation-securite.tn

LOGIQUE DE RÉPONSE :

Pour les MARQUES :
- La base de données INNORPI (registre des marques déposées) est sur un réseau INTERNE non public.
- La base indexée contient les PROCÉDURES, TARIFS, DÉLAIS, FORMULAIRES et TEXTES LÉGAUX d'INNORPI.
- Pour vérifier si un nom est déjà déposé comme marque : recommande de consulter directement innorpi.tn ou de contacter l'INNORPI.
- Pour les questions procédurales (comment déposer, combien ça coûte, quel délai) : réponds depuis les sources INNORPI disponibles.

Pour le STARTUP ACT :
- Le Startup Act (Décret-loi 2018-20 du 11 avril 2018) est la loi instituant le label startup en Tunisie.
- La base contient la procédure complète, les critères d'éligibilité, les avantages fiscaux et sociaux, la liste des startups labellisées.
- Explique les étapes, les avantages (exonérations fiscales, avantages CNSS, droit à l'échec, congé entrepreneuriat) depuis les sources.

Pour les NOMS DE STARTUPS :
- La base contient des noms de startups depuis deux sources : F6S (annuaire global) et startup.gov.tn (liste des labellisées Startup Act).
- Si un nom apparaît dans la base F6S ou Startup Act, tu peux confirmer son existence.
- Si un nom n'est PAS trouvé dans la base, précise que la base n'est pas exhaustive et recommande de vérifier directement sur f6s.com, startup.gov.tn, ou au RNE.
- Ne prétends jamais qu'une startup n'existe pas si elle n'est pas dans la base — la base n'est pas un registre officiel complet.

SOURCES DISPONIBLES :
{context}

Réponds directement à la question posée. Structure ta réponse avec des sections claires si nécessaire.
Cite toujours les sources utilisées. Sois précis et concis."""

# ── Chargement du service d'embeddings local ─────────────────────────────────
print("Initialisation du service d'embeddings local...")
from embeddings import embedding_service
print("Service d'embeddings prêt.")

print("Initialisation ChromaDB...")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"},
)
print("ChromaDB prêt.")

app = FastAPI(title="Agent Légal IA — API", version="1.0.0")

# CORS pour Next.js frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def embed_query(text: str) -> list[float]:
    """Génère un embedding pour une requête en utilisant le service local."""
    return await embedding_service.embed_query(text)

def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Découpe un texte en chunks avec chevauchement."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        if len(chunk) > 50:
            chunks.append(chunk)
        i += size - overlap
    return chunks

async def search_docs(query: str, top_k: int = 5) -> list[dict]:
    """Recherche vectorielle dans ChromaDB avec ré-ordonnancement par pertinence lexicale."""
    count = collection.count()
    if count == 0:
        return []

    def detect_intents(q: str) -> set[str]:
        low = q.lower()
        intents: set[str] = set()

        # Marques / propriété industrielle
        if any(k in low for k in [
            "marque", "innorpi", "déposer", "deposer", "nice", "nom commercial",
            "trademark", "propriété industrielle", "brevet", "logotype",
            "enregistrement marque", "dépôt marque",
        ]):
            intents.add("trademark")

        # Fiscal / CNSS
        if any(k in low for k in [
            "cnss", "tva", "fiscal", "impot", "impôt", "is", "irpp",
            "cotisation", "taxe", "déclaration fiscale", "tfp", "foprolos",
        ]):
            intents.add("tax")

        # Jurisprudence
        if any(k in low for k in [
            "jurisprudence", "jugement", "arrêt", "arret", "tribunal", "cour",
            "décision judiciaire", "cassation",
        ]):
            intents.add("jurisprudence")

        # Licences open source
        if any(k in low for k in [
            "licence", "spdx", "agpl", "gpl", "mit", "apache-2.0", "open source",
            "licence logiciel", "bsd", "mozilla", "creative commons",
        ]):
            intents.add("license")

        # Startup Act spécifiquement
        if any(k in low for k in [
            "startup act", "label startup", "labellisation", "smart gov",
            "droit à l'échec", "congé entrepreneuriat", "avantages startup",
            "décret-loi 2018-20", "2018-20",
        ]):
            intents.add("startup_act")

        # Création d'entreprise / droit des sociétés
        if any(k in low for k in [
            "sarl", "suarl", "forme juridique", "creation", "création", "societe",
            "société", "statuts", "rne", "immatriculation", "associé", "actionnaire",
            "capital social", "apii", "startup", "entreprendre", "capital minimum",
        ]):
            intents.add("legal")

        if not intents:
            intents.add("general")
        return intents

    def extract_named_entity(q: str) -> str:
        """
        Extrait le nom d'une startup ou marque mentionné dans la query.
        Priorité : texte entre guillemets, puis nom propre en majuscule,
        puis tokens CamelCase, puis dernier token alphanum long.
        """
        # 1. Entre guillemets (doubles ou simples)
        m = re.search(r'["\u00ab\u2018\u2019\u201c\u201d]([^"\'«»\u2018\u2019\u201c\u201d]{2,80})["\u00bb\u2018\u2019\u201c\u201d]', q)
        if m:
            return m.group(1).strip()

        # 2. Guillemets typographiques français « »
        m2 = re.search(r"«\s*([^»]{2,80})\s*»", q)
        if m2:
            return m2.group(1).strip()

        # 3. Après "marque", "startup", "société", "entreprise", "nom"
        m3 = re.search(
            r"(?:marque|startup|société|societe|entreprise|nom(?:\s+commercial)?|label)\s+([A-Z][A-Za-z0-9\-]{1,40}(?:\s+[A-Z][A-Za-z0-9]{1,20})?)",
            q,
        )
        if m3:
            return m3.group(1).strip()

        # 4. Tokens CamelCase ou TOUT-EN-MAJUSCULES (≥3 chars) qui ne sont pas des mots FR courants
        FR_STOP = {
            "est", "une", "les", "des", "son", "pas", "que", "qui", "pour",
            "dans", "sur", "avec", "par", "mais", "non", "oui", "déjà",
            "existe", "quel", "quels", "comment", "peut", "elle", "il",
        }
        tokens = re.findall(r"[A-Z][A-Za-z0-9]{2,}", q)
        candidates = [t for t in tokens if t.lower() not in FR_STOP]
        if candidates:
            return candidates[0]

        # 5. Dernier token alphanum long (≥4 chars)
        all_toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{3,}", q)
        meaningful = [t for t in all_toks if t.lower() not in FR_STOP]
        return meaningful[-1] if meaningful else ""

    def keyword_boost(result: dict, entity: str, intents: set) -> float:
        """
        Score bonus [0..1] basé sur la présence de mots-clés dans le contenu.
        Permet un ré-ordonnancement après la recherche vectorielle.
        """
        content = (result.get("content") or "").lower()
        meta = result.get("meta") or {}
        source_type = (meta.get("source_type") or "").upper()
        boost = 0.0

        # Présence du nom de l'entité dans le contenu
        if entity and entity.lower() in content:
            boost += 0.35

        # Bonus par type de source selon l'intent
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
            # Boost fort quand l'entité est directement un nom de startup connu
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

        return min(boost, 0.60)  # plafond pour ne pas écraser le score vectoriel

    intents = detect_intents(query)
    entity = extract_named_entity(query)
    if entity:
        log.info("entity_detected", entity=entity, intents=list(intents))

    vector = await embed_query(query)

    # ── Plan de requêtes ChromaDB ──────────────────────────────────────────────
    # Chaque intent génère une requête filtrée sur le bon domaine/source_type.
    # On lance aussi toujours une requête sans filtre pour ne rien rater.
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
        # Toujours chercher dans la base startups quand on a un nom d'entité
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

    # Toujours une passe sans filtre (capture les chunks multi-domaines)
    query_plan.append(None)

    # ── Exécution des requêtes ─────────────────────────────────────────────────
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

    # ── Déduplication ─────────────────────────────────────────────────────────
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

    # ── Ré-ordonnancement lexical ─────────────────────────────────────────────
    # Score final = score vectoriel + boost lexical basé sur l'entité et les intents
    for r in deduped:
        r["_final_score"] = r["score"] + keyword_boost(r, entity, intents)

    deduped.sort(key=lambda x: x["_final_score"], reverse=True)

    return deduped[:20]


# ── HTML ──────────────────────────────────────────────────────────────────────
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


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.get("/stats")
async def stats():
    return {"chunks": collection.count()}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.post("/ask")
async def ask(request: Request):
    body     = await request.json()
    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": True, "detail": "Question vide."})

    # 1. Recherche dans ChromaDB
    results = await search_docs(question)

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
        return (toks[-1].strip() if toks else "")

    def extract_mark_names_from_results(items: list[dict]) -> list[str]:
        names: list[str] = []
        for it in items:
            content = it.get("content", "") or ""
            meta = it.get("meta") or {}
            label = (meta.get("source_label") or "")

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

        # dedup
        out = []
        seen = set()
        for n in names:
            k = n.lower()
            if k in seen:
                continue
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
        # Vérifier si nous avons des sources pour les marques (WIPO/F6S pour vérification, INNORPI pour procédures)
        has_wipo_f6s = any((r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"] for r in results)
        has_innorpi = any((r.get("meta") or {}).get("source_type") == "INNORPI" for r in results)
        
        # Si c'est une question procédurale, INNORPI suffit
        procedural_query = any(k in question.lower() for k in [
            "comment", "procedure", "procédure", "déposer", "deposer",
            "protection", "protéger", "proteger", "enregistrer", "dépôt", "loi", "réglementation"
        ])
        
        if procedural_query and has_innorpi:
            pass  # OK, on a les procédures INNORPI
        elif not procedural_query and not has_wipo_f6s:
            return {
                "error": False,
                "answer": (
                    "Je n'ai pas trouvé de source WIPO ou F6S pertinente pour vérifier cette marque spécifique. "
                    "Relancez l'ingestion WIPO/F6S et reformulez avec le nom exact entre guillemets."
                ),
                "sources": [],
            }
        elif procedural_query and not has_innorpi:
            return {
                "error": False,
                "answer": (
                    "Je n'ai pas trouvé de source INNORPI pertinente pour les procédures de dépôt de marque. "
                    "Relancez l'ingestion INNORPI pour obtenir les informations procédurales."
                ),
                "sources": [],
            }

    def source_label(item: dict) -> str:
        m = item.get("meta") or {}
        return m.get("source_label") or m.get("source") or m.get("filename") or "source"

    def deterministic_audit(q: str, items: list[dict]) -> str:
        legal_form_re = re.compile(r"\b(sarl|suarl|s\.a\.|\bsa\b|forme\s+juridique|code\s+des\s+soci[eé]t[eé]s)\b", re.I)
        low = q.lower()
        has_legal_need = any(k in low for k in ["forme juridique", "sarl", "sa", "statuts", "creation", "création", "societe", "société"])
        has_trademark_need = any(k in low for k in ["marque", "innorpi", "deposer", "déposer", "nice"])
        has_license_need = any(k in low for k in ["licence", "spdx", "agpl", "gpl", "mit", "apache-2.0"])
        has_tax_need = any(k in low for k in ["cnss", "tva", "fiscal", "impot", "impôt", "irpp", "is"])
        has_case_need = any(k in low for k in ["jurisprudence", "jugement", "arrêt", "arret", "tribunal", "cour"])

        def pick(pred):
            return [r for r in items if pred(r)]

        def text_of(r: dict) -> str:
            return (r.get("content") or "").lower()

        legal_hits = pick(
            lambda r: ((r.get("meta") or {}).get("domain") == "LEGAL")
            and bool(legal_form_re.search(text_of(r)))
        )
        trademark_hits = pick(lambda r: (
            ((r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"]) or 
            ((r.get("meta") or {}).get("source_type") == "INNORPI")
        ))
        license_hits = pick(lambda r: ((r.get("meta") or {}).get("source_type") == "SPDX"))
        tax_hits = pick(
            lambda r: ((r.get("meta") or {}).get("domain") == "FISCAL")
            and any(k in text_of(r) for k in ["cnss", "tva", "taxe", "fiscal", "impot", "impôt"])
        )
        case_hits = pick(
            lambda r: ((r.get("meta") or {}).get("domain") == "JURISPRUDENCE")
            and any(k in text_of(r) for k in ["jugement", "arrêt", "arret", "tribunal", "cour", "affaire"])
        )

        # Pour la marque: les pages procédurales INNORPI sont suffisantes pour
        # les questions "comment déposer / protéger". La vérification d'un nom
        # spécifique (conflit) exige un nom proche — on distingue les deux cas.
        candidate = extract_candidate_mark(q)
        names = extract_mark_names_from_results(trademark_hits)
        procedural_query = any(k in q.lower() for k in [
            "comment", "procedure", "procédure", "déposer", "deposer",
            "protection", "protéger", "proteger", "enregistrer", "dépôt",
        ])
        if procedural_query:
            trademark_relevant = trademark_hits  # pages procédurales suffisent
        else:
            trademark_relevant = trademark_hits if has_close_match(candidate, names) else trademark_hits[:1] if trademark_hits else []

        rows = []

        if has_legal_need:
            state = "VÉRIFIÉ" if legal_hits else "INSUFFISANT"
            ev = "; ".join(source_label(x) for x in legal_hits[:3]) or "Aucune source LEGAL pertinente"
            rows.append(("Forme juridique / création", state, ev))

        if has_trademark_need:
            wipo_f6s_hits = [r for r in trademark_hits if (r.get("meta") or {}).get("domain") in ["MARQUES", "ENTREPRISES"]]
            innorpi_hits = [r for r in trademark_hits if (r.get("meta") or {}).get("source_type") == "INNORPI"]
            
            if wipo_f6s_hits or innorpi_hits:
                state = "VÉRIFIÉ"
                sources = []
                if wipo_f6s_hits:
                    sources.append("WIPO/F6S (vérification marques)")
                if innorpi_hits:
                    sources.append("INNORPI (procédures/lois)")
                ev = "; ".join(sources)
            else:
                state = "DONNÉES PARTIELLES"
                ev = "Certaines sources manquantes - compléter l'ingestion WIPO/F6S et INNORPI"
            rows.append(("Marques (vérification + procédures)", state, ev))

        if has_license_need:
            state = "VÉRIFIÉ" if license_hits else "INSUFFISANT"
            ev = "; ".join(source_label(x) for x in license_hits[:3]) or "Aucune source SPDX pertinente"
            rows.append(("Licences open source", state, ev))

        if has_tax_need:
            state = "VÉRIFIÉ" if tax_hits else "INSUFFISANT"
            ev = "; ".join(source_label(x) for x in tax_hits[:3]) or "Aucune source fiscale/CNSS/TVA pertinente"
            rows.append(("CNSS / TVA / Fiscal", state, ev))

        if has_case_need:
            state = "VÉRIFIÉ" if case_hits else "INSUFFISANT"
            ev = "; ".join(source_label(x) for x in case_hits[:3]) or "Aucune source de jurisprudence pertinente"
            rows.append(("Jurisprudence", state, ev))

        if not rows:
            return ""

        verified = sum(1 for _, s, _ in rows if s == "VÉRIFIÉ")
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

    # Audit déterministe — précède la réponse LLM mais ne la remplace pas
    audit_prefix = ""
    if is_multi_domain_check(question):
        audit_prefix = deterministic_audit(question, results)

    # 2. Construire le contexte depuis les documents trouvés
    if not results:
        context = "AUCUN DOCUMENT CHARGÉ"
    else:
        parts = []
        for i, r in enumerate(results, 1):
            meta = r.get("meta") or {}
            label = meta.get("source_label") or meta.get("source") or meta.get("filename") or "document"
            parts.append(f"[SOURCE {i} — {label} — pertinence {r['score']:.2f}]\n{r['content']}")
        context = "\n\n---\n\n".join(parts)

    system = STRICT_SYSTEM.format(context=context)

    # 3. Appel LLM
    try:
        llm = AsyncOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            http_client=httpx.AsyncClient(verify=False, timeout=90.0),
        )
        resp = await llm.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=1500,
            temperature=0.1,  # très bas pour rester collé aux sources
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": question},
            ],
        )
        answer = resp.choices[0].message.content
        # Ajoute l'audit déterministe en bas de la réponse LLM si pertinent
        if audit_prefix:
            answer = answer.rstrip() + "\n\n---\n\n" + audit_prefix
        sources = list({
            (r.get("meta") or {}).get("source_label")
            or (r.get("meta") or {}).get("source")
            or (r.get("meta") or {}).get("filename", "?")
            for r in results
        })
        return {"error": False, "answer": answer, "sources": sources}

    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return JSONResponse({"error": True, "detail": str(e)})


@app.get("/domains")
async def domains():
    """Statistiques par domaine."""
    try:
        counts = {}
        for domain in ["LEGAL", "FISCAL", "MARQUES", "ENTREPRISES", "JURISPRUDENCE"]:
            res = collection.get(where={"domain": {"$eq": domain}}, limit=1)
            total = collection.count()
            counts[domain.lower()] = len(collection.get(where={"domain": {"$eq": domain}})["ids"])
        return {"domains": counts, "total": collection.count()}
    except Exception:
        return {"domains": {}, "total": collection.count()}


if __name__ == "__main__":
    import uvicorn
    print("\n  Agent Legal IA — http://localhost:5051\n")
    uvicorn.run(app, host="0.0.0.0", port=5051, log_level="info")
