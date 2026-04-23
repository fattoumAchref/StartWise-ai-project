# StartWise — Système Multi-Agent d'Analyse Financière pour Startups

> Un fondateur décrit sa startup en langage naturel. En 30 secondes, plusieurs agents IA autonomes collaborent pour produire une analyse financière complète et une recommandation d'investissement.

---

## Ce que fait le système

Un fondateur tape par exemple :

> *"SaaS B2B, 12 clients à 800 TND/mois, churn 2%, burn rate 5 000 TND/mois, trésorerie 45 000 TND, je cherche à lever 95 000 TND."*

Le système répond avec :
- KPIs calculés (runway, LTV/CAC, gross margin, MRR)
- 3 scénarios de projection sur 24 mois (pessimiste / réaliste / optimiste)
- Simulation Monte Carlo (probabilité de survie à 12 mois sur 1 000 tirages)
- Prévision de saisonnalité sectorielle
- Benchmarks sectoriels comparatifs
- Recommandation d'investissement autonome : **STRONG_BUY / BUY / HOLD / PASS** avec valorisation, dilution cap table et scénario de financement optimal

---

## Stack Technique

| Couche | Technologie | Port |
|---|---|---|
| Frontend | Next.js 14 · React · TypeScript · Tailwind CSS | **3000** |
| Backend API | Django 5 · Django REST Framework · Daphne (ASGI) | **8000** |
| Finance A2A Server | FastAPI · Uvicorn | **8001** |
| Investment A2A Server | FastAPI · Uvicorn | **8002** |
| Bus de Communication | FastAPI · Redis pub-sub | **8765** |
| Sessions / État | Redis (pickle) | **6379** |

---

## Démarrage Rapide

### Prérequis
- Python 3.10+, Node.js 18+, Redis (`redis-server`)
- Accès réseau ESPRIT (pour `tokenfactory.esprit.tn`)

### Installation

```bash
# 1. Dépendances Python
pip install -r requirements.txt

# 2. Dépendances Django
pip install -r backend/requirements_django.txt

# 3. Base de données Django
cd backend && python manage.py migrate && cd ..

# 4. Dépendances frontend
cd frontend && npm install && cd ..
```

### Configuration `.env`

```env
ESPRIT_API_KEY=sk-...                        # clé API obligatoire
ESPRIT_BASE_URL=https://tokenfactory.esprit.tn/api
ESPRIT_MODEL=hosted_vllm/Llama-3.1-70B-Instruct
ESPRIT_VERIFY_SSL=false

A2A_BUS_URL=http://localhost:8765
INVESTMENT_AGENT_URL=http://localhost:8002

# Optionnel — pour les benchmarks web en temps réel
# TAVILY_API_KEY=tvly-...

# Ajouter un nouvel agent spécialiste : zéro code
# RISK_AGENT_URL=http://localhost:8003
```

### Lancement

```bash
start.bat    # lance les 6 processus → ouvrir http://localhost:3000
```

| # | Processus | Description |
|---|---|---|
| 1 | **A2A Bus** (8765) | Routeur de messages inter-agents |
| 2 | **Investment Bus Listener** | Thread BRPOP de l'investment agent |
| 3 | **Finance A2A Server** (8001) | API A2A de l'agent finance |
| 4 | **Investment A2A Server** (8002) | API A2A de l'agent investment |
| 5 | **Django Backend** (8000) | API REST + sessions + comm |
| 6 | **Next.js Frontend** (3000) | Interface utilisateur |

---

## Architecture — Comment ça marche

### Vue d'ensemble

```
Fondateur (navigateur)
        │ texte naturel
        ▼
  Next.js Frontend (3000)
        │ POST /api/chat  [X-Session-ID header]
        ▼
  Django Backend (8000)
        │
        ├─ parse → validate → pipeline → confidence
        │                                     │
        │                              broadcast A2A
        │                                     │
        ├──────────────────────────────────────┤
        │                                     │
  Finance A2A (8001)              Investment A2A (8002)
  FinanceAgent                    InvestmentBusAdapter
        │                                     │
        │  ←──── A2A Bus (8765) / Redis ─────→│
        │                                     │
  FinanceCommAgent thread          Pipeline 7 étapes
  (écoute + raisonne)                         │
        │                            recommendation
        │                            STRONG_BUY 80%
        │                                     │
        └──────── Redis state ────────────────┘
                       │
               polling toutes 2s
                       │
              Next.js affiche le résultat
```

### Principe fondamental

