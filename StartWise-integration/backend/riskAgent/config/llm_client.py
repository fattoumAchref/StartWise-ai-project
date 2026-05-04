import logging
import httpx
from openai import OpenAI

from dotenv import load_dotenv
import os

load_dotenv()

TOKENFACTORY_API_KEY = (
    os.getenv('TOKENFACTORY_API_KEY')
    or os.getenv('TOKEN_FACTORY_API_KEY')
    or os.getenv('ESPRIT_API_KEY')
    or os.getenv('LLM_API_KEY')
    or os.getenv('OPENAI_API_KEY')
)
MODEL_NAME = os.getenv('MODEL_NAME') or os.getenv('LLM_MODEL') or 'hosted_vllm/Llama-3.1-70B-Instruct'

logger = logging.getLogger(__name__)

def create_llm_client(timeout: float = 120.0):
    """
    Initialise et retourne le client LLM OpenAI-compatible (TokenFactory).
    """
    logger.info("🤖 Initialisation du client LLM (Llama 3.1 via API)...")

    http_client = httpx.Client(
        verify=False,
        timeout=timeout
    )

    client = OpenAI(
        api_key=TOKENFACTORY_API_KEY,
        base_url="https://tokenfactory.esprit.tn/api/v1",
        http_client=http_client,
        timeout=timeout
    )

    logger.info("✅ Client LLM initialisé via API")

    return client, MODEL_NAME