# StartWise — Plateforme d’idéation et d’analyse stratégique multi-agents

Ce dépôt (`StartWise-integration`) est le cœur applicatif : **Next.js**, **Django**, **bus A2A Redis**, **agents Finance / Investment / Risk** (Uvicorn), **idéation**, **audit produit**, **LexWise**, etc.  
Le dépôt parent **`agent legal`** contient en plus `start.bat` / `stat.bat` pour lancer l’ensemble des services sous Windows.

---

## Table des matières

1. [Vue d’ensemble](#1-vue-densemble)
2. [Architecture technique détaillée](#2-architecture-technique-détaillée)
   - [Services et ports](#21-services-et-ports)
   - [Bus A2A (Redis)](#22-bus-a2a-redis)
   - [Agent Finance (`finagents.finance`) — détail](#23-agent-finance-finagentsfinance)
   - [Agent légal et LexWise — détail](#24-agent-légal-et-lexwise-legal_advisor)
   - [Agent Investment (`finagents.investment`)](#25-agent-investment-finagentsinvestment)
   - [Agent Risk](#26-agent-risk)
   - [Django (CFO, agents, idéation, legal, audit)](#27-django-cfo-agents-idéation-legal-audit)
   - [Frontend Next.js](#28-frontend-nextjs)
3. [Lancement Windows : `start.bat` / `stat.bat`](#3-lancement-windows--startbat--statbat)
4. [Variables d’environnement importantes](#4-variables-denvironnement-importantes)
5. [Parcours Idéation → Dashboard](#5-parcours-idéation--dashboard)
6. [Structure réelle des dossiers](#6-structure-réelle-des-dossiers)
7. [Installation manuelle (sans batch)](#7-installation-manuelle-sans-batch)
8. [Configuration `.env`](#8-configuration-env)
9. [Historique des correctifs récents (référence)](#9-historique-des-correctifs-récents-référence)
10. [Métriques d’évaluation, UX, protocole A2A et conflits](#10-métriques-dévaluation-ux-protocole-a2a-et-conflits)
11. [Équipe](#11-équipe)

---

## 1. Vue d’ensemble

StartWise accompagne un fondateur depuis **l’idée** jusqu’à des **analyses** (viabilité financière, investissement, risque, juridique, marketing, etc.).

| Zone | Rôle principal |
|------|----------------|
| **Idéation** | Tunnel Q&R + synthèse / plan d’affaires (API Django `ideation/`, agents Python dédiés) |
| **Dashboard** | Viabilité CFO, Investment, Risk, LexWise, Product Audit, onboarding… (Next.js + API Django + agents A2A) |
| **Bus A2A** | Messagerie inter-agents via **Redis** (listes `a2a:<agent_id>:inbox`) exposée en HTTP (`a2a_bus`) |
| **Finagents** | Agents **Finance**, **Investment**, **Risk** en services FastAPI / Uvicorn + logique métier Python |

Les modules **Legal** et **Marketing** consomment aussi le bus depuis Django (`legal_advisor`, `agents`, etc.).

---

## 2. Architecture technique détaillée

### 2.1. Services et ports

| Service | Port | Commande type | Rôle |
|---------|------|----------------|------|
| **A2A Bus** | `8765` | `uvicorn a2a_bus.bus_server:app --port 8765` | `POST /publish` → push Redis sur les files des destinataires ; `GET/POST` inbox |
| **Finance A2A** | `8001` | `uvicorn finagents.finance.a2a_server:app --port 8001` | Protocole A2A (JSON-RPC) pour l’analyse financière ; délègue aux agents spécialisés |
| **Investment A2A** | `8002` | `uvicorn finagents.investment.a2a_server:app --port 8002` | Réception `tasks/send` → publication `financial_analysis` sur le bus ; **consumer Redis intégré** (lifespan) |
| **Risk A2A** | `8003` | `uvicorn riskAgent.a2a_server:app --port 8003` (depuis `backend/`) | Agent risque A2A |
| **Django (Daphne)** | `8000` | `daphne -p 8000 startwise.asgi:application` | API REST, WebSockets, CFO, idéation, legal, product-audit… |
| **Next.js** | `3000` | `npm run dev` | Interface utilisateur |
| **Redis** | `6379` | Docker ou service local | Files du bus + état sessions |
| **Qdrant** | `6333` | Docker (optionnel) | Vecteurs (audit / RAG selon modules) |
| **Ideation agents** | `8101–8103` | `python -m ideation.agents.*` | Agents idéation (question, research, formulator) |

**Ordre de dépendance logique** : Redis → Bus 8765 → Finance / Investment / Risk → Django → Frontend.

---

### 2.2. Bus A2A (Redis)

- **Code** : `a2a_bus/bus_server.py` (FastAPI), `a2a_bus/comm_agent.py` (thread `BRPOP` par agent).
- **Clé d’inbox** : `a2a:<agent_id>:inbox` (liste Redis).
- **`POST /publish`** : pour chaque id dans `message["to"]`, `LPUSH` du JSON du message.
- **Consommation** : chaque `CommAgent` fait `BRPOP` sur sa propre inbox (un message ne va qu’à **un** worker qui gagne le pop — d’où l’importance d’**un seul** `InvestmentBusAdapter` actif sur `investment_agent`).

Variables utiles :

- `A2A_BUS_URL` (ex. `http://localhost:8765`) — utilisée par les agents pour publier en HTTP.
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB` — connexion directe Redis si le bus HTTP échoue (fallback `LPUSH`).

---

### 2.3. Agent Finance (`finagents.finance`)

L’**agent Finance** est le **cœur analytique** de la viabilité financière StartWise : il transforme le texte (ou le contexte) du fondateur en **chiffres structurés**, enchaîne des **calculs déterministes** (pas de « math LLM »), puis **pousse** le résultat vers les agents spécialisés (investissement, risque, etc.). Il est conçu comme un **agent autonome** avec points de décision explicites et tâches au format **A2A** (Google/IBM).

#### Objectif

- Produire une **analyse financière complète** (KPIs, runway, Monte Carlo, scénarios, benchmarks secteur, score de confiance, message inter-agents).
- **Déléguer** ensuite aux autres agents (investissement, risque, …) sans figer leur logique dans le code Finance : le registre d’agents (`agent_card.py`) décide des URLs et du fallback bus.

#### Surface réseau (protocole A2A)

| Fichier | Rôle |
|---------|------|
| `finagents/finance/a2a_server.py` | Serveur **FastAPI** Uvicorn (port **8001** par défaut). **Agent Card** : `GET /.well-known/agent.json`. **JSON-RPC** sur `POST /` : `tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe` (SSE). Stockage des tâches en mémoire (+ option Redis selon implémentation du store). |
| `FINANCE_AGENT_URL` | URL publiée dans la carte agent (défaut `http://localhost:8001`). |

Les compétences déclarées dans la carte incluent l’analyse startup : burn, runway, LTV/CAC, marge, **Monte Carlo** (probabilité de survie 12 mois), scénarios pessimiste / réaliste / optimiste, comparaison **benchmarks** secteur, et la **délégation** vers l’agent investissement.

#### États d’une tâche (`Task`)

Gérés par `FinanceAgent` + serveur A2A :

```
submitted → working ⇄ input-required → completed | failed
```

- **`input-required`** : données insuffisantes ou confiance trop basse — l’agent pose des **questions** au fondateur ; le client renvoie `tasks/send` avec la suite du dialogue pour **`continue_task`**.
- **`completed`** : artefacts attachés (JSON d’analyse + résumé texte).
- **`failed`** : erreur bloquante (ex. aucune donnée).

Paramètres notables dans `FinanceAgent` :

- **`MIN_CONFIDENCE = 0.35`** : en dessous, deuxième point de décision peut demander **une** clarification ciblée.
- **`MAX_CLARIFICATION_ROUNDS = 2`** : plafond pour éviter les boucles infinies.

#### Les étapes du raisonnement (`_run` dans `agent.py`)

1. **Parser** le texte utilisateur → objet **`FinancialContext`** (`finagents/finance/tools/parser.py`, LLM + contexte connu). Les tours précédents sont fusionnés (`known_context` / `_parent_context`) pour comprendre des réponses courtes (« 5000 TND », « j’ai perdu 3 clients »).
2. **Valider** les entrées (`pipeline/validate_inputs.py`) → champs critiques manquants, incohérences, score de qualité.
3. **Point de décision 1 (DP1)** : si la validation échoue et qu’il reste des tours de clarification → le LLM génère jusqu’à **3 questions** en français (sinon questions préconstruites) → tâche **`input-required`**. Sinon on continue.
4. **Benchmarks secteur** : `fetch_benchmarks` (optionnel, non bloquant si échec).
5. **Pipeline d’analyse** : `run_analysis_pipeline` (`pipeline/orchestrator.py`) — **calculs déterministes** en chaîne (voir ci-dessous).
6. **Point de décision 2 (DP2)** : si le **score de confiance** du pipeline est **strictement inférieur à 0,35** → une question LLM « la plus impactante » → `input-required`. Sinon poursuite.
7. **Délégation** : `_delegate_to_agents` — pour chaque agent du registre, **POST JSON-RPC** `tasks/send` vers son URL ; si échec HTTP et `bus_fallback` → publication sur le **bus Redis** (`FinanceCommAgent.publish`).
8. **Complétion** : artefacts **`financial-analysis`** (JSON) et **`summary`** (texte), message agent, état **`completed`**.

*(Les étapes 7–8 correspondent aux « Step 5–6 » dans les commentaires du fichier `agent.py`.)*

#### Où le LLM intervient (et où il n’intervient pas)

- **LLM** : parsing du langage naturel, **DP1** (questions manquants), **DP2** (une question si confiance basse), méthode **`decide()`** pour d’autres raisonnements si l’orchestrateur Django l’utilise.
- **Pas de LLM pour les maths** : KPIs, Monte Carlo, scénarios, comparateur viennent des modules **`finagents/finance/pipeline/`** et outils associés — prévisibles et auditables.

#### Contenu du pipeline (`run_analysis_pipeline`)

Ordre logique (`pipeline/orchestrator.py`) :

1. `validate_inputs`
2. `calculate_kpis` (si données minimales, ex. burn + trésorerie)
3. `route_by_phase` + modèles actifs selon la phase startup
4. `scenario_projection`
5. `monte_carlo`
6. `seasonality_trend` (si données suffisantes)
7. `scenario_comparator` (si benchmarks disponibles)
8. Score de **confiance** + construction du **`a2a_message`** pour diffusion aux autres agents

Le résultat agrégé inclut notamment : validation, KPIs, Monte Carlo, phase, scénarios, saisonnalité, comparateur, confiance, message A2A.

#### Mémoire conversationnelle

- L’historique est porté par l’objet **`Task`** (messages utilisateur / agent).
- `continue_task` reprend **`all_user_text()`** pour tout re-parser — rien n’est perdu entre les tours de clarification.
- Au **nouveau** `process_task`, l’agent peut **vider** l’état A2A / investment Redis précédent (`_clear_a2a_state`) pour ne pas mélanger deux analyses dans l’UI.

#### Délégation multi-agents (registre)

- **`finagents/finance/agent_card.py`** : liste intégrée **investment_agent**, **risk_agent**, **marketing_agent**, **legal_agent** avec URLs (souvent Django pour marketing/legal) et **`bus_fallback`**.
- Variables d’environnement du type **`INVESTMENT_AGENT_URL`**, **`RISK_AGENT_URL`**, etc. — permettent d’ajouter un agent **sans modifier** `agent.py`.
- Chaque spécialiste reçoit le **même** paquet d’analyse ; chacun **décide** s’il répond (pattern autonome côté Investment/Risk).

#### `FinanceCommAgent` (`bus_publisher.py`)

- Thread **`CommAgent`** avec **`AGENT_ID = finance_agent`** : consomme la file Redis **`a2a:finance_agent:inbox`**.
- Quand Investment (ou un autre) répond, le message arrive ici : **classification** du type de message (souvent via LLM), puis mise à jour du **hash Redis** `a2a:finance_agent:state` (clés par expéditeur + clés **rétro-compat** `investment_rating`, `risk_level`, `investment_recommendation`, etc.) pour alimenter le **dashboard** / CFO sans polling sur chaque microservice.

#### Fichiers et dossiers utiles

| Chemin | Rôle |
|--------|------|
| `finagents/finance/agent.py` | **`FinanceAgent`** — boucle `_run`, décisions, délégation, complétion. |
| `finagents/finance/a2a_server.py` | Gateway HTTP A2A + Agent Card. |
| `finagents/finance/protocol_models.py` | Modèles `Task`, `Message`, `Artifact`, statuts, erreurs JSON-RPC. |
| `finagents/finance/pipeline/` | Orchestrateur + étapes de calcul (KPIs, MC, scénarios…). |
| `finagents/finance/tools/parser.py` | Extraction `FinancialContext` depuis le texte. |
| `finagents/finance/tools/benchmark_fetcher.py` | Données de référence secteur. |
| `finagents/finance/bus_publisher.py` | **`FinanceCommAgent`** — publish + consume + état Redis. |
| `finagents/finance/agent_card.py` | **Registre** des agents spécialisés. |

#### Variables LLM côté Finance

- Par défaut : **`ESPRIT_BASE_URL`**, **`ESPRIT_API_KEY`**, **`ESPRIT_MODEL`** (voir `agent.py` — alignés avec `settings.py` Django via `os.environ.setdefault` pour `ESPRIT_API_KEY`).

---

### 2.4. Agent légal et LexWise (`legal_advisor`)

L’**agent légal** StartWise est le module Django **`legal_advisor`** : conseiller juridique **centré sur la Tunisie** (droits des affaires, startups, fiscalité, marques, licences, etc.). Il combine **RAG sur ChromaDB** (données scrappées et indexées), **recherche web Tavily** en secours, **mémoire de session** courte, et participation au **bus A2A** comme **`legal_agent`**. L’interface utilisateur principale est la page **LexWise** (`/dashboard/lexwise`) qui appelle l’API Django sous le préfixe **`/legal/`**.

#### Rôle fonctionnel

- Répondre aux questions en **s’appuyant sur les sources** fournies au modèle (chunks JORT, DGI, CNSS, INNORPI, SPDX, base startups, etc.) — prompt **strict** : pas d’hallucination de texte « officiel » inventé ; si l’info manque, réponse **partielle** mais utile.
- Détecter des **intentions** (`trademark`, `tax`, `startup_act`, `legal`, `license`, `jurisprudence`, …) pour orienter la requête RAG, le fallback web et des **audits déterministes** (ex. marque, licences) lorsque le code l’active.
- **Publier** sur le bus un message **`legal.assessment`** après chaque réponse réussie à `/legal/ask`, pour que les autres agents (Finance, Investment, Risk, Marketing) enrichissent leur contexte partagé Redis.

#### URLs HTTP (montage Django)

Préfixe : **`/legal/`** (`backend/startwise/urls.py` → `path('legal/', include('legal_advisor.urls'))`).

| Route | Méthode | Description |
|-------|---------|-------------|
| **`/legal/.well-known/agent.json`** | GET | **Carte d’agent A2A** : identité `legal_agent`, compétence `legal_qa`, capacités, et bloc **`a2a`** (`publishes: legal.assessment`, `subscribes: financial_analysis`, `risk.assessment`, `investment.recommendation`, `marketing.analysis`). |
| **`/legal/ask`** | POST | Corps JSON : `question`, optionnellement `session_id`, `startup_context`. Retourne `answer`, `sources`, flags type `web_used`. C’est l’endpoint consommé par le frontend LexWise. |
| **`/legal/session/clear`** | POST | Efface l’historique conversationnel en mémoire pour un `session_id`. |
| **`/legal/stats`** | GET | Nombre de chunks indexés dans ChromaDB (pour la mini-UI embarquée `/legal/`). |
| **`/legal/`** (racine) | GET | Page HTML de démo / test du chat (même logique que l’ancien `chat_ui`). |
| **`/legal/domains`** | GET | Liste des domaines / thèmes couverts (si implémenté dans `views.domains`). |

#### Pipeline de réponse (`views.py` — vue `ask`)

1. **Réception** de la question (+ contexte startup optionnel pour enrichir le prompt).
2. **`search_docs`** : embedding de la requête (`state.embedding_service`), recherche vectorielle dans la **collection Chroma** `documents` ; détection d’**entité nommée** et d’**intents** pour filtrer et scorer les passages.
3. **Filtrage qualité RAG** : passages avec score suffisant (`good_rag`, seuil typique 0,45).
4. **Fallback Tavily** (`web_search_fallback`) si trop peu de bons passages ou si une entité attendue n’apparaît pas dans le RAG : requêtes ciblées par intent, domaines tunisiens (`legislation.tn`, `cnss.nat.tn`, `innorpi.nat.tn`, `startup.gov.tn`, …) ou ouverts (licences).
5. **Court-circuit** : si la question est une **recherche de nom** et que l’entité n’existe ni dans RAG ni sur le web → réponse fixe orientant vers **RNE** / **INNORPI** (sans inventer une fiche).
6. **Audits spécialisés** (dans la même vue, selon la question) : par ex. vérifications **marque** (similarité, données INNORPI scrapées), **multi-domaines**, **licences SPDX**, etc. — logique déterministe + LLM pour la prose.
7. **Appel LLM** (`AsyncOpenAI` compatible OpenAI, URL/clé depuis `settings.LLM_BASE_URL` / `LLM_API_KEY`) avec le prompt système **`STRICT_SYSTEM`** : contexte = sources concaténées, style imposé (paragraphes, gras, max ~220 mots, fin par ligne **Source :**).
8. **Historique** : append question/réponse dans `_sessions[session_id]` (max **20** tours, TTL **1 h**).
9. **`publish_assessment`** (`legal_advisor/bus_adapter.py`) : diffusion **`legal.assessment`** vers `finance_agent`, `investment_agent`, `risk_agent`, `marketing_agent` avec résumé, sources, intents, niveau de « risque » dérivé des intents (compliance vs informationnel).

#### Données et RAG (`state.py`, `ingest.py`, `scrapers/`)

- **ChromaDB** persistant : chemin **`CHROMA_PATH`** (défaut sous `backend/chroma_db`, configurable dans `settings.py` et `start.bat` via `CHROMA_PATH` à la racine du monorepo si besoin).
- **Collection** : `documents`, espace cosinus HNSW.
- **Embeddings** : service chargé au démarrage Django depuis le module **`embeddings`** (voir `legal_advisor/state.py` — import depuis le backend).
- **Ingestion** : script **`legal_advisor/ingest.py`** — lance les scrapers, découpe en chunks (~600 mots, overlap), embed avec **`intfloat/multilingual-e5-base`**, stocke dans Chroma. Modes `--only jort|dgi|spdx|innorpi|…` pour ingérer partiellement.

**Scrapers** (dossier `legal_advisor/scrapers/`) : non exhaustif — **JORT** (`jort.py`), **DGI/CNSS** (`dgi_cnss.py`), **droit des sociétés** (`droit_societes.py`), **INNORPI** (`innorpi.py`), **WIPO** (`wipo.py`), **SPDX** licences (`spdx.py`), **base startups** (`startups_db.py`), etc. Ils alimentent le corpus indexé.

#### Bus A2A — `LegalBusAdapter` (`bus_adapter.py`)

- Démarré par **`startup_singletons()`** dans Django (`get_legal_bus_adapter()`), thread **`CommAgent`** avec **`AGENT_ID = legal_agent`**.
- **Écoute** (types connus) : `financial_analysis`, `investment.recommendation`, `risk.assessment`, `risk.conflict_report`, `marketing.analysis`, notes marketing, etc.
- **`_should_engage`** : ignore les types inconnus ; pour `financial_analysis`, exige au moins **secteur / sector / kpis** dans le payload pour éviter les messages vides.
- **Réactions publiées** (en plus du stockage d’état Redis `a2a:legal_agent:state`) :
  - **`legal.regulatory_note`** si le niveau de risque financier est **HIGH** ou **CRITICAL** (rappel covenants, insolvabilité, etc.).
  - **`legal.conflict_review`** si un **`risk.conflict_report`** a une sévérité autre que faible.
  - **`legal.investment_note`** si le rating investissement est **BUY** ou **STRONG_BUY** (due diligence, titrisation locale, etc.).
- **Contexte startup** : lors d’un `financial_analysis`, extrait secteur / phase / pays / MRR / runway → clé Redis **`a2a:legal_agent:startup_context`** (JSON, TTL 1 h) + champs dans `set_state` pour contextualiser les futures réponses légales.

Le **`FinanceCommAgent`** ré-ingère ensuite ces messages et met à jour les clés **`legal_agent_*`** (et équivalents) dans l’état partagé consommé par le dashboard.

#### Intégration frontend (LexWise)

- Fichier typique : `frontend/src/app/dashboard/lexwise/page.tsx` — envoie la question à **`POST {BACKEND}/legal/ask`** avec `session_id` et un **`startup_context`** construit depuis le contexte idéation / CFO (`localStorage`, `ProjectContext`).
- Permet au juridique d’être **aligné** sur le secteur et le résumé business sans recopier manuellement.

#### Fichiers clés

| Chemin | Rôle |
|--------|------|
| `backend/legal_advisor/views.py` | **`ask`**, **`agent_card`**, stats, session, HTML démo ; prompt strict, Tavily, audits, LLM. |
| `backend/legal_advisor/bus_adapter.py` | **`LegalBusAdapter`** — subscribe bus, stockage contexte, notes réactives, **`publish_assessment`**. |
| `backend/legal_advisor/state.py` | Singleton **Chroma** + **embedding_service** au boot Django. |
| `backend/legal_advisor/ingest.py` | Pipeline d’indexation des scrapers vers Chroma. |
| `backend/legal_advisor/scrapers/*.py` | Collecte des sources tunisiennes / licences / marques. |
| `backend/legal_advisor/urls.py` | Routes `/legal/*`. |

#### Variables d’environnement utiles

- **`LLM_API_KEY`**, **`LLM_BASE_URL`**, **`LLM_MODEL`** — consommées par `settings.py` (et exposées comme `ESPRIT_*` pour d’autres modules).
- **`TAVILY_API_KEY`** — recherche web de secours dans `views.py`.
- **`CHROMA_PATH`** — emplacement de la base vectorielle persistante.

---

### 2.5. Agent Investment (`finagents.investment`)

#### Rôle

1. Recevoir une tâche A2A depuis le Finance agent (`tasks/send`).
2. Publier sur le bus un message `type: financial_analysis`, `to: ["investment_agent"]`.
3. Le **worker** `InvestmentBusAdapter` (`finagents/investment/bus_adapter.py`, `AGENT_ID = investment_agent`) consomme ce message, décide s’il s’engage, lance `InvestmentAgent.analyze`, publie `investment.recommendation` (ou clarification, erreur, skip structuré).
4. Notifier l’état de la tâche A2A côté serveur HTTP Investment : `POST http://localhost:8002/internal/tasks/{task_id}/state/{completed|failed}` (car le bus adapter tourne dans le **même** processus Uvicorn que l’A2A server — la mémoire `_tasks` est partagée).

#### Consumer intégré (Uvicorn 8002)

- Au **démarrage** de `finagents/investment/a2a_server.py`, le **lifespan** FastAPI appelle `get_investment_bus_adapter()` pour démarrer le thread `CommAgent` **dans le même processus** que l’API A2A.
- **Variable** : `INVESTMENT_EMBED_BUS_ADAPTER` — par défaut `1` / true : embarquer le consumer. Mettre à `0` si un **autre** processus exécute déjà `InvestmentBusAdapter` (sinon deux `BRPOP` sur la même liste = comportements imprévisibles).

#### Django et l’Investment adapter

- Dans `backend/cfo/session_manager.py`, l’ancien démarrage systématique de `get_investment_bus_adapter()` dans Django a été **désactivé par défaut** pour éviter un **deuxième** consumer concurrent avec Uvicorn 8002.
- Pour l’ancien mode (consumer **uniquement** dans Django) : `INVESTMENT_BUS_ADAPTER_IN_DJANGO=1` et, côté serveur 8002, `INVESTMENT_EMBED_BUS_ADAPTER=0`.

#### Décision d’engagement (`_should_engage`)

- Filtre dur : payload vide → pas d’engagement.
- Filtre dur : au moins un signal financier parmi les KPIs connus **ou** `proba_survie_12m` (Monte Carlo) → considéré comme « données présentes ».
- Un **LLM** peut encore proposer `engage: false` ; si des KPIs sont pourtant présents, le code **force** l’engagement pour éviter le message utilisateur du type *« agent n’a pas traité : MRR manquant »* alors que burn/runway/CAC suffisent.
- Si l’agent refuse vraiment d’analyser (cas théorique après filtres), `_notify_no_engagement` publie quand même une `investment.recommendation` « skip » et complète la tâche A2A pour ne pas bloquer l’UI.

#### LLM sans LangChain (module Investment)

- `finagents/investment/llm_client.py` : appels **httpx** vers l’API OpenAI-compatible (`BASE_URL` + `/chat/completions`, clés dans `finagents/investment/config.py`).
- `input_handler`, `strategy_selector`, `output_formatter`, `memory/comparator` utilisent ce client — **plus de dépendance** à `langchain_openai` pour ces fichiers.

---

### 2.6. Agent Risk

- Code sous `backend/riskAgent/` (serveur A2A port **8003**).
- S’abonne au bus pour `financial_analysis` et messages liés ; publie `risk.assessment`, etc. (voir `finagents/risk/bus_adapter.py` et intégration Django selon déploiement).

---

### 2.7. Django (CFO, agents, idéation, legal, audit)

- **Settings** : `backend/startwise/settings.py` — ajoute le parent `StartWise-integration/` à `sys.path` pour importer `finagents` et `a2a_bus`.
- **ASGI** : `backend/startwise/asgi.py` — au chargement, `startup_singletons()` (`cfo/session_manager.py`) démarre notamment `FinanceCommAgent`, `FinanceAgent`, adapters risk/marketing/legal selon les imports — **sauf** Investment par défaut (voir ci-dessus).
- **URLs racine** : `backend/startwise/urls.py` — préfixes `api/` (CFO, agents), `ideation/`, `product-audit/`, `legal/`.
- **CFO** : viabilité, session Redis pickle, WebSocket, pont vers agents.
- **Ideation** : Django app `ideation` — orchestrateur, sessions, endpoints consommés par le frontend (`NEXT_PUBLIC_BACKEND_URL` + `/ideation`).

---

### 2.8. Frontend Next.js

- **Répertoire** : `frontend/`.
- **Pont idéation** : `ProjectContext`, `localStorage` (`sw_ideation_*`, `startwise_*`), pages `onboarding`, `dashboard/ideation`, `dashboard/viability-assessment`, etc.
- **Sidebar** : `app-sidebar.tsx` — étapes (idéation, audit, finance, investment, risk, LexWise…) avec statuts locked/unlocked selon `localStorage` (`startwise_summary`, `startwise_unlocked`, …).

---

## 3. Lancement Windows : `start.bat` / `stat.bat`

Emplacement : **`agent legal/start.bat`** (répertoire parent de `StartWise-integration`).

- **`stat.bat`** : simple `call` vers `start.bat` (même effet, nom plus court).

Le batch :

1. Définit `ROOT`, `SW` = `StartWise-integration`, active le venv (`.venv` ou `venv` à la racine `agent legal`).
2. Exporte notamment :
   - `PYTHONPATH=%SW%` (pour `finagents`, `a2a_bus` depuis la racine intégration),
   - `A2A_BUS_URL=http://localhost:8765`,
   - `INVESTMENT_AGENT_URL=http://localhost:8002`,
   - `INVESTMENT_EMBED_BUS_ADAPTER=1`,
   - `INVESTMENT_BUS_ADAPTER_IN_DJANGO=0`,
   - `RISK_AGENT_URL=http://localhost:8003`,
   - copie `.env` racine vers `backend/.env` si présent.
3. Démarre **Redis** (Docker) et **Qdrant** (Docker) si disponibles.
4. Ouvre des fenêtres `cmd /k` pour : Bus, Finance A2A, Investment A2A, Risk A2A, agents idéation, **Django Daphne 8000**, **Next.js 3000**.

> **Important** : il n’y a plus de fenêtre séparée « Investment Adapter » en `python -c sleep` — le consumer est **dans** le processus Investment **8002**.

---

## 4. Variables d’environnement importantes

| Variable | Exemple | Rôle |
|----------|---------|------|
| `A2A_BUS_URL` | `http://localhost:8765` | Publication HTTP des messages bus |
| `INVESTMENT_AGENT_URL` | `http://localhost:8002` | URL utilisée par le Finance agent pour `tasks/send` vers Investment |
| `INVESTMENT_EMBED_BUS_ADAPTER` | `1` / `0` | Démarrer le `InvestmentBusAdapter` dans le processus Uvicorn 8002 |
| `INVESTMENT_BUS_ADAPTER_IN_DJANGO` | `1` / absent | Si `1`, Django démarre aussi l’adapter Investment (**à éviter** en double avec embed) |
| `RISK_AGENT_URL` | `http://localhost:8003` | Registre agents Finance |
| `REDIS_HOST`, `REDIS_PORT` | `localhost`, `6379` | Bus + sessions |
| `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` | Base API côté Next (idéation, CFO, etc.) |
| `DJANGO_SECRET_KEY`, clés LLM, `CHROMA_PATH`, … | Voir `.env` / `settings.py` | Sécurité, modèles, chemins données |

---

## 5. Parcours Idéation → Dashboard

1. L’utilisateur complète le tunnel **onboarding** (`frontend/src/app/onboarding/page.tsx`) via le hook `useIdeation`.
2. À la fin, `generateSummary()` écrit le résumé dans `localStorage` (`startwise_summary`, etc.).
3. Le code enchaîne avec la synchronisation **ProjectContext** (`sw_ideation_*`) et pose **`sessionStorage['sw_fresh_session'] = '1'`** pour autoriser l’accès aux pages dashboard idéation (garde : sans ce flag, redirection vers onboarding).
4. **Correctif important** : après `await generateSummary()`, il ne faut pas se fier à la variable React `finalSummary` (closure obsolète) pour décider d’écrire les clés ; il faut relire **`localStorage.getItem('startwise_summary')`** avant de poser `sw_fresh_session` et les clés `sw_ideation_*` — sinon la session « fraîche » n’est pas enregistrée et l’utilisateur est renvoyé vers `onboarding?reset=true` avec données effacées.

Clés `localStorage` fréquentes :

- `startwise_summary`, `startwise_business_idea`, `startwise_session_id`, `startwise_track`
- `sw_ideation_summary`, `sw_ideation_business_idea`, `sw_ideation_data` (JSON)
- `startwise_summary` + idée : utilisés aussi par la sidebar pour déverrouiller les modules

---

## 6. Structure réelle des dossiers

```
StartWise-integration/
├── a2a_bus/                 # Serveur HTTP bus + CommAgent de base
│   ├── bus_server.py
│   └── comm_agent.py
├── finagents/
│   ├── finance/             # Agent Finance A2A + bus_publisher
│   ├── investment/          # Agent Investment A2A + bus_adapter + llm_client
│   └── risk/                # Adapter risk (consommation bus)
├── backend/
│   ├── startwise/           # settings, asgi, urls
│   ├── cfo/                 # CFO, session_manager, vues WebSocket / API
│   ├── ideation/
│   ├── agents/
│   ├── legal_advisor/
│   ├── product_audit/
│   ├── riskAgent/
│   └── manage.py
└── frontend/
    └── src/app/             # routes Next.js (dashboard, onboarding, …)
```

Le dépôt **`agent legal`** à la racine contient `start.bat`, `stat.bat`, le venv et éventuellement `.env` partagé.

---

## 7. Installation manuelle (sans batch)

1. **Python 3.11+** : créer un venv, `pip install -r backend/requirements.txt`.
2. **Node** : dans `frontend/`, `npm install`.
3. Lancer **Redis** (obligatoire pour le bus et nombreuses sessions).
4. Lancer dans l’ordre : **bus 8765** → **8001 / 8002 / 8003** → **Django 8000** → **Next 3000**.
5. Définir `PYTHONPATH` vers la racine `StartWise-integration` pour les commandes Uvicorn hors Django.

---

## 8. Configuration `.env`

À placer à la racine **`agent legal`** (copié vers `backend/.env` par `start.bat`) ou directement dans `backend/.env`.

Inclure au minimum les clés attendues par `settings.py` et les agents : **LLM** (TokenFactory / Groq / etc. selon modules), **Redis**, chemins **Chroma/Qdrant** si utilisés, **TAVILY** / **FIRECRAWL** selon features, **Telegram** si activé.

Voir aussi les commentaires dans `startwise/settings.py` et `finagents/investment/config.py` (exemples de noms de variables).

---

## 9. Historique des correctifs récents (référence)

| Sujet | Détail |
|-------|--------|
| **Onboarding idéation** | Après `generateSummary()`, utiliser le résumé lu depuis `localStorage` pour `sw_fresh_session` et `sw_ideation_*` (évite closure `finalSummary` vide). |
| **Investment sans réponse** | Le serveur 8002 publiait sur le bus sans consumer → lifespan + `InvestmentBusAdapter` embarqué ; retrait du duplicate Django par défaut ; suppression du second processus « adapter » dans `start.bat`. |
| **`langchain_openai` manquant** | Remplacement par `llm_client.py` (httpx) dans les modules Investment. |
| **« Non recommandé » / KPI manquants** | Prompt + override si KPIs présents ; extension des champs pris en compte (`cash_out_alert`, Monte Carlo). |

---

## 10. Métriques d’évaluation, UX, protocole A2A et conflits

Cette section synthétise ce qui est **implémenté dans le code** : comment l’interface guide l’utilisateur, quelles **métriques** reflètent la qualité des analyses, comment le **protocole A2A** relie les services, et comment les **alertes de conflits** remontent jusqu’à l’UI.

### 10.1. Protocole A2A (Agent-to-Agent)

StartWise s’aligne sur une approche **A2A** (inspirée des spécifications type Google / IBM) : découverte d’agent, tâches JSON-RPC, et bus Redis pour la messagerie asynchrone.

| Couche | Rôle |
|--------|------|
| **Agent Card** | Fichier JSON décrivant l’agent : `GET /.well-known/agent.json` sur Finance (**8001**), Investment (**8002**), Risk (**8003**), et `GET /legal/.well-known/agent.json` pour le légal sous Django. |
| **JSON-RPC 2.0** | `POST /` sur les serveurs Finance / Investment avec méthodes `tasks/send`, `tasks/get`, `tasks/cancel`, `tasks/sendSubscribe` (SSE). Le Finance agent envoie des tâches aux agents spécialisés via ce même schéma. |
| **Bus Redis** | Messages typés (`financial_analysis`, `investment.recommendation`, `risk.assessment`, `legal.assessment`, `risk.conflict_report`, …) avec champs `from`, `to`, `payload`, `metadata`. Publication HTTP `POST {A2A_BUS_URL}/publish` ou `LPUSH` direct. |
| **État partagé** | Chaque agent a un hash Redis `a2a:<agent_id>:state` (lecture côté Django pour l’UI). Un journal global `a2a:conversation:log` liste les derniers envois/réceptions (méthode `CommAgent.get_conversation_log`). |
| **API Django (pont UI)** | `GET /api/a2a/state` — agrège l’état du `FinanceCommAgent` (clés `investment_rating`, `risk_level`, champs de conflit, clarifications, etc.). `GET /api/a2a/network` — instantané multi-agents + journal pour le **CrossAgentPanel**. `POST /api/a2a/clarification` — transmet une réponse utilisateur vers la file d’attente investment (clarification). |
| **WebSocket** | `ws/a2a/` (Django Channels) peut pousser des mises à jour de type `a2a_state` au client connecté (`cfo/websocket_consumer.py`). |

En résumé : les **microservices** parlent A2A + bus ; le **frontend** parle REST Django (`/api/...`) qui lit la même vérité Redis.

### 10.2. Métriques d’évaluation (qualité & risque)

Ces indicateurs sont **déjà câblés** dans l’UI ou les réponses API — ils servent à la fois au **fondateur** (lisibilité) et au **debug** (mode expert).

| Métrique / signal | Origine (backend / pipeline) | Usage UI |
|-------------------|------------------------------|----------|
| **`data_quality_score`** | Validation des entrées (`validate_inputs` / état CFO) | Page **viabilité** : bandeau « haute fiabilité / partielle » si score ≥ 0,8 ou ≥ 0,6 ; libellés **Débutant / Expert**. Composant **Sidebar** CFO : classes `q-complete` / `q-partial` / `q-missing` (seuils 0,8 et 0,5). |
| **`confidence.score`** | Pipeline finance (`ConfidenceResult`) | Barre de progression pourcentage sur la page viabilité. |
| **Scores investissement** | `investment_score`, `investment_confidence` (hash Redis) | **A2APanel** : affichés en **mode Expert** à côté du rating. |
| **Similarité benchmarks** | `bench.similarity_score` | Affichée en **mode Expert** sur la viabilité (comparaisons sectorielles). |
| **Métriques page Risk** | `risk_agent` / API d’analyse risque | `conflict_score`, `conflict_density`, `stability`, `ablation`, `signal_labels`, liste structurée **`conflicts`** (texte + agents + sévérité) — voir `dashboard/risk/page.tsx`. |

Le **mode Débutant / Expert** (toggle sur la viabilité) ne change pas les calculs : il change **libellés**, **densité d’information** (noms de champs techniques vs phrases guidées) et **affichage** des scores secondaires.

### 10.3. Interface utilisateur — guidance et ergonomie

| Mécanisme | Fichiers / comportement |
|-----------|-------------------------|
| **Parcours guidé par étapes** | Page viabilité : blocs « Situation globale », « KPIs », « Projections », « Monte Carlo », etc., avec pastilles **À remplir / Disponible / Complet** ; textes différents selon `expertMode`. |
| **Questions CFO & champs manquants** | `AgentGuidance`, `QuestionsHub` : listes « Ce dont votre CFO a besoin », champs manquants avec **`fieldLabel`** (libellé débutant vs expert), objectifs par bloc (`beginnerGoal` / `expertGoal`). |
| **Idéation → Finance** | Contexte injecté (résumé idée), entrées **ideation** vs **startup** ; évite de redemander le secteur si déjà dans le résumé. |
| **Sidebar application** | `app-sidebar.tsx` : **déverrouillage progressif** — modules verrouillés tant que `startwise_summary` absent (sauf `startwise_unlocked`) ; **Reach to Investors** derrière la complétion marketing (`startwise_workflow_status`). |
| **Panneau A2A investissement** | `A2APanel.tsx` : ratings traduits (ex. `STRONG_BUY` → « Très favorable ») en mode débutant ; tableaux valorisation / scénario avec intitulés simplifiés ; attente avec compteur `elapsedSeconds` ; formulaire de **clarification** vers investment ; message vert si **réponses auto** par le finance comm. |
| **Réseau d’agents** | `CrossAgentPanel.tsx` : cartes colorées par agent, signal principal (phase, rating, risk level…), bouton pour **déplier le journal A2A** (types raccourcis : `fin.analysis`, `invest.rec`, …), rafraîchissement toutes les **8 s** ; message clair si Redis indisponible. |
| **Persistance & reprise** | `getA2AState` après analyse / `a2a_publish_time` pour **polling** jusqu’à 5 min ; historique d’instantanés A2A sur la viabilité pour comparer deux analyses. |

L’objectif UX est double : **réduire la charge cognitive** (vocabulaire métier masqué en débutant) tout en laissant un **mode expert** pour due diligence et démo technique.

### 10.4. Détection et alertes de conflits inter-agents

Les conflits sont traités à **plusieurs niveaux** (règles, LLM, bus, UI).

#### A) Coordinateur Finance (`FinanceCommAgent`, `bus_publisher.py`)

Après chaque message classé **`recommendation`** ou **`assessment`**, la méthode **`_reason_about_conflicts()`** :

1. Agrège toutes les opinions stockées dans `a2a:finance_agent:state` (clés `*_recommendation`, `*_rating`, `*_level`, …) pour les agents se terminant par `_agent`.
2. Si **moins de 2** signaux → supprime les clés `conflict_type`, `conflict_message`, `conflict_severity` (pas de faux positif).
3. Sinon appelle un **LLM coordinateur** : « détecte les contradictions » ; attend un JSON `{ type, message, severity }` ou l’équivalent cohérent / `null`.
4. Écrit le résultat dans le **même hash Redis** consommé par `GET /api/a2a/state`.

Le **frontend** (`A2APanel`) affiche un encadré orangé si `conflict_type` est présent : en débutant le titre devient **« Point d’attention »** au lieu du code technique.

#### B) Agent Risk (`finagents/risk/bus_adapter.py`)

Après analyse, comparaison des signaux pairs (finance, investment, marketing, legal) :

- **Règles** explicites (ex. `finance_investment_mismatch`, `finance_legal_gap`, `marketing_finance_gap`) avec sévérité `high` / `medium`.
- **Enrichissement LLM** possible sur un résumé textuel des pairs.
- Publication **`risk.conflict_report`** sur le bus avec `conflict_count`, `severity`, `summary`, `agents_compared`.

#### C) Réactions en chaîne

| Agent | Action |
|-------|--------|
| **Legal** | Sur `risk.conflict_report` de sévérité non triviale → **`legal.conflict_review`** vers tous (`bus_adapter.py`). |
| **Investment** | Stocke le rapport ; si sévérité haute/moyenne → peut publier **`investment.conflict_stance`** (baisse de confiance, note explicative). |

Ces messages repassent par le **FinanceCommAgent** (intent `assessment`) et alimentent l’état Redis / le journal.

#### D) Page Risk dédiée

`frontend/src/app/dashboard/risk/page.tsx` affiche le **nombre de conflits**, les **métriques** (`conflict_density`, etc.) et une liste détaillée des **conflits** retournés par l’API d’analyse risque (libellés orientés analyste).

---

## 11. Équipe

Projet réalisé dans le cadre du **partenariat Medianet** — ESPRIT School of Engineering.

---

*StartWise — De l’idée à la stratégie, avec bus A2A, agents spécialisés et interface Next.js unifiée.*
