# backend/api — CFO FinAgent Module (OUR CODE)

Django app for the financial viability / CFO agent feature.

## Files

| File | Role |
|---|---|
| `views.py` | HTTP endpoints (14 REST routes) — thin layer only |
| `cfo_engine.py` | All CFO business logic: LLM calls, pipeline, what-if, context merge |
| `formatters.py` | Markdown text formatting for API responses |
| `serializers.py` | JSON serialization of analysis objects |
| `session_utils.py` | Redis-backed session state + agent singletons |
| `urls.py` | URL routing (mounted at `/api/`) |

## Endpoints (all at `/api/`)

`POST /chat` · `GET /state` · `POST /whatif` · `GET /a2a-state` · `POST /pdf`
`POST /upload` · `DELETE /reset` · `POST /toggle-whatif` · `POST /toggle-section`
`POST /conversations/new` · `GET /conversations` · `POST /conversations/restore`
`DELETE /conversations/<id>`
