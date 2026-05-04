# StartWise / FinAgent — Multi-Agent AI Platform for Startups

**Keywords:** multi-agent AI, startup viability, financial analysis, investment recommendation, risk scoring, legal compliance Tunisia, marketing intelligence, A2A agent protocol, JSON-RPC, Redis, FastAPI, Django, Next.js, LangGraph, RAG, FAISS, Monte Carlo simulation, Tunisia startups, B2B SaaS, automation, API, ESPRIT TokenFactory, **Esprit School of Engineering**

> Plateforme open source où plusieurs agents IA spécialisés collaborent (bus A2A, tâches JSON-RPC, sessions Redis) pour accompagner une startup : finance, investissement, risque, juridique tunisien, marketing, idéation et audit produit — en langage naturel, avec une UI Next.js guidée par parcours utilisateur.

---

## Overview

**StartWise** (dépôt racine **finAgent**) est un projet de recherche et d’ingénierie développé dans le cadre des enseignements et projets à **Esprit School of Engineering** (Tunisie). Il combine :

- un **pipeline financier déterministe** (pas de calcul d’argent par LLM) ;
- des **agents spécialisés** (investissement, risque, juridique, marketing) reliés par un **bus A2A** et des **serveurs A2A FastAPI** (protocole JSON-RPC de type `tasks/send`) ;
- un **frontend** (Next.js, App Router) avec parcours progressif (idéation → outils → synthèse marketing / investisseurs).

L’objectif est double : **outil utilisable** par un fondateur, et **base technique** pour des contributeurs (architecture claire, points d’extension documentés).

---

## Features

| Domain | Capabilities |
|--------|----------------|
| **Financial viability (CFO)** | Extraction structurée des messages (LLM), validation, KPIs (runway, LTV/CAC, MRR, marge), 3 scénarios × 24 mois, Monte Carlo (probabilité de survie 12 mois), benchmarks sectoriels (RAG / Chroma + recherche web), score de confiance, **diffusion A2A** vers investissement, risque, marketing, juridique. |
| **Investment agent** | Analyse levée / dilution / valorisation (TND), notation **STRONG_BUY / BUY / HOLD / PASS**, clarifications autonomes si drapeaux rouges, publication `investment.recommendation` sur le bus. Les **conflits inter-agents** signalés par le risque vont dans un message dédié `investment.conflict_stance` (stocké à part) — **pas** comme texte de recommandation principal. |
| **Risk agent** | **HTTP A2A** (`tasks/send`) : risque global fusionné (Monte Carlo multi-agents, score de conflit, incertitude, RAG **FAISS** sur cas d’échec, scores SQL secteur, risques par domaine marketing / juridique / investissement), liste de conflits, cas similaires, métriques d’ablation et de stabilité. **Adaptateur bus** : consommation d’analyses financières, publication `risk.assessment`, rapports de conflit vers l’investissement. |
| **Legal advisor (LexWise)** | RAG Qdrant (collections juridiques tunisiennes), Claude + embeddings + reranker, modules création, IP, contrats, levée, conformité — API sous Django (`/legal/`). |
| **Marketing intelligence** | Chaîne d’agents (LangGraph) : tendance, vision, émotion, créatif, commercial — intégration Django. |
| **Ideation** | Agents ADK (question, recherche, formulator) — ports 8101–8103. |
| **Product audit** | Scraping, embeddings, Qdrant, rapport concurrentiel. |

---

## Tech Stack

### Frontend

- **Next.js** (App Router), **React**, **TypeScript**
- **Tailwind CSS**, composants UI (sidebar, dashboard)
- Appels **REST** au backend Django (`/api/cfo/*`, etc.) et **JSON-RPC** direct vers le Risk Agent (port 8003) depuis la page Risque
- Parcours utilisateur : déverrouillage après idéation (`localStorage`), pages **Viabilité financière**, **Investissement**, **Risque**, **LexWise**, **Go to Market**, **Reach to Investors** (ancre dashboard)

### Backend

