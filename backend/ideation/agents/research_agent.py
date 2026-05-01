import os

import uvicorn
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm

try:
    from google.adk.a2a.utils.agent_to_a2a import to_a2a
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Missing A2A dependency. Install with: pip install \"a2a-sdk[http-server]\""
    ) from exc

from .helpers import normalize_litellm_model, setup_env
from .search_tools import firecrawl_search

setup_env()

PORT = int(os.getenv("RESEARCH_AGENT_PORT", "8102"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MODEL = normalize_litellm_model(
    os.getenv("RESEARCH_AGENT_MODEL", "gpt-4o")
)


def main() -> None:
    root_agent = LlmAgent(
        model=LiteLlm(model=MODEL),
        name="ResearchAgent",
        tools=[firecrawl_search],
        description=(
            "Performs web-backed strategic startup research and surfaces "
            "question angles with citations."
        ),
        instruction=(
            "You are the Research Agent for startup ideation.\n"
            "Use the firecrawl_search tool to gather fresh strategic evidence.\n"
            "Identify assumptions and high-leverage follow-up angles.\n"
            "Prefer concise bullet points and include source links."
        ),
    )

    a2a_app = to_a2a(root_agent, host=HOST, port=PORT)
    print(f"Running Research Agent on {HOST}:{PORT}")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
