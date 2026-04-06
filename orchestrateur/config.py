"""
Configuration MVP Orchestrator.
"""

# TokenFactory LLM
TOKENFACTORY_API_KEY = "sk-3af10c5256a547299d9402856f312f8f"
BASE_URL = "https://tokenfactory.esprit.tn/api"
MODEL_NAME = "hosted_vllm/Llama-3.1-70B-Instruct"

# Agents disponibles
AVAILABLE_AGENTS = ["finance", "marketing", "investment"]

# Timeout
AGENT_TIMEOUT = 60  # seconds