> **Le LLM ne calcule jamais.** Il raisonne (décisions, questions, classification). Les chiffres sont produits par du Python pur, auditable et reproductible.

---

## Agent Finance — Le Chef d'Orchestre

**Fichier :** `agents/finance/agent.py`

C'est un vrai agent autonome, pas un pipeline linéaire. Il a des buts, des décisions, et une mémoire de conversation.

### Boucle de raisonnement

```
Input fondateur
      │
  [LLM] parse_founder_input()
      │  extrait FinancialContext depuis langage naturel
      │
  validate_inputs()
      │
      ▼
*** DÉCISION 1 (LLM) ***
"Ai-je assez de données pour faire une analyse fiable ?"
  → NON : génère des questions contextuelles → attend le fondateur (input-required)
  → OUI : continue  [max 2 rounds de clarification]
      │
  fetch_benchmarks()
      │  RAG ChromaDB + Tavily (si dispo)
      │
  run_analysis_pipeline()
      │  8 étapes déterministes (voir ci-dessous)
      │
      ▼
*** DÉCISION 2 (LLM) ***
"La confiance dans l'analyse est-elle ≥ 35% ?"
  → NON : identifie la donnée manquante la plus impactante → relance
  → OUI : continue
      │
  broadcast → TOUS les agents enregistrés
      │
  task.completed
```

### Pipeline Déterministe (8 étapes)

Aucun LLM ici — uniquement des calculs Python :

| Étape | Module | Ce qu'il calcule |
|---|---|---|
| 1 | `validate_inputs` | Qualité, cohérence, champs manquants |
| 2 | `calculate_kpis` | Runway, LTV, CAC, Gross Margin, MRR, Churn |
| 3 | `route_by_phase` | Phase startup : SEED / TRACTION / FUNDRAISING |
| 4 | `scenario_projection` | Pessimiste / Réaliste / Optimiste × 24 mois |
| 5 | `monte_carlo` | P10/P50/P90, probabilité survie 12m (×1 000 simulations) |
| 6 | `seasonality_trend` | Saisonnalité + tendance (Prophet + calendrier MENA) |
| 7 | `scenario_comparator` | KPIs vs benchmarks sectoriels (si benchmarks dispo) |
| 8 | `confidence + A2A` | Score pondéré + message A2A pour les spécialistes |

**Score de confiance :**

| Composant | Poids |
|---|---|
| Qualité des données | 40% |
| Précision Monte Carlo `1 − (P90−P10)/P50` | 35% |
| Cohérence logique | 25% |

---

## Protocole A2A — Communication Inter-Agents

**Standard :** Google/IBM Agent-to-Agent Protocol (A2A)

### Pourquoi A2A et pas des appels directs ?

Les appels directs créent du couplage fort : si tu ajoutes un agent risk, tu dois modifier l'agent finance. Avec A2A, l'agent finance **broadcast** et chaque agent décide lui-même d'engager.

### Agent Card — Découverte automatique

Chaque agent expose `GET /.well-known/agent.json` :

```json
{
  "id": "investment_agent",
  "name": "Investment Analysis Agent",
  "skills": ["investment_analysis", "valuation", "funding_strategy"],
  "input_modes": ["data"],
  "output_modes": ["data", "text"]
}
```

L'`AgentRegistry` les lit au démarrage. Ajouter un agent = une env var :

```env
RISK_AGENT_URL=http://localhost:8003   # → risk_agent reçoit tous les broadcasts
```

**Zéro modification de code.**

### Dispatcher JSON-RPC 2.0 — `POST /`

```json
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "message": {
      "role": "agent",
      "parts": [{"type": "data", "mimeType": "application/json", "data": {...}}]
    }
  }
}
```

| Méthode | Description |
|---|---|
| `tasks/send` | Créer ou continuer une tâche |
| `tasks/get` | Lire état + artefacts |
| `tasks/cancel` | Annuler |
| `tasks/sendSubscribe` | Flux SSE temps-réel |

### États d'une tâche

```
submitted → working → completed
                ↕
          input-required   ← l'agent demande des données
                ↓
             failed / canceled
```

---

## Bus A2A — Transport des Messages

**Fichier :** `a2a_bus/`

Le bus est un serveur FastAPI (8765) qui s'appuie sur Redis.

### Transport : LPUSH → BRPOP

```
Publication  : LPUSH a2a:{destinataire}:inbox {message}
Réception    : BRPOP a2a:{destinataire}:inbox timeout=5s  (bloquant, zéro CPU)
```

