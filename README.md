# StartWise — Plateforme Multi-Agents IA pour Startups

> Plusieurs agents IA autonomes collaborent pour analyser une startup : viabilité financière, intelligence marketing, idéation et audit produit — le tout en langage naturel.

---

## Modules de la plateforme

| Module | Description | Responsable |
|---|---|---|
| **CFO Financier** | Analyse financière complète + recommandation investissement | Notre équipe |
| **Marketing Intelligence** | 5 agents LangGraph : Trend → Vision → Émotion → Créatif → Commercial | Collègues |
| **Idéation** | Tunnel Q&A ADK → résumé business + logo + image | Collègues |
| **Product Audit** | Scraping Firecrawl → Gemini embed → Qdrant → rapport concurrentiel | Collègues |

---

## Ce que fait le module CFO

Un fondateur décrit sa startup en langage naturel :

> *"SaaS B2B, 12 clients à 800 TND/mois, churn 2%, burn rate 5 000 TND/mois, trésorerie 45 000 TND, je cherche à lever 95 000 TND."*

Le système répond avec :

- KPIs calculés (runway, LTV/CAC, gross margin, MRR, breakeven)
- 3 scénarios de projection sur 24 mois (pessimiste / réaliste / optimiste)
- Simulation Monte Carlo (probabilité de survie à 12 mois sur 1 000 tirages)
- Prévision de saisonnalité sectorielle (calendrier MENA)
- Benchmarks sectoriels comparatifs (RAG ChromaDB + Tavily)
- Recommandation d'investissement autonome : **STRONG_BUY / BUY / HOLD / PASS** avec valorisation, dilution cap table et scénario de financement optimal

---

## Stack Technique

| Couche | Technologie | Port |
|---|---|---|
| Frontend | Next.js · React 19 · TypeScript · Tailwind CSS | **3000** |
| Backend API | Django 5 · Daphne (ASGI) | **8000** |
| Finance A2A Server | FastAPI · Uvicorn | **8001** |
| Investment A2A Server | FastAPI · Uvicorn | **8002** |
| Bus de Communication | FastAPI · Redis pub-sub | **8765** |
| Question Agent (Idéation) | ADK standalone | **8101** |
| Research Agent (Idéation) | ADK standalone | **8102** |
| Formulator Agent (Idéation) | ADK standalone | **8103** |
| Sessions / État | Redis (pickle) | **6379** |
| Vectorstore Product Audit | Qdrant (Docker) | **6333** |

---

## Démarrage Rapide

### Prérequis

- Python 3.10+, Node.js 18+
- Redis en cours d'exécution (`redis-server` ou Docker)
- Docker (pour Qdrant — module Product Audit uniquement)
- Accès réseau ESPRIT (pour `tokenfactory.esprit.tn`)

### Installation

```bash
# 1. Dépendances Python agents
pip install -r requirements-agents.txt

# 2. Dépendances Django backend
pip install -r backend/requirements-base.txt

# 3. Base de données Django
cd backend && python manage.py migrate && cd ..

# 4. Dépendances frontend
cd frontend && npm install && cd ..
```

### Configuration `.env` (à la racine du projet)

```env
# LLM principal — obligatoire
ESPRIT_API_KEY=sk-...
ESPRIT_BASE_URL=https://tokenfactory.esprit.tn/api
ESPRIT_MODEL=hosted_vllm/Llama-3.1-70B-Instruct
ESPRIT_VERIFY_SSL=false

# Communication inter-agents
A2A_BUS_URL=http://localhost:8765

# Idéation (collègues)
OPENAI_API_KEY=sk-...
OPENROUTER_API_KEY=sk-or-...
QUESTION_AGENT_URL=http://localhost:8101
RESEARCH_AGENT_URL=http://localhost:8102
FORMULATOR_AGENT_URL=http://localhost:8103

# Product Audit (collègues)
FIRECRAWL_API_KEY=fc-...
GEMINI_API_KEY=...
QDRANT_URL=http://localhost:6333

# Optionnel — benchmarks web temps réel
# TAVILY_API_KEY=tvly-...
```

### Lancement

```bash
start.bat    # lance tous les processus → ouvrir http://localhost:3000
```

| # | Processus | Port |
|---|---|---|
| 1 | Redis (Docker) | 6379 |
| 2 | A2A Bus | 8765 |
| 3 | Finance A2A Server | 8001 |
| 4 | Investment A2A Server | 8002 |
| 5 | Django Backend | 8000 |
| 6 | Next.js Frontend | 3000 |
| 7 | Question Agent | 8101 |
| 8 | Research Agent | 8102 |
| 9 | Formulator Agent | 8103 |

