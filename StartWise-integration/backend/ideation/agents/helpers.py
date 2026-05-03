import os
from pathlib import Path

FORCED_ENV_KEYS = {
    "AGENT_HOST",
    "QUESTION_AGENT_PORT",
    "RESEARCH_AGENT_PORT",
    "FORMULATOR_AGENT_PORT",
    "PYTHONUTF8",
    "TEXT_MODEL_PROVIDER",
    "QUESTION_AGENT_MODEL",
    "RESEARCH_AGENT_MODEL",
    "FORMULATOR_AGENT_MODEL",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "FIRECRAWL_API_KEY",
    "FIRECRAWL_COUNTRY",
    "FIRECRAWL_LOCATION",
}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in FORCED_ENV_KEYS:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def setup_env() -> None:
    _load_env_file(Path(__file__).resolve().parents[2] / ".env")

    # LiteLLM on Windows should read/write files in UTF-8 mode.
    os.environ.setdefault("PYTHONUTF8", "1")

    # Shared defaults for local development.
    os.environ.setdefault("AGENT_HOST", "0.0.0.0")
    os.environ.setdefault("TEXT_MODEL_PROVIDER", "openai")
    os.environ.setdefault("QUESTION_AGENT_PORT", "8101")
    os.environ.setdefault("RESEARCH_AGENT_PORT", "8102")
    os.environ.setdefault("FORMULATOR_AGENT_PORT", "8103")
    os.environ.setdefault(
        "QUESTION_AGENT_MODEL", "gpt-4o"
    )
    os.environ.setdefault(
        "RESEARCH_AGENT_MODEL", "gpt-4o"
    )
    os.environ.setdefault(
        "FORMULATOR_AGENT_MODEL", "gpt-4o"
    )


def normalize_litellm_model(model_name: str) -> str:
    value = (model_name or "").strip()
    if not value:
        provider = os.getenv("TEXT_MODEL_PROVIDER", "openai").strip().lower() or "openai"
        return f"{provider}/gpt-4o"
    if "/" in value:
        return value
    provider = os.getenv("TEXT_MODEL_PROVIDER", "openai").strip().lower() or "openai"
    return f"{provider}/{value}"
