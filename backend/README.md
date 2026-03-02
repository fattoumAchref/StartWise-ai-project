# Startwise Backend (Django + ADK A2A)

This backend implements the ideation Q/A flow using Django as the **client agent API layer** and three Google ADK agents over A2A:

- `QuestionAgent` (sync JSON-RPC): refinement, answer evaluation, keyword extraction
- `ResearchAgent` (web research): strategic notes via `google_search`
- `FormulatorAgent` (next question generation): one strategic question at a time

The generated flow is sequential: each next question depends on prior user answers.

## API Contract

Implemented endpoints (matching frontend service calls):

- `GET /health`
- `POST /init`
- `POST /respond`
- `GET /keywords/<session_id>/<question_index>`
- `POST /suggest`
- `GET /session/<session_id>`
- `DELETE /session/<session_id>`
- `GET /summary/<session_id>`
- `POST /summary-with-image/<session_id>`
- `POST /reset`

## Local Setup

1. Create virtualenv and install dependencies:

```bash
pip install -r backend/requirements.txt
```

If you use `uv`:

```bash
uv pip install -r requirements.txt
```

2. Copy env template:

```bash
cp backend/.env.example backend/.env
```

3. Export env vars from `.env` (or load with your preferred tool).
   Required for AI Studio mode:
   - `GOOGLE_GENAI_USE_VERTEXAI=false`
   - `GOOGLE_API_KEY=<your Gemini API key>`

4. Start ADK agents (three separate terminals):

```bash
python -m ideation.agents.question_agent
python -m ideation.agents.research_agent
python -m ideation.agents.formulator_agent
```

5. Start Django API on port `8001`:

From repo root:

```bash
python backend/manage.py runserver 0.0.0.0:8001
```

From `backend/` directory:

```bash
python manage.py runserver 0.0.0.0:8001
```

## Notes

- If agents are not running yet, set `USE_A2A_MOCK=true` to test with deterministic fallback behavior.
- Research->formulator handoff is executed through streaming mode in the orchestrator (`A2AClient.stream`), enabling async/SSE-style execution semantics.
- This setup is configured for Gemini API key auth (AI Studio), not Vertex service-account auth.
- ADK A2A bridge requires `a2a-sdk` (installed via `requirements.txt` as `a2a-sdk[http-server]`).
