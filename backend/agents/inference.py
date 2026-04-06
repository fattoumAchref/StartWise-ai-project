# backend/agents/inference.py
# ============================================================
#  HIGH-AVAILABILITY INFERENCE LAYER — StartWise
# ============================================================
#  Architecture de résilience à 3 niveaux :
#    1. Groq (ultra-rapide, prioritaire)
#    2. TokenFactory/ESPRIT (secours LLM)
#    3. Pollinations.ai (secours image uniquement)
# ============================================================

import os
import io
import asyncio
import base64
import time
import json
import httpx
import requests
import logging
from PIL import Image
from openai import OpenAI, APIStatusError, APITimeoutError, APIConnectionError
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────

GROQ_BASE_URL      = "https://api.groq.com/openai/v1"
ESPRIT_BASE_URL    = "https://tokenfactory.esprit.tn/api"

# Modèles Groq — fast 8B pour les tâches légères, 70B pour la qualité
GROQ_MODEL_FAST    = "llama-3.1-8b-instant"
GROQ_MODEL_QUALITY = "llama-3.3-70b-versatile"

# Modèle ESPRIT (fallback)
ESPRIT_MODEL       = "hosted_vllm/Llama-3.1-70B-Instruct"

# Mapping frontend model id → Groq model id réel
FRONTEND_MODEL_MAP = {
    "llama-70b": "llama-3.3-70b-versatile",
    "llama-8b":  "llama-3.1-8b-instant",
    "qwen-32b":  "qwen/qwen3-32b",
    "kimi-k2":   "moonshotai/kimi-k2-instruct",
}

# Erreurs Groq qui déclenchent le basculement
_GROQ_RETRYABLE = (APIStatusError, APITimeoutError, APIConnectionError)


# ─────────────────────────────────────────────────────────────
#  1. SmartInferenceProvider
#     Groq (prioritaire) → TokenFactory/ESPRIT (secours)
# ─────────────────────────────────────────────────────────────

