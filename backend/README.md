# Startwise Backend (Django + ADK A2A)

This backend implements the ideation Q/A flow using Django as the **client agent API layer** and three Google ADK agents over A2A:

- `QuestionAgent` (sync JSON-RPC): refinement, answer evaluation, keyword extraction
- `ResearchAgent` (web research): strategic notes via `Firecrawl` search
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
- `POST /generate-image`
- `GET /image-output`
- `GET /images/<filename>`
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
   Required for text-agent runtime:
   - `OPENAI_API_KEY=<your OpenAI API key>`
   - `TEXT_MODEL_PROVIDER=openai`
   - `QUESTION_AGENT_MODEL=gpt-4o`
   - `RESEARCH_AGENT_MODEL=gpt-4o`
   - `FORMULATOR_AGENT_MODEL=gpt-4o`
   Required for research:
   - `FIRECRAWL_API_KEY=<your Firecrawl API key>`
   Optional for OpenRouter-backed image/logo generation:
   - `OPENROUTER_API_KEY=<your OpenRouter API key>`
   Optional for geo-targeted research:
   - `FIRECRAWL_COUNTRY=US`
   - `FIRECRAWL_LOCATION=San Francisco,California,United States`
   Recommended on Windows:
   - `PYTHONUTF8=1`
   Optional for summary image generation:
   - `BACKEND_URL=http://localhost:8001`
   - `IDEATION_IMAGE_MODEL=flux`
   - `IDEATION_IMAGE_WIDTH=1344`
   - `IDEATION_IMAGE_HEIGHT=640`
   - `IMAGE_TIMEOUT_SECONDS=60`

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
- `A2A_USE_STREAMING=false` is the safe default because many locally exposed ADK A2A agents do not support `message/stream`. The orchestrator uses standard sync requests unless you explicitly enable streaming.
- The ADK agents now use LiteLLM + OpenAI for text generation while still running over A2A.
- Firecrawl search is used for fresh-web research because `google_search` is Gemini-specific and not compatible with the OpenRouter model path.
- ADK A2A bridge requires `a2a-sdk` (installed via `requirements.txt` as `a2a-sdk[http-server]`).
- `POST /summary-with-image/<session_id>` now attempts to generate a background image, stores the file under `backend/ideation/output/images/`, and appends image metadata to the returned summary markdown.