- **Django 5** + **Daphne (ASGI)** — API session CFO, marketing, idéation, legal, product audit (**port 8000**)
- **FastAPI** + **Uvicorn** — serveurs A2A : Finance **8001**, Investment **8002**, Risk **8003**
- **Redis** — files d’attente `a2a:{agent_id}:inbox`, hash d’état `a2a:{agent_id}:state`, sessions Django (pickle)
- **PostgreSQL** + SQLAlchemy async (Legal Advisor)
- **Qdrant** — recherche vectorielle (legal, product audit)
- **ChromaDB** — benchmarks / documents CFO (selon configuration)
- **FAISS** + **sentence-transformers** — RAG cas startups échouées (Risk Agent)
- **SQLite** — scores sectoriels (`riskAgent/data`)

### Other tools & integrations

- **ESPRIT TokenFactory** (`tokenfactory.esprit.tn`) — LLM hébergé (variables `ESPRIT_*`)
- **Anthropic / OpenAI / Cohere** — selon modules (legal, embeddings, reranking)
- **Docker** — Redis, Qdrant (voir `start.bat`)
- **httpx**, **numpy** — bus HTTP, simulations Monte Carlo

---

## Architecture & agent logic

### High-level data flow

```
Founder UI (Next.js :3000)
    │  HTTP + session header
    ▼
Django (:8000)  →  CFO engine  →  Finance pipeline  →  A2A publish (bus :8765)
                              │
                              ├→ FinanceCommAgent (thread)  →  Redis state  →  GET /api/cfo/a2a/state
                              │
                              └→ Inboxes: investment_agent, risk_agent, legal_agent, marketing_agent …
                                      │
                                      ▼
                              FastAPI A2A servers (:8001 / :8002 / :8003)  ←  JSON-RPC tasks/*
```

### CFO / Finance agent (`finagents/finance/`)

1. **Parser (LLM)** : extrait burn, MRR, churn, secteur, etc. depuis le texte fondateur.
2. **Validateur** : qualité des données, champs manquants.
3. **Pipeline déterministe** (ordre logique) : `validate_inputs` → `calculate_kpis` → `route_by_phase` → `scenario_projection` → `monte_carlo` → `seasonality_trend` → `scenario_comparator` → **confidence** puis **message A2A** vers le bus.
4. **Décision** : aucun KPI monétaire n’est « inventé » par le LLM ; les scénarios et la survie Monte Carlo sont **reproductibles**.

### Finance communication agent (`FinanceCommAgent`, `bus_publisher.py`)

- **Classification d’intent** sur le type de message (`recommendation`, `clarification_request`, `assessment`, `error`, `conflict_stance`, …) puis dispatch.
- **Stockage générique** : `{sender_id}_recommendation`, `{sender_id}_rating`, etc.
- **Clés legacy** pour l’UI : `investment_rating`, `investment_recommendation`, `risk_level`, …
- **Messages `investment.conflict_stance`** : détectés explicitement (et par heuristique sur le contenu) ; seuls `investment_conflict_stance*` sont mis à jour — **les champs de verdict d’investissement ne sont pas écrasés** par le texte de conflit.

### Investment agent (`finagents/investment/`)

- **Engagement** : le bus adapter peut refuser d’analyser si le payload financier est vide (LLM d’engagement + garde-fous).
- **Rounds** : analyse financière → éventuellement **clarification** (`investment.clarification_request`) → réponse → **`investment.recommendation`** avec données structurées (valorisation, scénario optimal, dilution).
- **Conflits (risk)** : sur `risk.conflict_report`, publication d’un **`investment.conflict_stance`** (note dans `payload.data.note`) — information pour la page **Risque** et l’état session, distincte de la recommandation.

### Risk agent (`StartWise-integration/backend/riskAgent/`)

- **Entrée A2A** : `tasks/send` avec `description`, `sector`, `country`, optionnellement `agent_outputs` (claims multi-agents).
- **Signaux fusionnés** : Monte Carlo (tirages multi-agents), score de conflit, incertitude, RAG, SQL secteur, risques marketing / juridique / investissement → **fusion pondérée** par confiance.
- **Métriques** : variance de stabilité (`STABILITY_RUNS`), ablation leave-one-out, densité de conflits, liste de conflits (LLM + règles si ≥ 2 agents).

### Legal, marketing, ideation, product audit

