"""
Configuration MVP Orchestrator.
"""

# TokenFactory LLM
TOKENFACTORY_API_KEY = "sk-f042a9ed44984cac8447e241e8a86791"
BASE_URL = "https://tokenfactory.esprit.tn/api"
MODEL_NAME = "hosted_vllm/Llama-3.1-70B-Instruct"

# Agents disponibles
AVAILABLE_AGENTS = ["finance", "marketing", "investment"]

# Timeout
AGENT_TIMEOUT = 60  # seconds