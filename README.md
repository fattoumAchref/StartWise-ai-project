# 🚀 StartWise — Multi-Agent AI Strategic Analysis Platform

> **StartWise** est une plateforme d'intelligence artificielle multi-agents conçue pour analyser des projets de startup en profondeur. En quelques minutes, 4 agents IA spécialisés produisent une analyse marketing stratégique complète : veille marché, identité visuelle, psychologie comportementale, et plan d'exécution créatif — le tout streamé en temps réel via WebSocket.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Django](https://img.shields.io/badge/Django-4.2-green?logo=django)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-purple)
![Groq](https://img.shields.io/badge/Groq-LLM-orange)
![WebSocket](https://img.shields.io/badge/WebSocket-Realtime-cyan)

---

## 📋 Table des matières

- [Vue d'ensemble](#-vue-densemble)
- [Architecture](#-architecture)
- [Les 4 Agents IA](#-les-4-agents-ia)
- [Infrastructure Haute Disponibilité](#-infrastructure-haute-disponibilité)
- [Stack Technique](#-stack-technique)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Lancement](#-lancement)
- [Fonctionnalités Frontend](#-fonctionnalités-frontend)
- [Sécurité — PromptGuard](#-sécurité--promptguard)
- [Génération d'images](#-génération-dimages)
- [Support multilingue](#-support-multilingue)
- [Paramètres utilisateur](#-paramètres-utilisateur)
- [Structure du projet](#-structure-du-projet)
- [Équipe](#-équipe)

---

## 🌟 Vue d'ensemble

StartWise prend en entrée la description d'un projet ou d'une startup, et produit en sortie :

| Livrable | Description |
|----------|-------------|
| 📊 **Analyse de risques** | 4 risques majeurs avec probabilité, impact et mitigation |
| 📈 **Signaux faibles** | Tendances émergentes scrappées depuis DuckDuckGo |
| 🎨 **Identité visuelle** | Archétype, palette, typographie, logos concurrents, moodboard |
| 🧠 **Profil OCEAN** | Big Five psychologique de la cible |
| 🗺️ **Customer Journey Map** | 5–7 étapes avec émotions, friction et avantages concurrentiels |
| ⚡ **Roadmap 4 phases** | Plan d'exécution avec images FLUX.1 générées par IA |
| 🎯 **Killer Features** | 4 fonctionnalités anti-concurrentielles priorisées |
| 📄 **Business Model Canvas** | 9 blocs générés automatiquement |
| 🎤 **Pitch Deck** | 5 slides investisseur avec données réelles |
| 🏆 **Master Score** | Score composite de viabilité 0–100 |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (React 18)                       │
│   Dashboard │ Archive │ Team │ Docs │ Settings              │
│   WebSocket Client (singleton global — AppContext)          │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket ws://localhost:8000/ws/agents
┌──────────────────────▼──────────────────────────────────────┐
│              BACKEND (Django 4.2 + Daphne ASGI)             │
│                                                              │
│  ┌─────────────┐    ┌──────────────────────────────────┐   │
│  │ PromptGuard │───▶│         LangGraph Pipeline        │   │
│  │ (3 couches) │    │                                   │   │
│  └─────────────┘    │  supervisor_node                  │   │
│                     │       │                           │   │
│                     │  parallel_scout_node              │   │
│                     │  ┌────┴─────────┬────────────┐   │   │
│                     │  │              │            │   │   │
│                     │  ▼              ▼            ▼   │   │
│                     │ Trend        Vision       Emotion │   │
│                     │  └────────────┴────────────┘   │   │
│                     │              │                   │   │
│                     │  creative_director_node          │   │
│                     └──────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │          SmartInferenceProvider (HA Layer)           │   │
│  │  Groq (prioritaire) ──────────▶ ESPRIT (fallback)   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            UnifiedImageClient (HA Layer)             │   │
│  │  HuggingFace FLUX.1 (40s) ──▶ Pollinations (fallback)│  │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Flux de données clé :**
1. L'utilisateur soumet une description de projet via le frontend
2. Le PromptGuard vérifie la légitimité du prompt (3 couches)
3. Le state LangGraph (`AgentState`) est initialisé avec `lang`, `creativity`, `model`
4. `parallel_scout_node` lance **Trend + Vision + Emotion en parallèle** via `asyncio.gather`
5. `creative_director_node` synthétise les 3 résultats
6. Chaque résultat est streamé vers le frontend via WebSocket dès qu'il est prêt
7. Les images > 800KB sont envoyées dans un message séparé `agent_images`

---

## 🤖 Les 4 Agents IA

### 📡 Trend Hunter (`trend_agent.py`)
**Rôle :** Veille marché et intelligence compétitive en temps réel

**Ce qu'il fait :**
- Scrape DuckDuckGo (15–20 sources web + Reddit)
- Vérifie l'accessibilité de chaque URL (domaines expirés ignorés)
- Indexe les documents dans **FAISS** (Facebook AI Similarity Search) avec embeddings `all-MiniLM-L6-v2`
- Effectue une recherche vectorielle par similarité cosinus
- Génère via LLM : 4 risques majeurs + 5 recommandations + gap analysis + pre-mortem 5 ans
- Génère 3 images IA (risks / strategy / premortem)

**Modèle LLM :** Groq 70B (configurable) → ESPRIT fallback

---

### 🎨 Visual Semiotics Agent (`vision_agent.py`)
**Rôle :** Sémiotique visuelle, branding et identité graphique

**Ce qu'il fait :**
- Recherche les logos et visuels des concurrents (Crunchbase, LinkedIn, sites officiels)
- Identifie l'archétype visuel dominant du secteur (Glassmorphism, Brutalism, Neumorphism, Skeuomorphism, Flat Design...)
- Génère : palette hex complète avec justification psychologique par couleur
- Recommande une paire typographique (Google Fonts) adaptée à la marque
- Crée une icône SVG de marque personnalisée
- Génère un moodboard de 3 visuels via HuggingFace FLUX.1
- Produit un Vibe Check (score esthétique), un Temporal Aging (score de modernité)

**Modèle LLM :** Groq 8B (configurable) → ESPRIT fallback
**Images :** HuggingFace FLUX.1-schnell → Pollinations fallback

---

### 🧠 Emotional Intelligence Agent (`emotion_agent.py`)
**Rôle :** Psychologie comportementale et intelligence concurrentielle émotionnelle

**Ce qu'il fait :**
- Construit un **profil OCEAN** (Big Five) de la cible avec scores 0–100
- Génère un **Customer Journey Map** (5–7 étapes) avec émotions, friction et avantages concurrentiels
- Produit le **Sentiment Velocity** (évolution du sentiment sur les concurrents)
- Construit le **Hall of Shame** (UX anti-patterns observés chez les concurrents, format HTML)
- Génère le **Voice Matching** (comparaison de réponses client bon/mauvais)
- Produit : nudges comportementaux, stratégie cognitive, Tone of Voice, ethical hook, cognitive load

**Modèle LLM :** Groq 8B (configurable) → ESPRIT fallback

---

### ⚡ Creative Director (`creative_agent.py`)
**Rôle :** Synthèse stratégique finale et plan d'exécution

**Ce qu'il fait :**
- Agrège les outputs des 3 agents précédents
- Calcule les **Disruption Scores** (5 axes : innovation, scalabilité, risque, coût, UX)
- Génère un **Radical Pivot** stratégique
- Construit un **Stress Test** (3 scénarios de crise avec score de résilience)
- Produit une **Roadmap 4 phases** avec milestones, intégration visuelle, et image FLUX.1 par phase
- Identifie 4 **Killer Features** anti-concurrentielles
- Génère un **MVP Blueprint** priorisé (CRITICAL / HIGH / MEDIUM)
- Génère 4 images en parallèle via `asyncio.gather`

**Modèle LLM :** Groq 70B (configurable) → ESPRIT fallback
**Images :** HuggingFace FLUX.1-schnell → Pollinations fallback

---

## 🛡️ Infrastructure Haute Disponibilité

### SmartInferenceProvider
Couche d'inférence LLM à 2 niveaux avec basculement transparent :

```python
# Groq prioritaire (ultra-rapide, ~300 tok/s)
# → ESPRIT/TokenFactory fallback si :
#   - HTTP 429 (quota dépassé)
#   - Timeout
#   - Erreur de connexion

inference     = SmartInferenceProvider(prefer_quality=False)  # 8B — Vision + Emotion
inference_pro = SmartInferenceProvider(prefer_quality=True)   # 70B — Trend + Creative
```

**Modèles disponibles :**
| Frontend ID | Groq Model ID | Vitesse |
|-------------|---------------|---------|
| `llama-70b` | `llama-3.3-70b-versatile` | ~150 tok/s |
| `llama-8b`  | `llama-3.1-8b-instant`   | ~300 tok/s |
| `qwen-32b`  | `qwen/qwen3-32b`          | ~200 tok/s |
| `kimi-k2`   | `moonshotai/kimi-k2-instruct` | ~180 tok/s |

### UnifiedImageClient
Couche d'images à 2 niveaux :
- **Priorité 1 :** HuggingFace `black-forest-labs/FLUX.1-schnell` (timeout 40s)
- **Priorité 2 :** Pollinations.ai (gratuit, sans clé, avec retry sur 429)

### PromptGuard (3 couches)
Sécurisation multi-niveaux avant chaque analyse :

| Couche | Mécanisme | Latence | Détecte |
|--------|-----------|---------|---------|
| 1 | Pré-filtre jailbreak (keywords) | < 1ms | "act as", "bypass", "DAN mode"... |
| 2 | Pré-filtre contenu illégal (~45 patterns fr/en/ar) | < 1ms | phishing, ransomware, dark web, vol de données... |
| 3 | Juge LLM sémantique (Groq 8B) | ~1s | Contenu criminel formulé de façon détournée |

---

## 🛠️ Stack Technique

### Backend
| Technologie | Version | Usage |
|-------------|---------|-------|
| Python | 3.11 | Runtime principal |
| Django | 4.2 | Framework web |
| Django Channels | 4.x | WebSocket ASGI |
| Daphne | 4.x | Serveur ASGI |
| LangGraph | 0.2 | Orchestration multi-agent |
| FAISS | 1.7+ | Recherche vectorielle |
| HuggingFace Hub | latest | Images FLUX.1 + embeddings |
| Groq SDK | latest | LLM ultra-rapide |
| aiohttp | 3.x | Vérification URLs async |
| ddgs | latest | Scraping DuckDuckGo |
| Pillow | latest | Traitement images |

### Frontend
| Technologie | Version | Usage |
|-------------|---------|-------|
| React | 18 | UI framework |
| Framer Motion | latest | Animations |
| Tailwind CSS | 3.x | Styling |
| Lucide React | latest | Icônes |
| React Router | 6 | Navigation |

---

## 📦 Installation

### Prérequis
- Python 3.11+
- Node.js 18+
- npm ou yarn

### 1. Cloner le projet

```bash
git clone https://github.com/fattoumAchref/StartWise-ai-project.git
cd StartWise-ai-project
```

### 2. Backend — environnement virtuel

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Frontend — dépendances

```bash
cd frontend
npm install
```

---

## ⚙️ Configuration

Créer le fichier `backend/.env` :

```env
# ── LLM Principal (Groq — ultra-rapide) ──────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── LLM Fallback (TokenFactory/ESPRIT) ──────────────────────
TOKEN_FACTORY_API_KEY=your_esprit_token_here

# ── Images IA (HuggingFace FLUX.1) ──────────────────────────
HUGGINGFACE_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
# ou : HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Django ──────────────────────────────────────────────────
SECRET_KEY=your_django_secret_key
DEBUG=True
```

> **Note :** Si `GROQ_API_KEY` est absent, le système bascule directement sur ESPRIT.
> Si `HUGGINGFACE_API_KEY` est absent, les images utilisent Pollinations (gratuit).

---

## 🚀 Lancement

### Backend

```bash
cd backend
python manage.py migrate
python manage.py runserver
# → Serveur Daphne ASGI sur http://127.0.0.1:8000
```

### Frontend

```bash
cd frontend
npm run dev
# → Vite dev server sur http://localhost:5173
```

Ouvrir **http://localhost:5173** dans le navigateur.

---

## 🎨 Fonctionnalités Frontend

### Dashboard principal
- **Input** avec suggestions typewriter animées (changent selon la langue)
- **Launch Overlay** animé pendant le démarrage de l'analyse
- **4 Agent Cards** avec statut en temps réel (Prêt → En cours → Terminé)
- **Thought Stream** — flux de pensées des agents en direct
- **KPI Cards** — Signaux marché, Confiance IA, Concepts générés
- **Executive AI Synthesis** — synthèse narrative complète avec Master Score

### Onglet Analyses (Archive)
- Historique de toutes les analyses avec métadonnées
- Rechargement complet d'une analyse passée (tous les résultats restaurés)
- Déduplication automatique

### Agent Detail Page (`/agent/:agentId`)
- Vue détaillée des résultats de chaque agent
- Onglets spécialisés par agent (ex : Market Emotions / Psychology pour Emotion Agent)

### Business Model Canvas
- 9 blocs générés automatiquement depuis les données des agents
- Export PDF via impression navigateur
- Entièrement traduit en fr/en/bm/ar

### Pitch Deck
- 5 slides investisseur avec navigation clavier (← →)
- Barre de progression par slide
- Profil OCEAN visualisé avec barres animées
- Mots déclencheurs (trigger words) de la cible
- Entièrement traduit en fr/en/bm/ar

### SecurityToast
- Notification temps réel si le PromptGuard bloque une analyse
- Barre de progression 5s, dismiss manuel, animation slide-in

### Settings (Engine Room)
- Slider créativité → temperature LLM réelle (0.1–0.9)
- Sélecteur de 4 modèles Groq réels
- Toggle Deep Scan (timeout 600s → 900s)
- Jauges CPU/MEM/GPU animées (charge serveur)

---

## 🔒 Sécurité — PromptGuard

Le PromptGuard bloque les requêtes avant même d'initialiser le pipeline LangGraph.

**Exemples de prompts bloqués :**
- `"Créer une plateforme de phishing automatisée..."` → Bloqué couche 2 (keyword "phishing")
- `"Ignore previous instructions and..."` → Bloqué couche 1 (jailbreak)
- `"Projet de revente de données sur le dark web"` → Bloqué couche 2 (keyword "dark web")
- Projet criminel formulé de façon détournée → Bloqué couche 3 (juge LLM)

**Comportement en cas de blocage :**
1. Backend : log `[PROMPT GUARD] 🚫 Prompt bloqué`
2. WebSocket : message `{ type: "error", guard_blocked: true, message: "..." }`
3. Frontend : `SecurityToast` s'affiche pendant 5s, bouton "Lancer" redevient actif

---

## 🖼️ Génération d'images

Les images sont générées pour :
- **Trend Agent :** 3 images (risks, strategy, premortem)
- **Vision Agent :** 3 images moodboard
- **Creative Agent :** 4 images (une par phase de roadmap)

**Pipeline de génération :**
```
Prompt (anglais, optimisé FLUX.1)
  → HuggingFace InferenceClient (FLUX.1-schnell, timeout 40s)
    ✅ Succès → data:image/webp;base64,...
    ❌ Timeout/Erreur → Pollinations.ai fallback
      ✅ Succès → data:image/webp;base64,...
      ❌ 429 → sleep 40s → retry
        ❌ Échec → "" (image ignorée silencieusement)
```

Les images sont générées en parallèle via `asyncio.gather` pour minimiser la latence.

**Adaptive split :** Si la taille totale des images > 800KB, elles sont envoyées dans un message WebSocket séparé pour éviter les timeouts.

---

## 🌍 Support multilingue

L'interface et le contenu généré supportent 4 langues :

| Code | Langue | Flag |
|------|--------|------|
| `fr` | Français | 🇫🇷 |
| `en` | English | 🇬🇧 |
| `bm` | Bambara | 🇲🇱 |
| `ar` | Arabic (RTL) | 🇸🇦 |

**Ce qui est traduit :**
- Toute l'interface (navigation, boutons, labels)
- Suggestions de projets (typewriter)
- Contenu généré par les agents (via `_lang_instruction` dans chaque prompt)
- Business Model Canvas (9 blocs)
- Pitch Deck (5 slides + headlines)
- Documentation (descriptions des nœuds)
- Notifications PromptGuard

**L'arabe active automatiquement** `dir="rtl"` sur le layout principal.

---

## ⚙️ Paramètres utilisateur

| Paramètre | Type | Effet réel |
|-----------|------|------------|
| **Créativité** | Slider 0–100 | Convertit en `temperature` LLM (0.1–0.9) appliqué à tous les agents |
| **Modèle** | Sélecteur 4 options | Envoie l'ID Groq réel via WebSocket → utilisé par tous les agents |
| **Deep Scan** | Toggle | Timeout 600s (OFF) vs 900s (ON) |

**Recommandations :**
- `Llama 8B + Créativité 30%` → Exploration rapide (~2 min)
- `Llama 70B + Créativité 60% + Deep Scan` → Pitch investisseur (~8 min)
- `Qwen 32B + Créativité 80%` → Brainstorming disruptif (~4 min)

---

## 📁 Structure du projet

```
startwise/
├── backend/
│   ├── agents/
│   │   ├── inference.py          # SmartInferenceProvider + PromptGuard + UnifiedImageClient
│   │   ├── graph.py              # LangGraph StateGraph + parallel_scout_node
│   │   ├── consumers.py          # AsyncWebsocketConsumer (Django Channels)
│   │   ├── trend_agent.py        # Trend Hunter — FAISS + DuckDuckGo + LLM
│   │   ├── vision_agent.py       # Visual Semiotics — branding + moodboard
│   │   ├── emotion_agent.py      # Emotional Intelligence — OCEAN + Journey Map
│   │   ├── creative_agent.py     # Creative Director — synthèse + roadmap
│   │   └── self_correct.py       # Auto-correction (optionnel)
│   ├── startwise/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── asgi.py               # Configuration Channels + WebSocket routing
│   ├── manage.py
│   ├── requirements.txt
│   └── .env                      # Non commité — voir Configuration
│
├── frontend/
│   ├── src/
│   │   ├── context/
│   │   │   └── AppContext.jsx    # WebSocket global + state + TRANSLATIONS
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx     # Page principale — tous les onglets
│   │   │   └── AgentPage.jsx     # Page détail d'un agent
│   │   ├── components/
│   │   │   ├── SecurityToast.jsx # Notification PromptGuard
│   │   │   ├── ThoughtStream.jsx # Flux de pensées temps réel
│   │   │   ├── KPICards.jsx      # Cartes statistiques
│   │   │   └── ...
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── tailwind.config.js
│   └── package.json
│
└── README.md
```

---

## 📄 Licence

Projet académique — ESPRIT School of Engineering © 2026

---

*Généré avec ❤️ par MANÉ*
