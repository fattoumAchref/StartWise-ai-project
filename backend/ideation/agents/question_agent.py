import os

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents.llm_agent import LlmAgent

from .helpers import setup_env

setup_env()

PORT = int(os.getenv("QUESTION_AGENT_PORT", "8101"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MODEL = os.getenv("QUESTION_AGENT_MODEL", "gemini-2.5-pro")


def main() -> None:
    root_agent = LlmAgent(
        model=MODEL,
        name="QuestionAgent",
        description=(
            "Refines startup idea context, evaluates answer quality, "
            "and extracts keywords for iterative ideation."
        ),
        instruction=(
            "You are the Question Agent for startup ideation.\n"
            "Responsibilities:\n"
            "1) Refine broad founder statements into strategic focus.\n"
            "2) Evaluate answer quality (specificity, actionability, relevance).\n"
            "3) Generate concise keyword lists.\n"
            "4) Keep outputs compact and machine-consumable when requested."
        ),
    )

    a2a_app = to_a2a(root_agent, host=HOST, port=PORT)
    print(f"Running Question Agent on {HOST}:{PORT}")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
