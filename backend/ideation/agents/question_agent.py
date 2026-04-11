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

setup_env()

PORT = int(os.getenv("QUESTION_AGENT_PORT", "8101"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MODEL = normalize_litellm_model(
    os.getenv("QUESTION_AGENT_MODEL", "gpt-4o")
)


def main() -> None:
    root_agent = LlmAgent(
        model=LiteLlm(model=MODEL),
        name="QuestionAgent",
        description=(
            "Refines startup idea context, evaluates answer quality, "
            "and extracts keywords for iterative ideation."
        ),
        instruction=(
            "You are the Question Agent for startup ideation.\n"
            "Responsibilities:\n"
            "1) Refine broad founder statements into strategic focus.\n"
            "2) Evaluate answer quality (specificity, actionability, relevance) while respecting the founder's level.\n"
            "3) Generate concise keyword lists.\n"
            "4) Build lightweight founder-background profiles when requested.\n"
            "5) Keep outputs compact and machine-consumable when requested.\n"
            "6) Prefer plain language unless the conversation clearly shows the founder is comfortable with business jargon."
        ),
    )

    a2a_app = to_a2a(root_agent, host=HOST, port=PORT)
    print(f"Running Question Agent on {HOST}:{PORT}")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