---

## Architecture — Module CFO

### Vue d'ensemble

```
Fondateur (navigateur)
        │ texte naturel
        ▼
  Next.js Frontend :3000
        │ POST /api/cfo/chat  [X-Session-ID]
        ▼
  Django Backend :8000  (backend/cfo/)
        │
        ├─ parser.py (LLM) → FinancialContext
        ├─ validator.py     → ValidationResult
        ├─ pipeline.py      → KPIs + scénarios + Monte Carlo + saisonnalité
        ├─ fetch_benchmarks → ChromaDB + Tavily
        └─ confidence_a2a   → broadcast A2A
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          Finance A2A :8001             Investment A2A :8002
          FinanceAgent                  InvestmentBusAdapter
                    │                               │
                    └──── A2A Bus :8765 / Redis ────┘
                                    │
                          Redis state (pickle, TTL 24h)
                                    │
                          polling toutes 2s
                                    │
                         Next.js affiche le résultat
```

### Principe fondamental

> **Le LLM ne calcule jamais.** Il raisonne (décisions, questions, classification). Les chiffres sont produits par du Python pur, auditable et reproductible.

---

## Agent Finance — Boucle Autonome

**Fichier :** `finagents/finance/agent.py`

```
Input fondateur
      │
  [LLM] parse_founder_input()      → FinancialContext
      │
  validate_inputs()                → ValidationResult
      │
      ▼
*** DÉCISION 1 (LLM) ***
"Ai-je assez de données pour une analyse fiable ?"
  → NON : questions contextuelles → input-required  (max 2 rounds)
  → OUI : continue
      │
  fetch_benchmarks()               → RAG ChromaDB + Tavily
      │
  run_analysis_pipeline()          → 8 étapes déterministes
      │
      ▼
*** DÉCISION 2 (LLM) ***
"La confiance est-elle ≥ 35% ?"
  → NON : relance avec la donnée manquante la plus impactante
  → OUI : broadcast → tous les agents enregistrés → task.completed
```

### Pipeline Déterministe (8 étapes — zéro LLM)

| Étape | Module | Calcule |
|---|---|---|
| 1 | `validate_inputs` | Qualité, cohérence, champs manquants |
| 2 | `calculate_kpis` | Runway, LTV, CAC, Gross Margin, MRR |
| 3 | `route_by_phase` | Phase : SEED / TRACTION / FUNDRAISING |
| 4 | `scenario_projection` | Pessimiste / Réaliste / Optimiste × 24 mois |
| 5 | `monte_carlo` | P10/P50/P90, probabilité survie 12m (×1 000 simulations) |
| 6 | `seasonality_trend` | Saisonnalité + tendance (calendrier MENA) |
| 7 | `scenario_comparator` | KPIs vs benchmarks sectoriels |
| 8 | `confidence + A2A` | Score pondéré + message A2A pour les spécialistes |

**Score de confiance :**

| Composant | Poids |
|---|---|
| Qualité des données | 40% |
| Précision Monte Carlo `1 − (P90−P10)/P50` | 35% |
| Cohérence logique | 25% |

---

## Agent Investment — Le Spécialiste

**Fichier :** `finagents/investment/`

L'investment agent ne traite pas aveuglément chaque message. Il lit d'abord l'analyse et décide via LLM s'il a de la valeur à apporter (staying silent est une décision valide).

### Pipeline d'analyse (7 étapes)

```
FinancialContext reçu via A2A
  1. Validation input
  2. Détection stade (pre-seed / seed / série A)
  3. Calcul valorisation (DCF hybride + multiples sectoriels)
  4. Enrichissement benchmarks secteur
  5. Génération scénarios de financement (conservateur / réaliste / agressif)
  6. Sélection stratégie optimale (LLM scoring)
  7. Calcul dilution cap table
      ↓
  investment.recommendation → bus → Redis state → UI
```

### Output

```
rating:           STRONG_BUY | BUY | HOLD | PASS
confidence:       80%
valuation:        300 000 TND  (méthode: hybrid_dcf)
optimal_scenario: conservative
  raise_amount:   95 450 TND
  dilution:       15.1%
  post_money:     395 450 TND
founder_after:    81.1%
```

---

## Protocole A2A — Communication Inter-Agents

**Standard :** Google Agent-to-Agent Protocol (A2A)

Les agents ne se connaissent pas directement — l'agent finance **broadcast** sur le bus et chaque spécialiste décide lui-même d'engager. Ajouter un agent risk = une env var, zéro modification de code.

