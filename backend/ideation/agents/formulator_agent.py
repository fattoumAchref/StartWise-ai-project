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

PORT = int(os.getenv("FORMULATOR_AGENT_PORT", "8103"))
HOST = os.getenv("AGENT_HOST", "0.0.0.0")
MODEL = normalize_litellm_model(
    os.getenv("FORMULATOR_AGENT_MODEL", "gpt-4o")
)


def main() -> None:
    root_agent = LlmAgent(
        model=LiteLlm(model=MODEL),
        name="FormulatorAgent",
        description=(
            "Converts strategic notes into a single high-quality next question "
            "for the founder."
        ),
        instruction=(
            "You are the Formulator Agent.\n"
            "Given context and research notes, craft one and only one next question.\n"
            "The question must be strategic, specific, and dependent on prior answers.\n"
            "Prioritize understanding the founder's background and readiness before advanced business planning.\n"
            "Adjust the wording to the founder's level, and avoid unexplained jargon for beginners.\n"
            "Do not ask multiple questions."
        ),
    )

    a2a_app = to_a2a(root_agent, host=HOST, port=PORT)
    print(f"Running Formulator Agent on {HOST}:{PORT}")
    uvicorn.run(a2a_app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
