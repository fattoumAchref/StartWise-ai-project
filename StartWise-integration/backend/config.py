from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM — Llama via API ESPRIT
    llm_api_key: str = "sk-af700b35e54c4b98a460eb42d2f6064c"
    llm_base_url: str = "https://tokenfactory.esprit.tn/api"
    llm_model: str = "hosted_vllm/Llama-3.1-70B-Instruct"

    # Cohere reranker (optionnel — fallback cosine si absent)
    cohere_api_key: str = ""

    # Embeddings — multilingual-e5-base (local, gratuit)
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_dim: int = 768

    # Base de données — SQLite local (pas besoin de PostgreSQL)
    database_url: str = "sqlite+aiosqlite:///./agent_legal.db"

    # ChromaDB — stockage vectoriel local (pas besoin de Qdrant)
    chroma_path: str = "./chroma_db"

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # App runtime
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_debug: bool = False

    # Monitoring
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # Scraping
    jort_url: str = "https://www.legislation.tn"
    innorpi_url: str = "https://www.innorpi.tn"

    # Noms des collections ChromaDB
    col_legal: str = "legal_articles"
    col_trademarks: str = "trademarks"
    col_clauses: str = "contract_clauses"
    col_decisions: str = "court_decisions"
    col_tax: str = "tax_regulations"
    col_licenses: str = "software_licenses"


@lru_cache
def get_settings() -> Settings:
    return Settings()


cfg = get_settings()