Chaque agent a sa propre inbox. Le bus est juste un routeur — il ne lit pas les messages, il les distribue.

### Endpoints du bus

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/publish` | Envoyer un message vers `to: [agent_id]` |
| `GET` | `/inbox/{id}` | Lire les messages (non-destructif) |
| `POST` | `/inbox/{id}/pop` | Lire + supprimer |
| `POST` | `/inbox/{id}/ack/{msg_id}` | Acquitter |
| `GET` | `/log` | 500 derniers événements |

### Clés Redis

```
a2a:{id}:inbox                       → messages entrants (TTL 1h, LIFO)
a2a:{id}:state                       → état courant de l'agent (hash)
a2a:conversation:log                 → journal partagé sent+received
a2a:finance_agent:financial_context  → FinancialContext sérialisé (TTL 1h)
django:app_state:{session_id}        → session utilisateur pickled (TTL 24h)
```

---

## FinanceCommAgent — L'Intelligence de Communication

**Fichier :** `agents/finance/comm_agent.py`

Un thread démon autonome qui tourne dans le processus Django. Il écoute l'inbox de `finance_agent` et réagit aux messages de **tous** les agents spécialistes.

### Pourquoi ce composant existe

Quand l'investment agent pose des questions ou envoie une recommandation, quelqu'un doit répondre de façon autonome sans bloquer le thread principal. C'est le rôle du CommAgent.

### Ce qu'il fait

**Classification des messages (LLM si nécessaire) :**
```
Type string → heuristique rapide → intent
Si ambigu  → LLM lit le payload → intent
Intent : recommendation | clarification_request | assessment | error
```

**Chaîne de clarification complète :**

```
Round 1 : finance_agent  → investment_agent   [financial_analysis]
Round 2 : investment_agent → finance_agent    [investment.clarification_request]
           "Quel est votre MRR projeté à 6 mois ?"
Round 3 : finance_agent  → investment_agent   [finance.clarification_response]
           ┌─ LLM cherche la réponse dans le FinancialContext Redis
           ├─ Si trouvé : réponse précise avec les chiffres
           └─ Si non trouvé : "Procédez avec les données disponibles" (jamais bloqué)
Round 4 : investment_agent → finance_agent    [investment.recommendation]
           STRONG_BUY · confiance 80%
```

**Détection de conflits inter-agents :**
Quand plusieurs agents (investment + risk par exemple) ont des opinions contradictoires, le LLM les analyse ensemble et génère une alerte de conflit.

---

## Investment Agent — Le Spécialiste

**Fichier :** `agents/investment/`

### Décision d'engagement (LLM)

L'investment agent ne traite pas aveuglément chaque message. Il lit d'abord l'analyse financière et décide :

> *"Ces données sont-elles suffisantes pour évaluer le potentiel d'investissement ?"*

Si oui → il engage. Sinon → il ignore (pour les messages incomplets ou hors scope).

### Pipeline d'analyse (7 étapes)

```
FinancialContext reçu via A2A
  1. Validation input
  2. Détection stade (pre-seed / seed / série A)
  3. Calcul valorisation (DCF hybride + multiples sectoriels)
  4. Enrichissement benchmarks (données tunisiennes réelles)
  5. Génération scénarios de financement (conservateur / réaliste / agressif)
  6. Sélection stratégie optimale (scoring LLM)
  7. Calcul dilution cap table
      ↓
  investment.recommendation → bus → FinanceCommAgent → Redis state → UI
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

**Mémoire cross-session :** SQLite (`memory/investment_memory.db`) — compare les analyses successives pour détecter les améliorations ou régressions.

---

## Backend Django — La Couche API

**Fichier :** `backend/`

Django sert de pont entre le frontend et tous les agents. Il ne contient aucune logique métier — il orchestre.

### Session Management

Chaque utilisateur est identifié par un `X-Session-ID` généré côté client (localStorage). L'état complet de la session (contexte financier, analyse, messages) est pickled dans Redis :

```
X-Session-ID header → Redis GET → pickle.loads → dict Python
                                                       │
                                                  traitement
                                                       │
                                             pickle.dumps → Redis SETEX 24h
```

Pourquoi pickle et pas JSON ? Les dataclasses Python (`FinancialContext`, `KPIResult`, etc.) sont préservées telles quelles — pas besoin de sérialisation/désérialisation intermédiaire.

### Singletons au démarrage

`AppConfig.ready()` démarre deux threads au boot de Django :
- `FinanceAgent` — instance singleton partagée
- `FinanceCommAgent` — thread démon d'écoute A2A

