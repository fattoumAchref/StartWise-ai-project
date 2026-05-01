# test_groq_models.py
import os
from dotenv import load_dotenv
import requests

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}"
}

response = requests.get("https://api.groq.com/openai/v1/models", headers=headers)

print("📋 Modèles disponibles sur Groq :")
print("="*50)

if response.status_code == 200:
    models = response.json()
    for model in models.get("data", []):
        print(f"  • {model['id']}")
else:
    print(f"Erreur: {response.status_code}")
    print(response.text)