- **Legal** : pipeline RAG (reformulation → retrieval Qdrant → rerank Cohere → génération Claude), intégré Django.
- **Marketing** : graphe multi-nœuds (LangGraph), résultats agrégés côté dashboard marketing.
- **Ideation** : pipeline ADK multi-services.
- **Product audit** : enrichissement données + Qdrant + rapport.

---

## Communication & A2A protocol

### Message bus (HTTP + Redis fallback)

| Operation | Description |
|-----------|-------------|
| `POST /publish` | Publie un message JSON vers les `to: [agent_id, …]` (HTTP vers `A2A_BUS_URL`, ou LPUSH Redis sur `a2a:{id}:inbox`). |
| `POST /inbox/{agent_id}/pop` | Consommation (tests / debug). |
| `GET /health` | Santé du bus. |

Chaque agent **écoute** sa file Redis ; le **FinanceCommAgent** (côté Django) met à jour le **hash d’état** partagé lu par `GET /api/cfo/a2a/state`.

### JSON-RPC 2.0 (Finance, Investment, Risk servers)

Méthodes supportées (schéma commun) :

- **`tasks/send`** — crée ou continue une tâche (`input-required` pour clarifications finance).
- **`tasks/get`**, **`tasks/cancel`**, **`tasks/sendSubscribe`** — suivi / annulation / streaming selon implémentation.

Exemple minimal (Risk) :

```json
{
  "jsonrpc": "2.0",
  "id": "uuid",
  "method": "tasks/send",
  "params": {
    "id": "task-uuid",
    "message": {
      "role": "user",
      "parts": [{ "type": "data", "data": { "description": "…", "sector": "SaaS", "country": "Tunisia", "agent_outputs": [] } }]
    }
  }
}
```

Réponse : tâche avec `artifacts` (ex. `risk_report` en `DataPart`).

Documentation complémentaire : [`docs/a2a_integration_guide.md`](docs/a2a_integration_guide.md), [`CLAUDE.md`](CLAUDE.md).

---

## UI / UX & user guidance

- **Parcours** : idéation complétée (`startwise_summary`) ou bouton **Unlock all tools** → accès Product Audit, Finance, Investment, Risk, LexWise, Go to Market, **Reach to Investors** (lien vers `/dashboard#reach-investors`).
- **CFO** : conversation, graphiques, benchmarks, état A2A (polling / WebSocket selon build).
- **Investment** : panneau **A2APanel** — affiche la **recommandation** et les chiffres (valorisation, scénario) ; les alertes de conflit détaillées sont orientées vers la **page Risque**.
- **Risk** : formulaire description + secteur + pays, analyse JSON-RPC, cartes diagnostics (fusion, ablation, RAG, conflits), aperçu session live (`getA2AState`).
- **Accessibilité** : libellés français pour les cotes (ex. « Favorable »), mode expert possible sur certains composants.

---

## Evaluation metrics (résumé)

| Zone | Métrique / usage |
|------|------------------|
| **Finance** | KPIs explicites, probabilité survie 12 mois (Monte Carlo), score de **confiance** pondéré (cohérence données, benchmarks, scénarios). |
| **Investment** | `confidence_score` → notation STRONG_BUY … PASS ; scénarios et dilution cohérents avec les entrées. |
| **Risk** | `global_risk` (fusion), intervalle de confiance Monte Carlo sur taux d’échec simulé, `conflict_score`, `uncertainty`, scores RAG / secteur / par agent, **stabilité** (variance des fusions resamplées), **ablation** (sensibilité par signal retiré). |
| **Legal** | Score conformité, traçabilité des sources (JORT, INNORPI, etc.). |
| **Qualité produit** | Tests manuels par parcours ; bus `GET /health` ; endpoints `/health` des serveurs A2A. |

---

## Directory structure (indicative)

