import os

import uvicorn
from google.adk.agents.llm_agent import LlmAgent

try:
    from google.adk.a2a.utils.agent_to_a2a import to_a2a
except ModuleNotFoundError as exc:
    raise RuntimeError(
        "Missing A2A dependency. Install with: pip install \"a2a-sdk[http-server]\""
    ) from exc

from .helpers import setup_env

setup_env()

PORT = int(os.getenv("FORMULATOR_AGENT_PORT", "8103"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MODEL = os.getenv("FORMULATOR_AGENT_MODEL", "gemini-2.5-pro")


def main() -> None:
    root_agent = LlmAgent(
        model=MODEL,
        name="FormulatorAgent",
        description=(
            "Converts strategic notes into a single high-quality next question "
            "for the founder."
        ),
        instruction=(
            "You are the Formulator Agent.\n"
            "Given context and research notes, craft one and only one next question.\n"
            "The question must be strategic, specific, and dependent on prior answers.\n"
            "Do not ask multiple questions."
        ),
    )

    a2a_app = to_a2a(root_agent, host=HOST, port=PORT)
    print(f"Running Formulator Agent on {HOST}:{PORT}")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
