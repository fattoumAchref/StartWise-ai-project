# StartWise — Plateforme Multi-Agents IA pour Startups

> Plusieurs agents IA autonomes collaborent pour analyser une startup : viabilité financière, conseil juridique, intelligence marketing, idéation et audit produit — le tout en langage naturel.

---

## Modules de la plateforme

| Module | Description | Responsable |
|---|---|---|
| **CFO Financier** | Analyse financière complète + recommandation investissement | Notre équipe |
| **Legal Advisor** | Conseil juridique tunisien : création, IP, contrats, conformité | Salim |
| **Marketing Intelligence** | 5 agents LangGraph : Trend → Vision → Émotion → Créatif → Commercial | Collègues |
| **Idéation** | Tunnel Q&A ADK → résumé business + logo + image | Collègues |
| **Product Audit** | Scraping Firecrawl → Gemini embed → Qdrant → rapport concurrentiel | Collègues |

---

## Stack Technique

| Couche | Technologie | Port |
|---|---|---|
| Frontend | Next.js · React 19 · TypeScript · Tailwind CSS | **3000** |
| Backend API | Django 5 · Daphne (ASGI) | **8000** |
| Finance A2A Server | FastAPI · Uvicorn | **8001** |
| Investment A2A Server | FastAPI · Uvicorn | **8002** |
| Legal Advisor API | FastAPI · Uvicorn | **8003** |
| Bus de Communication | FastAPI · Redis pub-sub | **8765** |
| Question Agent (Idéation) | ADK standalone | **8101** |
| Research Agent (Idéation) | ADK standalone | **8102** |
| Formulator Agent (Idéation) | ADK standalone | **8103** |
| Sessions / État | Redis (pickle) | **6379** |
| Vectorstore Product Audit + Legal | Qdrant (Docker) | **6333** |

---

## Démarrage Rapide

### Prérequis

- Python 3.10+, Node.js 18+
- Redis en cours d'exécution (`redis-server` ou Docker)
- Docker (pour Qdrant)
- Accès réseau ESPRIT (pour `tokenfactory.esprit.tn`)

### Installation

```bash
# 1. Dépendances Python agents (Finance + Investment)
pip install -r requirements-agents.txt

# 2. Dépendances Django backend
pip install -r backend/requirements-base.txt

# 3. Dépendances Legal Advisor
pip install -r StartWise-integration/backend/requirements.txt

# 4. Base de données Django
cd backend && python manage.py migrate && cd ..

# 5. Dépendances frontend
cd frontend && npm install && cd ..
```

### Configuration `.env` (à la racine du projet)

Copier `.env.example` → `.env` et remplir les clés. Variables obligatoires :

```env
# LLM principal
ESPRIT_API_KEY=sk-...
ESPRIT_BASE_URL=https://tokenfactory.esprit.tn/api

# Agent légal
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...

# Communication inter-agents
A2A_BUS_URL=http://localhost:8765

# Idéation
OPENAI_API_KEY=sk-...
```

### Lancement

```bash
start.bat    # lance tous les processus → ouvrir http://localhost:3000
```

---

## Module CFO — Viabilité Financière

Un fondateur décrit sa startup :

> *"SaaS B2B, 12 clients à 800 TND/mois, churn 2%, burn rate 5 000 TND/mois, trésorerie 45 000 TND."*

Le système répond avec :

- KPIs calculés (runway, LTV/CAC, gross margin, MRR)
- 3 scénarios de projection × 24 mois (pessimiste / réaliste / optimiste)
- Simulation Monte Carlo (probabilité de survie 12 mois sur 1 000 tirages)
- Prévision de saisonnalité sectorielle (calendrier MENA)
- Benchmarks sectoriels (RAG ChromaDB + Tavily)
- Recommandation investissement : **STRONG_BUY / BUY / HOLD / PASS** + valorisation + dilution

### Architecture CFO

```
Fondateur
    │ POST /api/cfo/chat
    ▼
Django :8000 → parser (LLM) → validator → pipeline → benchmarks → confidence
                                                                         │
                                                               broadcast A2A bus
                                                               ┌─────────┴─────────┐
                                                     Finance :8001       Investment :8002
                                                                         Legal :8003
```

### Pipeline déterministe (zéro LLM pour les calculs)

| Étape | Ce qu'il calcule |
|---|---|
| `validate_inputs` | Qualité des données, champs manquants |
| `calculate_kpis` | Runway, LTV, CAC, Gross Margin, MRR |
| `route_by_phase` | SEED / TRACTION / FUNDRAISING |
| `scenario_projection` | 3 scénarios × 24 mois |
| `monte_carlo` | P10/P50/P90, probabilité survie 12m |
| `seasonality_trend` | Saisonnalité + calendrier MENA |
| `scenario_comparator` | vs benchmarks sectoriels |
| `confidence + A2A` | Score pondéré + broadcast |

