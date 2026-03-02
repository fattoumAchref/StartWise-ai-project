import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def setup_env() -> None:
    _load_env_file(Path(__file__).resolve().parents[2] / ".env")

    # Force AI Studio mode unless explicitly overridden.
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

    # Allow either key name in .env and normalize for SDK compatibility.
    if os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        os.environ.setdefault("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        os.environ.setdefault("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY", ""))

    # Shared defaults for local development.
    os.environ.setdefault("AGENT_HOST", "0.0.0.0")
    os.environ.setdefault("QUESTION_AGENT_PORT", "8101")
    os.environ.setdefault("RESEARCH_AGENT_PORT", "8102")
    os.environ.setdefault("FORMULATOR_AGENT_PORT", "8103")
    # Use a generally available, lower-cost default model for AI Studio keys.
    os.environ.setdefault("QUESTION_AGENT_MODEL", "gemini-2.0-flash")
    os.environ.setdefault("RESEARCH_AGENT_MODEL", "gemini-2.0-flash")
    os.environ.setdefault("FORMULATOR_AGENT_MODEL", "gemini-2.0-flash")