### Endpoints

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/api/chat` | Message principal du fondateur |
| `GET` | `/api/state` | État session complet (messages + analyse + KPIs) |
| `GET` | `/api/a2a/state` | Résultats des agents spécialistes |
| `POST` | `/api/a2a/clarification` | Réponse fondateur aux questions de l'investment agent |
| `POST` | `/api/whatif` | Simulation hypothétique ("que se passe-t-il si...") |
| `POST` | `/api/pdf` | Export rapport PDF |
| `POST` | `/api/upload` | Upload PDF/CSV pour extraction |
| `POST` | `/api/new-conversation` | Nouvelle conversation |
| `GET` | `/api/conversations` | Historique conversations |
| `DELETE` | `/api/reset` | Reset session complète |
| `WS` | `/ws/a2a/` | Push état A2A toutes les 2 secondes |

### CORS et Session

- `CORS_ALLOW_ALL_ORIGINS = True` + `CORS_ALLOW_CREDENTIALS = False`
- Pas de cookies — le `X-Session-ID` custom header évite tous les problèmes CORS credentials
- `APPEND_SLASH = False` — Django ne redirige pas les POST sans slash final

---

## Frontend Next.js — L'Interface

**Fichier :** `frontend/src/`

Interface React entièrement côté client. Elle interroge le backend Django directement (`http://localhost:8000/api`) sans passer par le proxy Next.js (timeout trop court pour les analyses longues ~30s).

### Ce que voit le fondateur

1. **Chat** — conversation naturelle avec le CFO IA
2. **Cartes KPI** — runway, LTV/CAC, gross margin, MRR
3. **Graphiques** (Plotly) — scénarios, Monte Carlo, saisonnalité
4. **Panel investissement** — recommandation + valorisation + cap table

### Polling A2A

Quand l'analyse est soumise, le frontend commence un polling toutes les 2s sur `/api/a2a/state`. Quand l'investment agent répond (après ~25-30s), le panel investissement se met à jour automatiquement.

---

## Où est utilisé le LLM

> **Règle :** le LLM raisonne, il ne calcule jamais. Chaque chiffre financier est du Python pur.