class SmartInferenceProvider:
    """
    Client LLM haute disponibilité.
    Tente Groq en premier ; bascule silencieusement sur ESPRIT si :
      - quota dépassé (429)
      - timeout
      - erreur de connexion
    Le basculement est totalement transparent pour les agents appelants.
    """

    def __init__(self, prefer_quality: bool = False):
        """
        prefer_quality=False → Groq llama-3.1-8b-instant (ultra-rapide, ~300 tok/s)
        prefer_quality=True  → Groq llama-3.3-70b-versatile (meilleure qualité)
        """
        self.groq_model  = GROQ_MODEL_QUALITY if prefer_quality else GROQ_MODEL_FAST
        self.esprit_model = ESPRIT_MODEL
        self._active_provider = "groq"  # pour logs

        # ── Client Groq ──────────────────────────────────────
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            self._groq = OpenAI(
                api_key=groq_key,
                base_url=GROQ_BASE_URL,
                timeout=httpx.Timeout(45.0, connect=8.0),
            )
        else:
            logger.warning("[INFERENCE] GROQ_API_KEY absente — Groq désactivé, ESPRIT sera utilisé directement")
            self._groq = None

        # ── Client ESPRIT (fallback) ─────────────────────────
        esprit_key = os.getenv("TOKEN_FACTORY_API_KEY")
        if esprit_key:
            self._esprit = OpenAI(
                api_key=esprit_key,
                base_url=ESPRIT_BASE_URL,
                http_client=httpx.Client(verify=False, timeout=httpx.Timeout(120.0, connect=15.0)),
            )
        else:
            logger.error("[INFERENCE] TOKEN_FACTORY_API_KEY absente — aucun fallback disponible")
            self._esprit = None

    def complete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model_override: str | None = None,
    ) -> str:
        """
        Appel synchrone.
        model_override : ID Groq réel (ex: "mixtral-8x7b-32768"), prioritaire sur self.groq_model.
        Retourne le contenu texte brut de la réponse.
        Lève RuntimeError si les deux providers échouent.
        """
        groq_model = model_override or self.groq_model
        # ── Tentative Groq ───────────────────────────────────
        if self._groq:
            try:
                resp = self._groq.chat.completions.create(
                    model=groq_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                self._active_provider = "groq"
                return resp.choices[0].message.content

            except _GROQ_RETRYABLE as e:
                status = getattr(e, "status_code", "?")
                print(
                    f"\n[FALLBACK] ⚠️  Groq indisponible (HTTP {status}) — "
                    f"bascule sur infrastructure de secours (ESPRIT)\n"
                )
                logger.warning(f"[FALLBACK] Groq → ESPRIT | {type(e).__name__}: {e}")

            except Exception as e:
                print(
                    f"\n[FALLBACK] ⚠️  Groq erreur inattendue ({type(e).__name__}) — "
                    f"bascule sur infrastructure de secours (ESPRIT)\n"
                )
                logger.warning(f"[FALLBACK] Groq → ESPRIT (inattendu) | {e}")

        # ── Basculement ESPRIT ───────────────────────────────
        if self._esprit:
            self._active_provider = "esprit"
            resp = self._esprit.chat.completions.create(
                model=self.esprit_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content

        raise RuntimeError(
            "[INFERENCE] Tous les providers LLM sont indisponibles (Groq + ESPRIT)."
        )

    async def acomplete(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model_override: str | None = None,
    ) -> str:
        """Version asynchrone — délègue à asyncio.to_thread pour ne pas bloquer la boucle."""
        return await asyncio.to_thread(self.complete, messages, temperature, max_tokens, model_override)

    @property
    def active_provider(self) -> str:
        """Retourne le nom du provider utilisé lors du dernier appel."""
        return self._active_provider


# ─────────────────────────────────────────────────────────────
#  2. PromptGuard
#     Analyse la dangerosité du prompt utilisateur AVANT
#     de lancer les 4 agents.
# ─────────────────────────────────────────────────────────────

class PromptGuard:
    """
    Sécurisation multi-couches — 3 niveaux d'analyse :

    Couche 1 — Pré-filtre jailbreak (mots-clés, <1ms)
               Détecte les tentatives de manipulation de l'IA elle-même.

    Couche 2 — Pré-filtre contenu illégal (mots-clés multilingues, <1ms)
               Détecte les projets criminels/nuisibles décrits explicitement.

    Couche 3 — Juge LLM sémantique (Groq, ~1s)
               Évalue si le projet est légal et éthique via un prompt de jugement.
               Agit en complément des deux filtres précédents.

    Si Groq est indisponible, la couche 3 fail-open (ne bloque pas).
    Les couches 1 & 2 bloquent toujours sans dépendance réseau.
    """

    _INJECTION_THRESHOLD = 0.85

    # ── Couche 1 : Jailbreak / manipulation de l'IA ──────────────────────
    _JAILBREAK_KEYWORDS = [
        "ignore previous instructions",
        "ignore all instructions",
        "disregard your",
        "you are now",
        "act as",
        "jailbreak",
        "prompt injection",
        "forget everything",
        "new instructions",
        "bypass",
        "override your",
        "system prompt",
        "pretend you are",
        "roleplay as",
        "hypothetically speaking",
        "in a fictional world",
        "for educational purposes only",
        "as an ai with no restrictions",
        "dan mode",
        "developer mode",
    ]

    # ── Couche 2 : Contenu illégal / projet criminel (fr + en + ar) ──────
    # Chaque entrée est un tuple (keyword, label_court)
    _ILLEGAL_PATTERNS: list[tuple[str, str]] = [
        # Cybercriminalité
        ("phishing",             "phishing"),
        ("hameçonnage",          "hameçonnage"),
        ("phishing-as-a-service","phishing-as-a-service"),
        ("spear phishing",       "spear phishing"),
        ("ransomware",           "ransomware"),
        ("rançongiciel",         "rançongiciel"),
        ("malware",              "malware"),
        ("logiciel malveillant", "logiciel malveillant"),
        ("keylogger",            "keylogger"),
        ("trojan",               "trojan"),
        ("botnet",               "botnet"),
        ("ddos",                 "attaque DDoS"),
        # Vol de données / fraude financière
        ("données volées",       "données volées"),
        ("stolen data",          "stolen data"),
        ("stolen credentials",   "stolen credentials"),
        ("carte bancaire volée", "carte bancaire volée"),
        ("stolen credit card",   "stolen credit card"),
        ("carding",              "carding"),
        ("skimming",             "skimming de carte"),
        ("fraude bancaire",      "fraude bancaire"),
        ("bank fraud",           "bank fraud"),
        ("blanchiment d'argent", "blanchiment"),
        ("money laundering",     "money laundering"),
        ("غسيل الأموال",         "blanchiment (ar)"),
        # Dark web / marchés illicites
        ("dark web",             "dark web"),
        ("darknet",              "darknet"),
        ("tor market",           "marché tor"),
        ("revente de données",   "revente de données"),
        ("données à vendre",     "données à vendre"),
        ("data for sale",        "data for sale"),
        # Drogues / armes
        ("trafic de drogue",     "trafic de drogue"),
        ("drug trafficking",     "drug trafficking"),
        ("vente d'armes",        "vente d'armes"),
        ("arms trafficking",     "arms trafficking"),
        ("تهريب المخدرات",       "trafic drogues (ar)"),
        # Contenu dangereux
        ("exploitation d'enfants","exploitation d'enfants"),
        ("child exploitation",   "child exploitation"),
        ("human trafficking",    "human trafficking"),
        ("traite humaine",       "traite humaine"),
        # Escroquerie généralisée
        ("arnaque automatisée",  "arnaque automatisée"),
        ("automated scam",       "automated scam"),
        ("emails trompeurs",     "emails trompeurs"),
        ("faux emails",          "faux emails"),
        ("fake invoices",        "fake invoices"),
        ("identity theft",       "vol d'identité"),
        ("vol d'identité",       "vol d'identité"),
    ]

    def __init__(self):
        groq_key = os.getenv("GROQ_API_KEY")
        self._client = (
            OpenAI(
                api_key=groq_key,
                base_url=GROQ_BASE_URL,
                timeout=httpx.Timeout(15.0, connect=6.0),
            )
            if groq_key
            else None
        )

    # ── Couche 1 & 2 : filtres textuels ──────────────────────────────────

    def _check_keywords(self, lower: str) -> tuple[bool, str]:
        """Retourne (bloqué, raison) si un mot-clé suspect est trouvé."""
        for kw in self._JAILBREAK_KEYWORDS:
            if kw in lower:
                print(f"[PROMPT GUARD] 🚫 Rejeté (jailbreak) : '{kw}'")
                return True, (
                    f"Tentative de manipulation de l'IA détectée : \"{kw}\". "
                    "Cette plateforme est réservée à l'analyse de projets légitimes."
                )
        for pattern, label in self._ILLEGAL_PATTERNS:
            if pattern in lower:
                print(f"[PROMPT GUARD] 🚫 Rejeté (contenu illégal) : '{label}'")
                return True, (
                    f"Projet refusé : contenu illégal ou nuisible détecté (\"{label}\"). "
                    "StartWise analyse uniquement des projets légaux et éthiques."
                )
        return False, ""

    # ── Couche 3 : juge LLM sémantique ───────────────────────────────────

    def _llm_judge(self, user_prompt: str) -> tuple[bool, str]:
        """
        Demande au LLM d'évaluer si le projet est légal et éthique.
        Retourne (bloqué, raison).
        """
        if not self._client:
            return False, ""

        system_msg = (
            "You are a legal and ethical compliance officer for a business analysis platform. "
            "Your ONLY task is to determine if the described project is legal and ethical. "
            "Respond with EXACTLY one word: SAFE or UNSAFE. No explanation, no punctuation."
        )
        user_msg = (
            f"Project description:\n\"\"\"\n{user_prompt[:800]}\n\"\"\"\n\n"
            "Is this project legal, ethical, and free of criminal intent? "
            "Respond SAFE or UNSAFE."
        )

        try:
            resp = self._client.chat.completions.create(
                model=GROQ_MODEL_FAST,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=5,
            )
            verdict = resp.choices[0].message.content.strip().upper()
            print(f"[PROMPT GUARD] 🧠 Juge LLM : {verdict}")
            if "UNSAFE" in verdict:
                return True, (
                    "Ce projet a été identifié comme illégal ou contraire à l'éthique par notre système de modération. "
                    "StartWise est réservé à l'analyse de projets légaux et responsables."
                )
            return False, ""
        except Exception as e:
            logger.warning(f"[PROMPT GUARD] Juge LLM échec ({e}) — fail-open")
            return False, ""

    # ── Point d'entrée principal ──────────────────────────────────────────

    def check(self, user_prompt: str) -> tuple[bool, str]:
        """
        Retourne (True, "") si le prompt est sûr.
        Retourne (False, raison) si dangereux.
        """
        if not user_prompt or not user_prompt.strip():
            return False, "Prompt vide ou invalide."

        lower = user_prompt.lower()

        # Couche 1 & 2 — filtres textuels instantanés
        blocked, reason = self._check_keywords(lower)
        if blocked:
            return False, reason

        # Couche 3 — juge LLM sémantique
        blocked, reason = self._llm_judge(user_prompt)
        if blocked:
            return False, reason

        print("[PROMPT GUARD] ✅ Prompt validé — aucune menace détectée")
        return True, ""

    async def acheck(self, user_prompt: str) -> tuple[bool, str]:
        """Version asynchrone."""
        return await asyncio.to_thread(self.check, user_prompt)


# ─────────────────────────────────────────────────────────────
#  3. UnifiedImageClient
#     HuggingFace FLUX.1-schnell (prioritaire, 40s timeout)
#     → Pollinations.ai (fallback visuel, gratuit)
# ─────────────────────────────────────────────────────────────

class UnifiedImageClient:
    """
    Client d'image unifié haute disponibilité.
      Priorité 1 : HuggingFace Inference API (FLUX.1-schnell)
      Priorité 2 : Pollinations.ai (FLUX, gratuit, sans clé)

    Retourne toujours une data URI WebP base64 ou "" si les deux échouent.
    """

    HF_MODEL       = "black-forest-labs/FLUX.1-schnell"
    HF_TIMEOUT_SEC = 40          # strictement 40s comme demandé
    POLL_TIMEOUT   = 70          # Pollinations peut être lent

    def __init__(self):
        hf_key = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        self._hf_client = (
            InferenceClient(provider="hf-inference", api_key=hf_key)
            if hf_key
            else None
        )

    def _to_webp_b64(self, img) -> str:
        """Convertit une PIL Image en data URI WebP base64."""
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=87, method=4)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

    def _hf_generate(self, prompt: str) -> str:
        """Appel synchrone HuggingFace — exécuté dans un thread."""
        image = self._hf_client.text_to_image(prompt, model=self.HF_MODEL)
        return self._to_webp_b64(image)

    def _pollinations_generate(self, prompt: str, seed: int = 42) -> str:
        """Appel synchrone Pollinations — dernier recours."""
        import urllib.parse
        safe = prompt.encode("ascii", errors="ignore").decode("ascii")[:280]
        if len(safe) < 20:
            safe = "hyper-realistic 3D render cinematic dark technology concept"
        encoded = urllib.parse.quote(safe)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=832&height=576&nologo=true&model=flux&seed={seed}"
        )
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=self.POLL_TIMEOUT)
                if resp.status_code == 429:
                    if attempt == 0:
                        print("[IMAGE FALLBACK] Pollinations 429 — attente 40s puis retry...")
                        time.sleep(40)
                        continue
                    return ""
                if resp.status_code != 200:
                    return ""
                img = Image.open(io.BytesIO(resp.content))
                return self._to_webp_b64(img)
            except Exception as e:
                print(f"[IMAGE FALLBACK] Pollinations erreur (attempt {attempt+1}): {type(e).__name__}")
                if attempt == 0:
                    time.sleep(5)
        return ""

    async def generate(self, prompt: str, seed: int = 42, label: str = "") -> str:
        """
        Génère une image de manière asynchrone.
        label : identifiant lisible pour les logs (ex: "logo_a", "phase_2")
        """
        tag = f"[{label}] " if label else ""

        # ── Tentative HuggingFace ─────────────────────────────
        if self._hf_client:
            try:
                async with asyncio.timeout(self.HF_TIMEOUT_SEC):
                    uri = await asyncio.to_thread(self._hf_generate, prompt)
                kb = len(uri) * 3 // 4 // 1024
                print(f"[IMAGE HF] ✅ {tag}{kb}KB — FLUX.1-schnell")
                return uri
            except asyncio.TimeoutError:
                print(f"[IMAGE HF] ⏱️  {tag}Timeout {self.HF_TIMEOUT_SEC}s — bascule sur Pollinations")
            except Exception as e:
                print(f"[IMAGE HF] ⚠️  {tag}Erreur HuggingFace ({type(e).__name__}) — bascule sur Pollinations")

        # ── Basculement Pollinations ──────────────────────────
        print(f"[IMAGE FALLBACK] 🔄 {tag}Pollinations.ai (dernier recours)...")
        try:
            async with asyncio.timeout(self.POLL_TIMEOUT + 50):
                uri = await asyncio.to_thread(self._pollinations_generate, prompt, seed)
            if uri:
                kb = len(uri) * 3 // 4 // 1024
                print(f"[IMAGE FALLBACK] ✅ {tag}{kb}KB — Pollinations")
            else:
                print(f"[IMAGE FALLBACK] ❌ {tag}Pollinations a échoué — image ignorée")
            return uri
        except asyncio.TimeoutError:
            print(f"[IMAGE FALLBACK] ⏱️  {tag}Pollinations timeout — image ignorée")
            return ""
        except Exception as e:
            print(f"[IMAGE FALLBACK] ❌ {tag}Pollinations exception: {e}")
            return ""

    async def generate_batch(self, prompts: dict[str, str], seeds: dict[str, int] | None = None) -> dict[str, str]:
        """
        Génère plusieurs images en parallèle.
        prompts = {"label": "prompt text", ...}
        seeds   = {"label": seed_int, ...}  (optionnel)
        Retourne {"label": "data:image/webp;base64,...", ...}
        """
        seeds = seeds or {}
        tasks = [
            self.generate(prompt, seed=seeds.get(label, 42), label=label)
            for label, prompt in prompts.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            label: (r if isinstance(r, str) else "")
            for label, r in zip(prompts.keys(), results)
        }