```
finAgent/
├── start.bat                    # Windows: bus, agents A2A, Django, Next.js
├── .env.example
├── requirements-agents.txt      # Python agents (racine venv)
├── a2a_bus/                     # FastAPI bus :8765
├── finagents/
│   ├── finance/                 # FinanceAgent, pipeline, a2a_server :8001, bus_publisher
│   └── investment/              # InvestmentAgent, bus_adapter, a2a_server :8002
├── backend/                     # Django (racine legacy) — marketing, ideation, cfo si présent
├── chroma_db/                   # Persistance Chroma (si utilisée)
├── docs/
├── StartWise-integration/
│   ├── frontend/                # Next.js :3000 (dashboard, risk, investment, lexwise, …)
│   └── backend/
│       ├── riskAgent/           # Risk A2A :8003, RAG FAISS, SQL sectoriel
│       ├── legal_advisor/
│       ├── cfo/                 # Vues API CFO, session Redis, WebSocket A2A
│       ├── ideation/
│       ├── agents/              # Marketing LangGraph
│       └── finagents/           # Copie / import finance-investment alignée déploiement
└── README.md
```

---

## Getting started

### Prerequisites

- **Python 3.10+**, **Node.js 18+**
- **Redis** (Docker recommandé, voir `start.bat`)
- **Docker** pour **Qdrant** (Legal + Product audit)
- Accès réseau **Esprit School of Engineering** / **TokenFactory** si utilisation des LLM ESPRIT

### Installation

```bash
pip install -r requirements-agents.txt
pip install -r backend/requirements-base.txt
pip install -r StartWise-integration/backend/requirements.txt

cd StartWise-integration/backend && python manage.py migrate
cd StartWise-integration/frontend && npm install
```

Copier **`.env.example`** → **`.env`** (racine). Variables typiques : `ESPRIT_API_KEY`, `ESPRIT_BASE_URL`, `A2A_BUS_URL`, `INVESTMENT_AGENT_URL`, `RISK_AGENT_URL`, clés Legal (Anthropic, Cohere, OpenAI) selon modules.

### Usage (Windows)

À la racine du dépôt :

```bat
start.bat
```

Puis ouvrir **http://localhost:3000** (frontend), **http://localhost:8000** (Django API, Legal sous `/legal/`).

| Service | Port |
|---------|------|
| Next.js frontend | **3000** |
| Django (CFO API, Legal, marketing, …) | **8000** |
| Finance A2A (FastAPI) | **8001** |
| Investment A2A (FastAPI) | **8002** |
| Risk A2A (FastAPI) | **8003** |
| A2A bus | **8765** |
| Redis | **6379** |
| Qdrant | **6333** |
| Ideation ADK agents | **8101–8103** |

### Quick A2A checks

```bash
curl http://localhost:8765/health
curl http://localhost:8003/health
curl http://localhost:8000/api/cfo/a2a/state   # avec en-tête session si requis
```

---

## Design choices (why)

| Choice | Rationale |
|--------|-----------|
| **Deterministic financial core** | Éviter les hallucinations sur runway, MRR ou marges — le LLM structure et explique, les calculs sont code + données. |
| **A2A bus + dedicated state** | Découplage des agents ; ajout d’un consommateur = configuration + inbox, sans refonte monolithique. |
| **Redis + pickle sessions** | Persistance rapide des objets Python (`FinancialContext`, …) pour le CFO Django. |
| **Separate conflict channel** | Cohérence UX : la **recommandation investissement** reste la sortie métier ; les **conflits** sont portés par le **Risk** et des champs session dédiés. |
| **Dual risk path** | Bus pour signaux temps réel ; **HTTP A2A** pour rapport complet interactif depuis l’UI. |

---

## Acknowledgments

Ce projet est réalisé dans le cadre des cours et projets de **software engineering**, **intelligence artificielle** et systèmes distribués à **[Esprit School of Engineering](https://esprit.tn)** (Tunisie), avec contributions d’équipes sur les modules marketing, idéation, audit produit et agent légal, et développement cœur CFO / A2A / risk / intégration StartWise.

Pour contribuer : respecter la structure des dossiers, documenter les nouveaux types de messages A2A, et lancer les tests / health checks des services avant une PR.

---

## See also

- [`docs/a2a_integration_guide.md`](docs/a2a_integration_guide.md) — intégration d’un nouvel agent A2A  
- [`CLAUDE.md`](CLAUDE.md) — notes d’architecture détaillées  
- [`StartWise-integration/backend/cfo/README.md`](StartWise-integration/backend/cfo/README.md) — module CFO Django  