| Fichier | Rôle du LLM |
|---|---|
| `finance/tools/parser.py` | Texte / PDF / CSV → `FinancialContext` structuré |
| `finance/agent.py` DP1 | "Ai-je assez de données ?" → questions contextuelles |
| `finance/agent.py` DP2 | "Confiance suffisante ?" → donnée manquante la plus impactante |
| `finance/comm_agent._classify_message()` | Intent du message entrant (heuristique d'abord) |
| `finance/comm_agent._auto_answer()` | Répondre aux questions depuis le FinancialContext |
| `finance/comm_agent._reason_about_conflicts()` | Contradictions entre opinions des agents |
| `investment/bus_adapter._should_engage()` | L'investment agent décide d'analyser ou ignorer |
| `investment/bus_adapter._detect_red_flags()` | Détection problèmes + formulation questions |
| `investment/strategy_selector.py` | Sélection stratégie de financement optimale |
| `backend/api/views.py` | Réponses conversationnelles + parsing what-if |

---

## Métriques d'Évaluation

**Fichier :** `agents/finance/evaluation.py`

### Métriques Agentiques

| Métrique | Formule | Ce qu'elle mesure |
|---|---|---|
| **TSR** Task Success Rate | `1.0=completed · 0.5=input-required · 0.0=failed` | L'agent a-t-il accompli sa mission ? |
| **GPS** Goal Progress Score | `sous-objectifs atteints / total` | Quelle proportion du pipeline a été complétée ? |
| **TCA** Tool Call Accuracy | `appels réussis / total` | Les outils fonctionnent-ils bien ? |
| **HR** Hallucination Rate | `claims non supportés / total (±15%)` | L'agent invente-t-il des chiffres ? |
| **ES** Efficiency Score | `min_rounds / actual_rounds` | L'agent est-il efficace ou trop bavard ? |

### RAGAS-style (RAG)

| Métrique | Description |
|---|---|
| **Faithfulness** | Les chiffres du résumé LLM = KPIs calculés réels |
| **Answer Relevance** | Runway, revenu, risque, confiance, recommandation couverts |
| **Context Recall** | Benchmarks récupérés couvrent bien le secteur |
| **Context Precision** | Benchmarks effectivement utilisés dans le comparateur |

---

## Structure des Fichiers

```
finAgent/
├── backend/                       Django REST API + sessions
│   ├── startwise/
│   │   ├── settings.py            CORS, Redis, Channels, APPEND_SLASH=False
│   │   ├── urls.py                Routes globales
│   │   └── asgi.py                Daphne + WebSocket
│   └── api/
│       ├── views.py               Tous les endpoints REST
│       ├── session_utils.py       Redis pickle sessions + singletons
│       ├── consumers.py           WebSocket A2A push
│       ├── apps.py                AppConfig.ready() → boot agents
│       └── urls.py                Routes sans trailing slash
│
├── frontend/                      Next.js 14
│   └── src/
│       ├── app/
│       │   ├── page.tsx           Page principale (chat + panels)
│       │   ├── layout.tsx         Layout global
│       │   └── globals.css        Design system
│       ├── components/
│       │   ├── Sidebar.tsx        Contexte startup + conversations
│       │   ├── KPICards.tsx       Cartes métriques financières
│       │   ├── Charts.tsx         Scénarios + Monte Carlo + Saisonnalité
│       │   └── A2APanel.tsx       Recommandation investment agent
│       └── lib/
│           ├── api.ts             Axios → Django direct (timeout 120s)
│           └── types.ts           Types TypeScript partagés
│
├── agents/
│   ├── finance/
│   │   ├── agent.py               Boucle autonome DP1/DP2
│   │   ├── agent_registry.py      Découverte agents par env vars
│   │   ├── a2a_models.py          Task · Message · Artifact · AgentCard
│   │   ├── a2a_server.py          FastAPI port 8001
│   │   ├── comm_agent.py          FinanceCommAgent (dispatch LLM-driven)
│   │   ├── evaluation.py          TSR · GPS · TCA · HR · ES · RAGAS
│   │   ├── calcul_tools/
│   │   │   ├── pipeline.py        Orchestrateur 8 étapes
│   │   │   ├── calculate_kpis.py
│   │   │   ├── monte_carlo.py
│   │   │   ├── scenario_projection.py
│   │   │   ├── seasonality_trend.py
│   │   │   ├── scenario_comparator.py
│   │   │   └── validate_inputs.py
│   │   └── tools/
│   │       ├── parser.py          LLM → FinancialContext
│   │       ├── fetch_benchmarks.py RAG + Tavily
│   │       ├── confidence_a2a.py  Score confiance + message A2A
│   │       └── pdf_report.py      Export PDF
│   │
│   └── investment/
│       ├── main.py                InvestmentAgent (pipeline 7 étapes)
│       ├── bus_adapter.py         BRPOP thread + LLM engagement
│       ├── a2a_server.py          FastAPI port 8002
│       ├── valuation_engine.py    DCF + multiples
│       ├── strategy_selector.py   LLM sélection stratégie
│       ├── dilution_calculator.py Cap table
│       └── memory/
│           ├── store.py           SQLite cross-session
│           └── comparator.py      Comparaison analyses historiques
│
├── a2a_bus/
│   ├── bus_server.py              FastAPI Redis port 8765
│   ├── comm_agent.py              CommAgent base (threading.Thread)
│   ├── run_mocks.py               --real-investment flag
│   └── mock_agents.py             Agents de test
│
├── models/
│   └── data_models.py             FinancialContext · KPIResult · Phase · etc.
│
├── chroma_db/                     Vectorstore benchmarks RAG
├── data/                          Cache saisonnalité JSON
├── .env                           Clés API + URLs agents
├── start.bat                      Lance les 6 processus
└── requirements.txt
```

---

## Choix de Design

### Pourquoi pas un seul agent monolithique ?
Séparer finance et investment permet à chaque agent d'être spécialisé, remplaçable et indépendamment testable. L'investment agent peut tourner sur une autre machine.

### Pourquoi pas OpenAI function calling ?
Le pipeline déterministe garantit des chiffres reproductibles. Un LLM qui calcule peut halluciner 5% d'erreur sur un runway — inacceptable pour des décisions financières.

### Pourquoi Redis pour les sessions et pas une base de données ?
Les dataclasses Python (`FinancialContext`, `KPIResult`) sont pickled directement — zéro mapping ORM, zéro perte de type. La TTL 24h est suffisante pour une session de travail.

### Pourquoi X-Session-ID et pas les cookies Django ?
Les cookies de session avec `CORS_ALLOW_CREDENTIALS=True` exigent une configuration HTTPS stricte. Le header custom `X-Session-ID` depuis localStorage est simple, stateless, et fonctionne en développement sans configuration TLS.