# ─────────────────────────────────────────────────────────────
#  Utilitaire : extrait temperature + model_override depuis state
# ─────────────────────────────────────────────────────────────

def state_llm_params(state: dict) -> dict:
    """
    Retourne {"temperature": float, "model_override": str|None}
    à passer à SmartInferenceProvider.complete().

    creativity (0-100) → temperature (0.1 – 0.9)
    model (frontend id) → Groq model id réel
    """
    creativity = state.get("creativity", 50)
    temperature = round(0.1 + (creativity / 100) * 0.8, 2)

    frontend_model = state.get("model", "llama-70b")
    model_override = FRONTEND_MODEL_MAP.get(frontend_model)  # None si inconnu (garde défaut)

    return {"temperature": temperature, "model_override": model_override}


# ─────────────────────────────────────────────────────────────
#  Singletons exportés (instanciation unique par processus)
# ─────────────────────────────────────────────────────────────

# Provider standard (Groq 8B → ESPRIT) — pour Vision + Emotion
inference     = SmartInferenceProvider(prefer_quality=False)

# Provider qualité (Groq 70B → ESPRIT) — pour Creative + Trend
inference_pro = SmartInferenceProvider(prefer_quality=True)

# Guard
prompt_guard  = PromptGuard()

# Image client
image_client  = UnifiedImageClient()
