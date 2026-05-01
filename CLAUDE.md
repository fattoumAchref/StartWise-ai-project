# StartWise — Architecture Reference for Claude

> Read this first. Everything you need to navigate the codebase is here.

---

## What is this project?

**StartWise** is a multi-agent AI platform for startup founders. It combines:
- A **Marketing Intelligence** module (5 LangGraph agents — colleagues' code)
- An **Ideation** tunnel (ADK Q&A flow — colleagues' code)
- A **Product Audit** module (Gemini + Qdrant — colleagues' code)
- A **Financial Viability CFO** module (Finance + Investment agents — OUR code)

All served by one Django backend and one Next.js frontend.

---

## Services map (what runs where)

| Service | Port | Command in start.bat | Notes |
|---|---|---|---|
| Next.js frontend | 3000 | `npm run dev` | App Router, React 19 |
| Django backend | 8000 | `daphne startwise.asgi:application` | All REST + WS |
| Finance A2A server | 8001 | `uvicorn finagents.finance.a2a_server:app` | FastAPI |
| Investment A2A server | 8002 | `uvicorn finagents.investment.a2a_server:app` | FastAPI |
| A2A Bus | 8765 | `uvicorn a2a_bus.bus_server:app` | FastAPI + **Redis** |
| Question Agent | 8101 | `python -m ideation.agents.question_agent` | Standalone |
| Research Agent | 8102 | `python -m ideation.agents.research_agent` | Standalone |
| Formulator Agent | 8103 | `python -m ideation.agents.formulator_agent` | Standalone |
| Qdrant | 6333 | Docker | Product Audit only |
| **Redis** | 6379 | **Must be running separately** | Session state + A2A bus |

> **Redis is required** but NOT launched by start.bat. Install Redis locally
> (Windows: via WSL or Memurai) or add `docker run -d -p 6379:6379 redis` to start.bat.

---

## Backend — Django multi-app (`backend/`)

```
backend/
├── manage.py
├── startwise/              # Django project config
│   ├── settings.py         # CWD forced to project root (chroma_db/, data/)
│   │                       # Loads .env from project root
│   │                       # InMemoryChannelLayer (no Redis for channels)
│   │                       # SESSION_ENGINE = db (SQLite)
│   ├── urls.py             # Route table (see below)
│   └── asgi.py             # Daphne ASGI entry
│
├── api/                    # OUR module — FinAgent Django wrapper
│   ├── views.py            # 14 REST endpoints
│   ├── session_utils.py    # Redis-backed session (pickle) + agent singletons
│   └── urls.py             # Mounted at /api/
│
├── agents/                 # Colleagues — Marketing LangGraph agents
│   ├── graph.py            # LangGraph: Trend→Vision→Emotion→Creative→Commercial
│   ├── inference.py        # LLM calls via TOKEN_FACTORY_API_KEY (Llama-3.1-70B)
│   ├── views.py            # SSE streaming + file endpoints
│   └── urls.py             # Mounted at /api/ (alongside ours — no conflicts)
│
├── ideation/               # Colleagues — ADK Q&A ideation tunnel
│   ├── agents/             # 3 standalone servers (run separately)
│   │   ├── question_agent.py   → :8101
│   │   ├── research_agent.py   → :8102
│   │   └── formulator_agent.py → :8103
│   ├── services/
│   │   ├── orchestrator.py     # Main pipeline; generate_summary() → Markdown text
│   │   ├── session_store.py    # JSON-persisted (ideation_sessions.json)
│   │   ├── schemas.py          # SessionState, QuestionState, etc.
│   │   ├── a2a_client.py       # Calls sub-agents via HTTP
│   │   ├── image_generation.py # OpenAI gpt-image-1
│   │   └── logo_generation.py  # OpenRouter
│   ├── views.py            # 15 REST endpoints
│   └── urls.py             # Mounted at /ideation/
│
└── product_audit/          # Colleagues — Gemini + Qdrant product analysis
    ├── services/
    │   ├── orchestrator.py     # Firecrawl scrape → Gemini embed → Qdrant store
    │   ├── gemini_client.py    # Gemini embedding + generation
    │   ├── qdrant_client.py    # Vector store (Qdrant :6333)
    │   └── firecrawl_client.py # Web scraping
    ├── views.py            # 3 REST endpoints
    └── urls.py             # Mounted at /product-audit/
```

### URL routing table

| Prefix | App | Who calls it |
|---|---|---|
| `/api/chat` | api (ours) | `frontend/src/lib/api.ts` |
| `/api/state` | api (ours) | `frontend/src/lib/api.ts` |
| `/api/pdf`, `/api/reset`, etc. | api (ours) | `frontend/src/lib/api.ts` |
| `/api/upload-document/` | agents (colleagues) | `frontend/src/services/agents.ts` |
| `/api/send-email/` etc. | agents (colleagues) | `frontend/src/services/agents.ts` |
| `/ideation/*` | ideation | `frontend/src/services/ideation.ts` |
| `/product-audit/*` | product_audit | `frontend/src/services/productAudit.ts` |

---

## OUR agents (`finagents/`)

```
finagents/
├── finance/
│   ├── agent.py              # Autonomous FinanceAgent (A2A Task state machine)
│   │                         # Parses → validates → runs pipeline → delegates
│   ├── a2a_server.py         # FastAPI :8001 — A2A JSON-RPC gateway
│   ├── a2a_models.py         # Task, Message, TextPart, Artifact, DataPart
│   ├── agent_registry.py     # Agent Card for discovery
│   ├── comm_agent.py         # Publishes to A2A bus
│   ├── evaluation.py         # Evaluation metrics
│   ├── calcul_tools/         # Deterministic calculation pipeline
│   │   ├── pipeline.py       # Orchestrates all steps; returns dict with all results
│   │   ├── calculate_kpis.py # Runway, LTV/CAC, gross margin, alerts
│   │   ├── monte_carlo.py    # 1000-simulation runway distribution
│   │   ├── scenario_projection.py  # 3 scenarios (pessimiste/realiste/optimiste)
│   │   ├── seasonality_trend.py    # Seasonal forecast
│   │   ├── scenario_comparator.py  # vs benchmark comparison
│   │   ├── route_by_phase.py # SEED / TRACTION / FUNDRAISING detection
│   │   └── validate_inputs.py
│   └── tools/
│       ├── parser.py         # NLP → FinancialContext (LLM)
│       ├── validator.py      # Data quality scoring
│       ├── fetch_benchmarks.py  # ChromaDB + Tavily
│       ├── pdf_report.py     # ReportLab PDF generation
│       ├── vectorizer.py     # ChromaDB upsert
│       └── confidence_a2a.py # Confidence score + A2A message builder
│
└── investment/
    ├── a2a_server.py         # FastAPI :8002 — Investment A2A gateway
    ├── bus_adapter.py        # Listens on A2A bus for finance broadcasts
    ├── valuation_engine.py   # DCF / revenue multiple / Berkus valuation
    ├── scenario_generator.py # Investment scenarios (conservative/base/aggressive)
    ├── benchmark_engine.py   # Sector benchmarks
    ├── stage_detector.py     # Pre-seed / Seed / Series A detection
    ├── strategy_selector.py  # VC / Angel / Bootstrap strategy
    ├── dilution_calculator.py
    ├── grants_checker.py
    └── memory/               # Cross-session comparisons
```

### Finance pipeline flow (what happens on `/api/chat`)

```
User message
    │
    ▼ parser.py (LLM)
FinancialContext
    │
    ▼ validator.py
ValidationResult (data quality score, missing fields)
    │
    ├── If data insufficient → FinanceAgent asks clarification (input-required state)
    │
    ▼ fetch_benchmarks.py (ChromaDB → Tavily fallback)
BenchmarkResult
    │
    ▼ pipeline.py (deterministic — no LLM)
    ├── validate_inputs
    ├── calculate_kpis      → KPIResult (runway, LTV/CAC, margin, alerts)
    ├── route_by_phase      → Phase (SEED/TRACTION/FUNDRAISING)
    ├── scenario_projection → 3 scenarios
    ├── monte_carlo         → 1000 simulations
    ├── seasonality_trend   → 12-month forecast
    ├── scenario_comparator → vs benchmark
    └── confidence_a2a      → ConfidenceResult + A2AMessage
    │
    ▼ comm_agent.py (publish to A2A bus :8765)
Investment agent receives and responds asynchronously
```

### Session state (important)

Session ID comes from `X-Session-ID` header (set by `frontend/src/lib/api.ts` from localStorage).
State is stored in Redis (pickle). Key: `django:app_state:{session_id}`.
TTL: 24h.

---

## A2A Bus (`a2a_bus/`)

```
a2a_bus/
├── bus_server.py   # Redis-backed HTTP message bus
│                   # POST /publish → push to recipient inboxes
│                   # GET /inbox/{agent_id} → read messages
│                   # POST /inbox/{agent_id}/pop → read + delete
├── bus_client.py   # Python client
├── run_mocks.py    # Runs agents as bus listeners
│                   # --real-investment → uses real InvestmentBusAdapter
├── mock_agents.py  # Mock Investment + Risk agents for testing
└── comm_agent.py   # FinanceAgent communication utilities
```

---

## Shared utilities (project root)

```
models/
└── data_models.py   # FinancialContext, Phase, DataQuality, AlertLevel
                     # These are the CANONICAL data types imported everywhere

scraping/            # Data gathering utilities (used by fetch_benchmarks.py)
├── market_data.py
├── news_scraper.py
├── saas_benchmarks.py
├── sector_calendar.py
└── yahoo_finance.py

chroma_db/           # ChromaDB vector store for benchmark data (ACTIVE)
data/                # Cache: sector_seasonality_cache.json, benchmarks_cache.json
```

> settings.py forces `os.chdir(PROJECT_ROOT)` so all relative paths (`chroma_db/`,
> `data/`) resolve to the project root, not `backend/`.

---

## Frontend (`frontend/src/`)

### Page routes

| URL | File | Purpose |
|---|---|---|
| `/` | `app/page.tsx` | Landing page |
| `/onboarding` | `app/onboarding/page.tsx` | Ideation Q&A tunnel (ADK) |
| `/dashboard` | `app/dashboard/page.tsx` → `pages/Dashboard.jsx` | Marketing agents dashboard |
| `/dashboard/ideation` | `app/dashboard/ideation/page.tsx` | Ideation summary + logo + image |
| `/dashboard/product-audit` | `app/dashboard/product-audit/page.tsx` | Product audit interface |
| `/dashboard/viability-assessment` | `app/dashboard/viability-assessment/page.tsx` | **OUR CFO page** |
| `/agent/[id]` | `app/agent/[id]/page.tsx` → `pages/AgentPage.jsx` | Marketing agent detail |

### Services (frontend API layer)

| File | Calls | Used by |
|---|---|---|
| `lib/api.ts` | `http://localhost:8000/api/*` | viability-assessment/page.tsx |
| `services/ideation.ts` | `http://localhost:8000/ideation/*` | onboarding + ideation page |
| `services/productAudit.ts` | `http://localhost:8000/product-audit/*` | product-audit page |
| `services/agents.ts` | `http://localhost:8000/api/*` + localStorage workflow | sidebar + dashboard |

### Components to know

| Component | Location | Purpose |
|---|---|---|
| `app-sidebar.tsx` | components/ | Main sidebar — reads workflow status from localStorage |
| `Charts.tsx` | components/ | Plotly charts: ScenariosChart, MonteCarloChart, SeasonalityChart, BenchmarkChart |
| `KPICards.tsx` | components/ | KPI grid display |
| `A2APanel.tsx` | components/ | Investment agent recommendation panel |
| `nav-main.tsx` | components/ | Sidebar navigation with status badges |
| `ui/sidebar.tsx` | components/ui/ | shadcn sidebar primitives |

### localStorage keys (cross-component communication)

| Key | Written by | Read by | Content |
|---|---|---|---|
| `startwise_summary` | onboarding/page.tsx | viability-assessment/page.tsx | Markdown narrative (headings: Business Idea, Risks, etc.) |
| `startwise_business_idea` | onboarding/page.tsx | viability-assessment/page.tsx | Short business idea string |
| `startwise_workflow_status` | services/agents.ts | app-sidebar.tsx | JSON: step statuses |
| `startwise_financial_data` | viability-assessment/page.tsx | app-sidebar.tsx | Analysis JSON |
| `startwise_market_data` | viability-assessment/page.tsx | app-sidebar.tsx | Benchmark JSON |
| `sw_session_id` | lib/api.ts | lib/api.ts | FinAgent session ID |
| `ideation_session_id` | onboarding/page.tsx | ideation/page.tsx | Ideation session ID |

### Context providers

| Context | File | Purpose |
|---|---|---|
| `AppContext` | context/AppContext.jsx | Language, analysis history, project description |
| `ProjectContext` | context/ProjectContext.tsx | Bridge: ideation summary → marketing agents |

---

## Environment variables (`.env` at project root)

Copied to `backend/.env` at launch by start.bat so ideation sub-agents can read it.

| Variable | Used by | Purpose |
|---|---|---|
| `ESPRIT_API_KEY` | finagents/ | Llama-3.1-70B (finance/investment LLM) |
| `ESPRIT_BASE_URL` | finagents/ | `https://tokenfactory.esprit.tn/api` |
| `ESPRIT_MODEL` | finagents/ | `hosted_vllm/Llama-3.1-70B-Instruct` |
| `TOKEN_FACTORY_API_KEY` | backend/agents/inference.py | Same key — alias for colleagues' code |
| `OPENAI_API_KEY` | backend/ideation/ | GPT-4o for ideation sub-agents + image gen |
| `OPENROUTER_API_KEY` | backend/ideation/ | Logo generation |
| `FIRECRAWL_API_KEY` | backend/product_audit/ | Web scraping |
| `GEMINI_API_KEY` | backend/product_audit/ | Embeddings + generation |
| `QDRANT_URL` | backend/product_audit/ | `http://localhost:6333` |
| `A2A_BUS_URL` | finagents/ | `http://localhost:8765` |
| `QUESTION_AGENT_URL` | backend/ideation/ | `http://localhost:8101` |
| `RESEARCH_AGENT_URL` | backend/ideation/ | `http://localhost:8102` |
| `FORMULATOR_AGENT_URL` | backend/ideation/ | `http://localhost:8103` |

---

## Common tasks

### Add a new finance endpoint
1. Add view in `backend/api/views.py`
2. Add URL in `backend/api/urls.py`
3. Add function in `frontend/src/lib/api.ts`

### Add a new frontend page
1. Create `frontend/src/app/dashboard/{name}/page.tsx`
2. Add it to `app-sidebar.tsx` nav items
3. Add status key to `WorkflowStatus` in `services/agents.ts`

### Debug finance analysis not working
1. Check Redis is running: `redis-cli ping`
2. Check Django logs for `[Django] FinanceAgent` startup message
3. Check `backend/api/session_utils.py` — singletons started in `startup_singletons()`
4. `startup_singletons()` is called from `backend/startwise/asgi.py` on startup

### Debug ideation not working
1. Check sub-agents are running (:8101, :8102, :8103)
2. Check `backend/ideation_sessions.json` exists and is valid JSON
3. Sub-agents load `.env` from `backend/.env` (not project root) — ensured by start.bat `copy`

---

## Known issues / debt

| Issue | Location | Impact |
|---|---|---|
| Emotion Agent JSON parse error | `backend/agents/emotion_agent.py` | LLM returns malformed JSON; pre-existing bug |
| Creative Director timeout | `backend/agents/creative_agent.py` | SSE timeout; pre-existing |
| `summary-with-image` retry loop | `frontend/src/hooks/useIdeation.ts` | Retries even on 200; pre-existing |
| Redis | `a2a_bus/bus_server.py`, `backend/api/session_utils.py` | Now launched via Docker in start.bat (step 1) |

---

## How to add a new specialist agent (Risk, Legal, etc.)

This is the pattern to follow. The Finance agent already broadcasts its analysis to the A2A bus after every analysis — your agent just needs to listen.

**Step 1 — Create the agent package**
```
finagents/risk/
├── __init__.py
├── a2a_server.py      # FastAPI server on a new port (e.g. 8003)
│                      # Copy finagents/investment/a2a_server.py as template
├── bus_adapter.py     # Listens to A2A bus, processes financial_analysis messages
│                      # Copy finagents/investment/bus_adapter.py as template
└── main.py            # Entry point (optional)
```

**Step 2 — Register the agent on the bus**

In `bus_adapter.py`, subscribe to `financial_analysis` message type:
```python
AGENT_ID = "risk_agent"   # must be unique on the bus
AGENT_TYPE = "risk"
# Listen for messages where recipients includes "risk_agent"
```

**Step 3 — Add to `start.bat`**
```bat
echo [N/M] Risk Agent A2A Server (port 8003)...
start "Risk A2A" cmd /k "venv\Scripts\activate && set A2A_BUS_URL=http://localhost:8765 && uvicorn finagents.risk.a2a_server:app --port 8003 --reload"
timeout /t 2 /nobreak >nul

echo [N+1/M] Risk Agent (bus listener)...
start "Risk Agent" cmd /k "venv\Scripts\activate && set A2A_BUS_URL=http://localhost:8765 && python -m a2a_bus.run_mocks --real-risk"
```

**Step 4 — Surface the result in the frontend**

In `frontend/src/app/dashboard/viability-assessment/page.tsx`, add a new panel (same pattern as the Investment panel) that polls for the risk agent's response via a new endpoint in `backend/api/views.py`.

**What the Finance agent sends on the bus (A2AMessage structure)**

See `finagents/finance/tools/confidence_a2a.py` for the exact payload structure.
Key fields: `financial_context`, `kpis`, `phase`, `confidence_score`, `scenarios`, `monte_carlo`.

---

## What NOT to touch

- `backend/agents/` — colleagues' marketing agents — do not modify
- `backend/ideation/` — colleagues' ideation module — do not modify
- `backend/product_audit/` — colleagues' product audit — do not modify
- `frontend/src/pages/Dashboard.jsx` — complex colleagues' component, reused as-is
- `frontend/src/pages/AgentPage.jsx` — same