### Transport : LPUSH → BRPOP (Redis)

```
Publication  : LPUSH a2a:{destinataire}:inbox {message}
Réception    : BRPOP a2a:{destinataire}:inbox timeout=5s
```

### Endpoints du bus (:8765)

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/publish` | Envoyer vers `to: [agent_id]` |
| `GET` | `/inbox/{id}` | Lire les messages |
| `POST` | `/inbox/{id}/pop` | Lire + supprimer |
| `GET` | `/log` | 500 derniers événements |

### Clés Redis

```
a2a:{id}:inbox                        messages entrants (TTL 1h)
django:app_state:{session_id}         session utilisateur pickled (TTL 24h)
```

---

## Backend Django — Endpoints CFO

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/api/cfo/chat` | Message principal du fondateur |
| `GET` | `/api/cfo/state` | État session complet |
| `GET` | `/api/cfo/a2a/state` | Résultats des agents spécialistes |
| `POST` | `/api/cfo/whatif` | Simulation hypothétique |
| `POST` | `/api/cfo/pdf` | Export rapport PDF |
| `POST` | `/api/cfo/upload` | Upload PDF/CSV pour extraction |
| `POST` | `/api/cfo/benchmarks` | Lancer les benchmarks sectoriels |
| `POST` | `/api/cfo/new-conversation` | Nouvelle conversation |
| `GET` | `/api/cfo/conversations` | Historique conversations |
| `DELETE` | `/api/cfo/reset` | Reset session complète |

**Session :** identifiée par `X-Session-ID` (localStorage côté client), pickled dans Redis, TTL 24h.

---

## Où est utilisé le LLM

| Fichier | Rôle du LLM |
|---|---|
| `finagents/finance/tools/parser.py` | Texte / PDF / CSV → `FinancialContext` structuré |
| `finagents/finance/agent.py` DP1 | "Ai-je assez de données ?" → questions contextuelles |
| `finagents/finance/agent.py` DP2 | "Confiance suffisante ?" → donnée manquante la plus impactante |
| `finagents/finance/bus_publisher.py` | Classification intent + réponses auto aux clarifications |
| `finagents/investment/bus_adapter.py` | Décision d'engagement + détection red flags |
| `finagents/investment/strategy_selector.py` | Sélection stratégie de financement optimale |
| `backend/cfo/cfo_engine.py` | Réponses conversationnelles + parsing what-if |

---

## Métriques d'Évaluation

**Fichier :** `finagents/finance/evaluation.py`

### Métriques Agentiques

| Métrique | Formule | Ce qu'elle mesure |
|---|---|---|
| **TSR** Task Success Rate | `1.0=completed · 0.5=input-required · 0.0=failed` | Mission accomplie ? |
| **GPS** Goal Progress Score | `sous-objectifs atteints / total` | Proportion du pipeline complétée |
| **TCA** Tool Call Accuracy | `appels réussis / total` | Fiabilité des outils |
| **HR** Hallucination Rate | `claims non supportés / total (±15%)` | Invente-t-il des chiffres ? |
| **ES** Efficiency Score | `min_rounds / actual_rounds` | Efficacité conversationnelle |

### RAGAS-style (RAG Benchmarks)

| Métrique | Description |
|---|---|
| **Faithfulness** | Les chiffres LLM = KPIs calculés réels |
| **Answer Relevance** | Runway, revenu, risque, confiance, recommandation couverts |
| **Context Recall** | Benchmarks récupérés couvrent bien le secteur |
| **Context Precision** | Benchmarks effectivement utilisés dans le comparateur |

---

## Structure des Fichiers

