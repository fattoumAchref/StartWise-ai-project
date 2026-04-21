# StartWise — Plateforme Intégrée d'Idéation et d'Analyse Stratégique

> **Transformez une idée brute en stratégie complète grâce à une pipeline IA multi-agents.**
> StartWise fusionne un tunnel d'idéation conversationnel (Google ADK) et un moteur d'analyse stratégique 5 agents (LangGraph / Groq) dans une interface Next.js unifiée, avec génération d'images IA (FLUX · SDXL) et diffusion Telegram.

---

## Table des Matières

- [Vue d'ensemble](#vue-densemble)
- [Architecture & Flux de données](#architecture--flux-de-données)
- [Fonctionnalités](#fonctionnalités)
  - [Module Idéation (ADK)](#module-idéation-adk)
  - [Module Analyse Stratégique (LangGraph — 5 agents)](#module-analyse-stratégique-langgraph--5-agents)
  - [Module Product Audit](#module-product-audit)
  - [Génération d'images IA](#génération-dimages-ia)
  - [Intégration Telegram](#intégration-telegram)
  - [Fonctionnalités transversales](#fonctionnalités-transversales)
- [Stack Technique](#stack-technique)
- [Structure du Projet](#structure-du-projet)
- [Installation & Lancement](#installation--lancement)
- [Configuration (.env)](#configuration-env)
- [Équipe](#équipe)

---

## Vue d'ensemble

StartWise est une plateforme web complète conçue pour accompagner les entrepreneurs depuis la germination de leur idée jusqu'à la production d'analyses stratégiques actionnables et de livrables visuels. Elle repose sur trois modules principaux reliés par un pont de contexte partagé :

| Module | Rôle | Technologie |
|---|---|---|
| **Idéation** | Onboarding conversationnel, génération de concept, identité de marque | Next.js + Google ADK (Python) |
| **Analyse Stratégique** | Tendances, vision, émotions, créativité, plan commercial + images IA | Django + LangGraph + Groq + HuggingFace |
| **Product Audit** | Audit de site concurrent via crawling et analyse Gemini | Django + Firecrawl + Gemini |

---

## Architecture & Flux de données

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND  (Next.js — port 3000)                        │
│                                                                                 │
│  ┌────────────────────────┐         ┌────────────────────────────────────────┐  │
│  │   Tunnel d'Idéation    │         │   Dashboard Analyse Stratégique        │  │
│  │  (Onboarding / ADK)    │──────►  │    (LangGraph / 5 Agents)              │  │
│  │                        │ Bridge  │                                        │  │
│  │  • Collecte l'idée     │ Context │  • Trend Hunter                        │  │
│  │  • Génère identité     │(localStorage)  • Visionary                       │  │
│  │  • Sauvegarde contexte │         │  • Emotion Analyst                     │  │
│  │  • Session guard       │         │  • Creative Director                   │  │
│  └────────────────────────┘         │  • Commercial Agent                    │  │
│                                     └────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────────┬───────────────────────────────┘
               │ REST API (/api/ideation/*)        │ REST + WebSocket (/api/agents/*)
               │                                  │
┌──────────────▼──────────────────────────────────▼───────────────────────────────┐
│                          BACKEND  (Django — port 8000)                          │
│                                                                                 │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────────┐ │
│  │   App : ideation        │    │   App : agents (LangGraph)                  │ │
│  │                         │    │                                             │ │
│  │  • Orchestrateur ADK    │    │  • GraphState partagé                       │ │
│  │  • 6 agents ADK         │    │  • 5 agents parallèles (Groq)               │ │
│  │  • Session store        │    │  • Commercial Agent + image prototype       │ │
│  └─────────────────────────┘    │  • PromptGuard 3 couches                    │ │
│                                 │  • Injection RAG (document_text)            │ │
│                                 │  • FLUX.1-schnell (logo + prototype)        │ │
│                                 │  • SDXL (moodboard atmosphérique)           │ │
│                                 │  • Telegram Bot (sendMessage + sendPhoto)   │ │
│                                 └─────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌─────────────────────────┐    ┌─────────────────────────────────────────────┐ │
│  │   App : product_audit   │    │   Base de données                           │ │
│  │                         │    │   PostgreSQL (prod) / SQLite (dev)          │ │
│  │  • Firecrawl (crawling) │    │                                             │ │
│  │  • Gemini (analyse)     │    │                                             │ │
│  │  • Qdrant (vectorDB)    │    │                                             │ │
│  └─────────────────────────┘    └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Pont de contexte (Context Bridge)

Après l'idéation, le résumé et l'idée métier sont sauvegardés dans `localStorage` sous les clés :
- `sw_ideation_summary` — synthèse de l'idée générée par l'ADK
- `sw_ideation_business_idea` — idée métier principale

Le module d'analyse stratégique lit ces clés à l'initialisation (`AppContext`) et les injecte automatiquement dans chaque requête agent via le champ `document_text` du `GraphState` LangGraph.

### Système de session guard

Un flag `sw_fresh_session` (sessionStorage) est posé à la fin de l'onboarding. Chaque page du dashboard vérifie sa présence et redirige vers `/onboarding?reset=true` si absent, garantissant que l'utilisateur passe toujours par le tunnel d'idéation au démarrage d'une nouvelle session de navigateur.

---

## Fonctionnalités

### Module Idéation (ADK)

Pipeline conversationnel en 7 étapes, chacune gérée par un agent ADK spécialisé :

| Étape | Agent | Description |
|---|---|---|
| 1 | **Ideation Agent** | Collecte l'idée initiale, clarifie le secteur et la cible |
| 2 | **Viability Agent** | Évalue la faisabilité technique et marché |
| 3 | **SWOT Agent** | Génère la matrice SWOT complète |
| 4 | **BMC Agent** | Construit le Business Model Canvas (9 blocs) |
| 5 | **Brand Identity Agent** | Crée le nom de marque, slogan, palette de couleurs |
| 6 | **Marketing Agent** | Propose une stratégie marketing initiale |
| 7 | **Pitch Deck Agent** | Structure le pitch deck (problème → solution → marché → équipe) |

Un bouton **"Nouvelle Analyse"** permet de réinitialiser complètement la session et de repartir sur une nouvelle idée depuis la page d'idéation.

### Module Analyse Stratégique (LangGraph — 5 agents)

Cinq agents IA s'exécutent sur le `GraphState` LangGraph, leurs résultats étant fusionnés par un nœud de synthèse :

| Agent | Rôle |
|---|---|
| **Trend Hunter** | Détecte les tendances marché émergentes liées à l'idée |
| **Visionary** | Projette des scénarios de croissance à 3 et 5 ans |
| **Emotion Analyst** | Analyse les leviers émotionnels et psychologiques des clients cibles |
| **Creative Director** | Propose des angles créatifs différenciants + logo IA + moodboard |
| **Commercial Agent** | Plan d'action commercial, stratégie de lancement, diffusion Telegram |

**PromptGuard** — Sécurité en 3 couches :
1. Détection de prompt injection (regex + heuristiques)
2. Validation sémantique du contexte métier
3. Sanitisation des sorties avant affichage

**RAG (Retrieval-Augmented Generation)** — Upload de PDF/TXT depuis la sidebar ; le texte extrait est injecté dans `document_text` et transmis à tous les agents à chaque requête.

**Self-correction** — Si un agent retourne un JSON malformé, un nœud de correction automatique réessaie avec des instructions enrichies.

### Module Product Audit

Audit automatisé d'un site concurrent via URL :
1. **Firecrawl** crawle le site et extrait le contenu structuré
2. **Gemini** analyse le contenu (UX, offre, positionnement, points faibles)
3. **Qdrant** (vectorDB) stocke les embeddings pour des comparaisons futures
4. Le rapport est présenté en sections : Résumé exécutif, Forces, Faiblesses, Opportunités

### Génération d'images IA

Deux modèles HuggingFace sont utilisés selon l'usage :

| Modèle | Usage | Endpoint |
|---|---|---|
| **FLUX.1-schnell** (`black-forest-labs/FLUX.1-schnell`) | Logo de marque (1 image) + Visuel Prototype produit | HuggingFace Inference API |
| **SDXL** (`stabilityai/stable-diffusion-xl-base-1.0`) | Moodboard atmosphérique (1 image) | HuggingFace Inference API |

- **Logo** : généré par le Creative Director à partir du nom de marque et des couleurs ; affiché en pleine largeur avec bouton de téléchargement. Le logo personnalisé est persisté dans `localStorage` (`sw_custom_logo`) et survit à la navigation.
- **Moodboard** : image atmosphérique illustrant l'univers émotionnel de la marque.
- **Prototype** : rendu photoréaliste du produit/service, généré à la demande depuis l'agent Commercial. Envoyable directement sur Telegram.

### Intégration Telegram

Le **Commercial Agent** propose un bouton **"Propulser sur Telegram"** qui envoie en une action :

- **Photo principale** : le visuel prototype généré par FLUX.1-schnell (envoi multipart/form-data, aucune URL publique requise)
- **Légende** : rapport stratégique complet formaté en Markdown Telegram (scores de disruption, killer features, roadmap, recommandation finale)
- **Fallback automatique** : si le parsing Markdown échoue, re-envoi en texte brut

Configuration requise dans `.env` :
```env
TELEGRAM_BOT_TOKEN=votre_token_bot
TELEGRAM_CHAT_ID=votre_chat_id
```

### Fonctionnalités transversales

- **Dark / Light mode** — Géré par `next-themes` ; Tailwind v4 dark mode via `@custom-variant dark`
- **Internationalisation (i18n)** — 4 langues : Français, English, Bambara, Arabe (RTL automatique)
- **Historique des analyses** — 15 dernières analyses conservées en `localStorage`, accessibles depuis la sidebar
- **Sélecteur de modèle** — Choix du modèle Groq (llama-3.3-70b, mixtral-8x7b, gemma2-9b) en temps réel via WebSocket
- **WebSocket live** — Résultats des agents streamés en temps réel avec reconnexion automatique
- **Animations & Skeleton loading** — Transitions fluides, états de chargement par section

---

## Stack Technique

| Couche | Technologie | Version |
|---|---|---|
| Frontend | Next.js | 15.x |
| UI Components | shadcn/ui + Tailwind CSS | v4 |
| State Management | React Context (AppContext) | — |
| Theme | next-themes | — |
| Backend Framework | Django | 5.x |
| WebSocket | Django Channels | — |
| Agent Framework (Idéation) | Google ADK (Python) | — |
| Agent Framework (Marketing) | LangGraph | — |
| LLM (Marketing / Agents) | Groq (llama-3.3-70b) | — |
| LLM (Product Audit) | Google Gemini | — |
| Image Generation (Logo/Prototype) | FLUX.1-schnell via HuggingFace | — |
| Image Generation (Moodboard) | Stable Diffusion XL via HuggingFace | — |
| Messaging | Telegram Bot API | — |
| Web Crawling | Firecrawl | — |
| Vector Database | Qdrant | — |
| Base de données | SQLite (dev) / PostgreSQL (prod) | — |
| Communication Frontend/Backend | REST (Fetch API) + WebSocket | — |

---

## Structure du Projet

```
startwise/
├── backend/                        # Django backend
│   ├── backend/                    # Settings, URLs, WSGI
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   ├── ideation/                   # Module ADK (6 agents)
│   │   ├── services/
│   │   │   ├── orchestrator.py     # Pipeline ADK principal
│   │   │   ├── a2a_client.py       # Communication inter-agents
│   │   │   ├── schemas.py          # Modèles Pydantic
│   │   │   └── session_store.py    # Gestion des sessions
│   │   ├── views.py
│   │   └── urls.py
│   ├── agents/                     # Module LangGraph (5 agents)
│   │   ├── trend_agent.py          # Trend Hunter
│   │   ├── vision_agent.py         # Visionary + génération logo/moodboard
│   │   ├── emotion_agent.py        # Emotion Analyst
│   │   ├── creative_agent.py       # Creative Director
│   │   ├── commercial_agent.py     # Commercial Agent
│   │   ├── graph.py                # Définition du LangGraph
│   │   ├── inference.py            # FluxImageClient + SDXLImageClient (HuggingFace)
│   │   ├── telegram_service.py     # sendMessage + sendPhoto (URL & bytes)
│   │   ├── self_correct.py         # Auto-correction JSON
│   │   ├── document_processor.py   # Extraction PDF/TXT (RAG)
│   │   ├── consumers.py            # WebSocket (Django Channels)
│   │   ├── views.py
│   │   └── urls.py
│   ├── product_audit/              # Module Firecrawl + Gemini
│   │   ├── services/
│   │   │   ├── firecrawl_client.py
│   │   │   ├── gemini_client.py
│   │   │   ├── qdrant_client.py
│   │   │   └── orchestrator.py
│   │   ├── views.py
│   │   └── urls.py
│   ├── manage.py
│   └── requirements.txt
│
├── frontend/                       # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx          # Providers (ThemeProvider, etc.)
│   │   │   ├── globals.css         # Tailwind v4 + dark mode variant
│   │   │   ├── onboarding/         # Tunnel ADK (session guard)
│   │   │   └── dashboard/          # Pages par étape (ideation, SWOT, BMC…)
│   │   ├── components/
│   │   │   ├── app-sidebar.tsx     # Sidebar unifiée (étapes + historique marketing)
│   │   │   ├── site-header.tsx     # Header (i18n + theme toggle)
│   │   │   ├── nav-main.tsx        # Navigation avec statuts (locked/available/completed)
│   │   │   └── ui/                 # shadcn/ui components
│   │   ├── context/
│   │   │   └── AppContext.jsx      # État global (langue, thème, historique)
│   │   ├── pages/
│   │   │   ├── AgentPage.jsx       # Dashboard principal analyse stratégique (5 agents)
│   │   │   └── Dashboard.jsx       # Landing dashboard (session guard)
│   │   └── services/
│   │       └── agents.ts           # API calls + WorkflowStatus
│   ├── package.json
│   └── tsconfig.json
│
├── .gitignore
└── README.md
```

---

## Installation & Lancement

### Prérequis

- Python 3.11+
- Node.js 18+
- npm ou yarn

### 1. Backend (Django — port 8000)

```bash
# Cloner le dépôt et aller dans le dossier backend
git clone https://github.com/fattoumAchref/StartWise-ai-project.git
cd startwise/backend

# Créer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Remplir .env (voir section Configuration)

# Appliquer les migrations
python manage.py migrate

# Lancer le serveur
python manage.py runserver 0.0.0.0:8000
```

### 2. Frontend (Next.js — port 3000)

```bash
cd startwise/frontend

# Installer les dépendances
npm install

# Lancer en développement
npm run dev
```

L'application est accessible sur **http://localhost:3000**

---

## Configuration (.env)

Créer un fichier `.env` dans `backend/` avec les clés suivantes :

```env
# Django
SECRET_KEY=votre_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# LLM — Groq (agents stratégiques)
GROQ_API_KEY=votre_clé_groq

# LLM — Google (module idéation + product audit)
GOOGLE_API_KEY=votre_clé_google_ai
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Image Generation — HuggingFace (FLUX.1-schnell + SDXL)
HF_TOKEN=votre_token_huggingface
# ou
HUGGINGFACE_API_KEY=votre_token_huggingface

# Telegram Bot (envoi du rapport + prototype)
TELEGRAM_BOT_TOKEN=votre_token_bot_telegram
TELEGRAM_CHAT_ID=votre_chat_id_telegram

# Firecrawl (module product audit)
FIRECRAWL_API_KEY=votre_clé_firecrawl

# Email outreach (module Reach to Investors)
RESEND_API_KEY=votre_clé_resend
HUNTER_API_KEY=votre_clé_hunter

# Qdrant (vectorDB)
QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=votre_clé_qdrant   (optionnel en local)

# Base de données (prod — décommenter si PostgreSQL)
# DATABASE_URL=postgresql://user:password@localhost:5432/startwise
```

---

## Équipe

Projet réalisé dans le cadre du **Hackathon Google ADK** — ESPRIT School of Engineering

| Nom | Rôle |
|---|---|
| **gninediarra** | Développeur Full-Stack — Architecture, intégration frontend/backend, agents LangGraph & ADK, image IA, Telegram |

---

*StartWise — De l'idée à la stratégie, propulsé par l'IA.*