### Endpoints CFO

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/api/cfo/chat` | Message fondateur |
| `GET` | `/api/cfo/state` | État session |
| `GET` | `/api/cfo/a2a/state` | Résultats agents spécialistes |
| `POST` | `/api/cfo/whatif` | Simulation hypothétique |
| `POST` | `/api/cfo/pdf` | Export PDF |
| `POST` | `/api/cfo/upload` | Upload PDF/CSV |
| `DELETE` | `/api/cfo/reset` | Reset session |

---

## Module Legal Advisor — Conseil Juridique Tunisien

**Fichiers :** `StartWise-integration/backend/legal_advisor/`

Conseiller juridique intelligent pour startups tunisiennes. Aucune connaissance juridique préalable requise.

| Module | Ce qu'il fait |
|---|---|
| **Création** | Choisit la forme juridique (SARL/SA/SUARL), génère les statuts et la checklist RNE |
| **Protection IP** | Vérifie disponibilité d'une marque à l'INNORPI (similarité phonétique), audite les licences logicielles |
| **Contrats** | Génère CDI, CDD, NDA, Prestation, Pacte d'actionnaires — détecte les clauses dangereuses |
| **Levée de fonds** | Explique BSA Air / Convertible / Equity, calcule la dilution, traduit un term sheet |
| **Conformité** | Score 0–100, alertes INPDP/CNSS/TVA/Travail, calendrier des échéances |

### Stack technique Legal Agent

- **LLM :** Claude Sonnet 4.6 (Anthropic)
- **Embeddings :** text-embedding-3-large (OpenAI)
- **Reranker :** rerank-multilingual-v3.0 (Cohere)
- **Vector Store :** Qdrant (6 collections)
- **Base de données :** PostgreSQL + SQLAlchemy async
- **API :** FastAPI :8003

### Workflow RAG Légal

```
Question fondateur
    │
    ▼ [Reformulateur] Claude décompose en N sous-requêtes Qdrant
    │
    ▼ [Retriever — parallèle] embed → search top-20 par collection
    │
    ▼ [Reranker Cohere] top-20 → top-5, pénalité textes abrogés
    │
    ▼ [Générateur Claude] prompt = chunks + sources + contexte
    │
    Réponse structurée : base légale + action recommandée + ⚖️ avocat si besoin
```

### Communication A2A avec le Legal Agent

Le Legal Agent reçoit les analyses financières du CFO via le bus A2A. Son inbox :

```
a2a:legal_agent:inbox   (bus: http://localhost:8765)
```

Pour envoyer une analyse vers le Legal Agent, le CFO inclut `"legal_agent"` dans le champ `to`.

### Sources légales

| Source | Données | Fréquence |
|---|---|---|
| JORT (legislation.tn) | Lois, décrets, arrêtés | Quotidienne |
| INNORPI | Marques déposées classes Nice 1–45 | Hebdomadaire |
| DGI | Taux TVA, IS, IRPP | Annuelle (après loi de finances) |
| CNSS | Taux cotisations | Annuelle |
| SPDX | Licences logicielles | Trimestrielle |

---

## Protocole A2A — Communication Inter-Agents

Le bus A2A est un routeur HTTP/Redis. Chaque agent a sa propre inbox. Pour intégrer un nouvel agent, voir [docs/a2a_integration_guide.md](docs/a2a_integration_guide.md).

```
Publication  : POST /publish  { "to": ["finance_agent", "legal_agent", ...] }
Réception    : POST /inbox/{agent_id}/pop
Bus health   : GET  /health
```

| Agent ID | Port | Inbox Redis |
|---|---|---|
| `finance_agent` | 8001 | `a2a:finance_agent:inbox` |
| `investment_agent` | 8002 | `a2a:investment_agent:inbox` |
| `legal_agent` | 8003 | `a2a:legal_agent:inbox` |

---

## Structure des Fichiers

```
finAgent/
│
├── backend/                          Django REST API
│   ├── cfo/                          Module CFO (notre équipe)
│   ├── agents/                       Marketing LangGraph (collègues)
│   ├── ideation/                     Idéation ADK (collègues)
│   └── product_audit/                Product Audit (collègues)
│
├── StartWise-integration/            Intégration Agent Légal (Salim)
│   └── backend/
│       ├── legal_advisor/            Agent légal Django app
│       │   ├── modules/              Création · IP · Contrats · Levée · Conformité
│       │   ├── rag/                  Pipeline RAG (reformulateur → retriever → reranker → générateur)
│       │   └── scrapers/             JORT · INNORPI · DGI · CNSS · SPDX
│       └── finagents/                Copie intégrée Finance + Investment
│
├── finagents/                        NOS agents autonomes
│   ├── finance/                      FinanceAgent + pipeline 8 étapes
│   └── investment/                   InvestmentAgent + pipeline 7 étapes
│
├── frontend/src/
│   ├── app/dashboard/
│   │   ├── viability-assessment/     Page CFO (notre équipe)
│   │   └── lexwise/                  Page Legal Advisor (Salim)
│   └── components/cfo/               Charts · KPICards · A2APanel
│
├── a2a_bus/                          Bus FastAPI + Redis :8765
├── docs/                             Guides d'intégration
├── .env.example                      Template variables d'environnement
├── start.bat                         Lance tous les processus
└── CLAUDE.md                         Référence architecture complète
```

---

## Choix de Design

**Pourquoi le LLM ne calcule-t-il jamais les KPIs ?**
Un LLM peut halluciner 5% d'erreur sur un runway — inacceptable pour des décisions financières. Le pipeline déterministe garantit des chiffres reproductibles.

**Pourquoi A2A et pas des appels directs ?**
Les appels directs créent du couplage fort. Avec A2A, chaque agent est indépendant. Ajouter un agent = une env var, zéro modification de code.

**Pourquoi Redis + pickle pour les sessions ?**
Les dataclasses Python (`FinancialContext`, `KPIResult`) sont préservées telles quelles — zéro mapping ORM, TTL 24h.

**Limites du Legal Advisor**
Les documents générés (statuts, pacte d'actionnaires) doivent être validés par un avocat avant toute signature. L'agent ne représente pas les parties devant les tribunaux.