```
finAgent/
│
├── backend/                          Django REST API
│   ├── startwise/
│   │   ├── settings.py               Config globale (Redis, CORS, apps)
│   │   ├── urls.py                   Routage global
│   │   └── asgi.py                   Daphne ASGI + boot singletons
│   │
│   ├── cfo/                          NOTRE module CFO
│   │   ├── views.py                  Endpoints REST CFO
│   │   ├── cfo_engine.py             Moteur principal (parse → pipeline → A2A)
│   │   ├── session_manager.py        Redis pickle sessions + singletons agents
│   │   ├── serializers.py            Sérialisation JSON (bench, ctx, kpis...)
│   │   ├── formatters.py             Markdown narratif + parse_docs_extra
│   │   └── urls.py                   Routes /api/cfo/
│   │
│   ├── agents/                       Collègues — Marketing LangGraph
│   ├── ideation/                     Collègues — Idéation ADK
│   └── product_audit/                Collègues — Product Audit Gemini+Qdrant
│
├── finagents/                        NOS agents autonomes
│   ├── finance/
│   │   ├── agent.py                  FinanceAgent (boucle DP1/DP2)
│   │   ├── a2a_server.py             FastAPI :8001
│   │   ├── bus_publisher.py          FinanceCommAgent (thread A2A)
│   │   ├── evaluation.py             TSR · GPS · TCA · HR · ES · RAGAS
│   │   ├── calcul_tools/
│   │   │   ├── pipeline.py           Orchestrateur 8 étapes
│   │   │   ├── calculate_kpis.py
│   │   │   ├── monte_carlo.py
│   │   │   ├── scenario_projection.py
│   │   │   ├── seasonality_trend.py
│   │   │   ├── scenario_comparator.py
│   │   │   └── validate_inputs.py
│   │   └── tools/
│   │       ├── parser.py             LLM → FinancialContext
│   │       ├── fetch_benchmarks.py   RAG ChromaDB + Tavily
│   │       ├── confidence_a2a.py     Score confiance + message A2A
│   │       └── pdf_report.py         Export PDF ReportLab
│   │
│   ├── investment/
│   │   ├── main.py                   InvestmentAgent (pipeline 7 étapes)
│   │   ├── bus_adapter.py            Thread BRPOP + LLM engagement
│   │   ├── a2a_server.py             FastAPI :8002
│   │   ├── valuation_engine.py       DCF hybride + multiples sectoriels
│   │   ├── strategy_selector.py      LLM sélection stratégie
│   │   ├── dilution_calculator.py    Cap table
│   │   └── memory/
│   │       ├── store.py              SQLite cross-session
│   │       └── comparator.py         Comparaison analyses historiques
│   │
│   └── models/
│       └── data_models.py            FinancialContext · KPIResult · Phase · etc.
│
├── frontend/src/
│   ├── app/
│   │   ├── page.tsx                  Landing page
│   │   ├── onboarding/               Tunnel idéation ADK
│   │   └── dashboard/
│   │       ├── page.tsx              Dashboard marketing
│   │       ├── ideation/             Résumé idéation + logo
│   │       ├── product-audit/        Rapport audit produit
│   │       └── viability-assessment/ NOTRE page CFO
│   │
│   ├── components/
│   │   ├── cfo/                      NOS composants CFO
│   │   │   ├── Charts.tsx            Scénarios · Monte Carlo · Saisonnalité · Benchmark
│   │   │   ├── KPICards.tsx          Cartes métriques financières
│   │   │   └── A2APanel.tsx          Panel recommandation investment agent
│   │   ├── landing/                  Page d'accueil
│   │   ├── ui/                       Composants shadcn/ui
│   │   └── app-sidebar.tsx           Sidebar principale
│   │
│   ├── services/
│   │   ├── cfo.ts                    API layer → Django /api/cfo/*
│   │   ├── ideation.ts               API layer → /ideation/*
│   │   ├── productAudit.ts           API layer → /product-audit/*
│   │   └── agents.ts                 API layer → marketing agents
│   │
│   └── lib/
│       ├── types.ts                  Types TypeScript partagés
│       └── utils.ts                  Utilitaires
│
├── a2a_bus/
│   ├── bus_server.py                 FastAPI Redis :8765
│   └── bus_client.py                 Client Python
│
├── chroma_db/                        Vectorstore benchmarks RAG
├── data/                             Cache saisonnalité + benchmarks JSON
├── .env                              Clés API + URLs agents
├── start.bat                         Lance tous les processus
├── requirements-agents.txt           Dépendances agents Python
├── backend/requirements-base.txt     Dépendances Django
└── CLAUDE.md                         Référence architecture complète
```

---

## Choix de Design

**Pourquoi le LLM ne calcule-t-il jamais ?**
Un LLM peut halluciner 5% d'erreur sur un runway — inacceptable pour des décisions financières. Le pipeline déterministe garantit des chiffres reproductibles et auditables.

**Pourquoi A2A et pas des appels directs ?**
Les appels directs créent du couplage fort. Avec A2A, l'agent finance broadcast et chaque spécialiste décide lui-même d'engager. Ajouter un agent risk = une env var, zéro code.

**Pourquoi Redis + pickle pour les sessions ?**
Les dataclasses Python (`FinancialContext`, `KPIResult`) sont préservées telles quelles — zéro mapping, zéro perte de type. TTL 24h suffit pour une session de travail.

**Pourquoi X-Session-ID et pas les cookies Django ?**
Le header custom depuis localStorage est stateless et fonctionne sans configuration TLS/HTTPS en développement.
