"""
Test rapide — vérifie le LLM Llama et les embeddings multilingual-e5-base.
Lancer : python test_llm.py
"""

import httpx
import asyncio
from openai import AsyncOpenAI
from sentence_transformers import SentenceTransformer

LLM_API_KEY  = "sk-af700b35e54c4b98a460eb42d2f6064c"
LLM_BASE_URL = "https://tokenfactory.esprit.tn/api"
LLM_MODEL    = "hosted_vllm/Llama-3.1-70B-Instruct"
EMBED_MODEL  = "intfloat/multilingual-e5-base"


# ── Test 1 : LLM ──────────────────────────────────────────────────

async def test_llm():
    print("=" * 50)
    print("TEST LLM — Llama 3.1 70B")
    print("=" * 50)

    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        http_client=httpx.AsyncClient(verify=False),
    )

    response = await client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=300,
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": "Tu es un conseiller juridique expert en droit tunisien des affaires. Réponds de façon concise.",
            },
            {
                "role": "user",
                "content": "Quelle est la différence entre une SARL et une SA en Tunisie ? Réponds en 3 points.",
            },
        ],
    )

    answer = response.choices[0].message.content
    print(f"Réponse Llama :\n{answer}\n")
    print(f"Tokens utilisés : {response.usage.total_tokens}")
    return True


# ── Test 2 : Embeddings ───────────────────────────────────────────

def test_embeddings():
    print("=" * 50)
    print("TEST EMBEDDINGS — multilingual-e5-base")
    print("=" * 50)

    print("Chargement du modèle (première fois = téléchargement ~500MB)...")
    model = SentenceTransformer(EMBED_MODEL)

    texts = [
        "query: Clause de non-concurrence dans un contrat de travail tunisien",
        "passage: La clause de non-concurrence ne peut excéder 2 ans et doit être compensée financièrement.",
        "passage: Le capital minimum d'une SARL en Tunisie est de 1000 dinars tunisiens.",
        "query: قانون الشركات التونسية",           # arabe
        "query: Company law in Tunisia",            # anglais
    ]

    vecs = model.encode(texts, normalize_embeddings=True)

    print(f"Dimension : {vecs.shape[1]}")
    print(f"Nombre de vecteurs : {vecs.shape[0]}")

    # Similarité cosine entre la requête et les passages
    import numpy as np
    q = vecs[0]  # requête non-concurrence
    for i, (t, v) in enumerate(zip(texts[1:], vecs[1:]), 1):
        score = float(np.dot(q, v))
        print(f"  Similarité avec [{t[:60]}...] = {score:.4f}")

    print()

    # Test multilingue
    q_ar = vecs[3]   # arabe
    q_en = vecs[4]   # anglais
    sim_ar_en = float(np.dot(q_ar, q_en))
    print(f"Similarité arabe ↔ anglais (même sujet) : {sim_ar_en:.4f}")
    print("  → Score > 0.7 = bon support multilingue\n")
    return True


# ── Test 3 : Phonétique ───────────────────────────────────────────

def test_phonetic():
    print("=" * 50)
    print("TEST PHONÉTIQUE — similarité de marques")
    print("=" * 50)

    import sys
    sys.path.insert(0, ".")
    from embeddings import PhoneticNormalizer

    ph = PhoneticNormalizer()
    pairs = [
        ("TakwinTech", "Takween"),      # très similaires — DOIT être > 0.7
        ("StartupTN", "StartupTN"),     # identiques — DOIT être 1.0
        ("Esprit", "Google"),           # différents — DOIT être < 0.3
        ("Sellini", "Salini"),          # similaires — DOIT être > 0.6
    ]

    for a, b in pairs:
        score = ph.similarity_score(a, b)
        flag = "✅" if (
            (score > 0.7 and a != b and "Google" not in b) or
            (score > 0.99 and a == b) or
            (score < 0.3 and "Google" in b)
        ) else "⚠️"
        print(f"  {flag} {a} ↔ {b} : {score:.3f}")

    print()
    return True


# ── Main ──────────────────────────────────────────────────────────

async def main():
    print("\n🚀 TESTS AGENT LÉGAL IA — TUNISIE\n")

    # 1. Phonétique (pas besoin de réseau)
    test_phonetic()

    # 2. Embeddings (télécharge le modèle si absent)
    try:
        test_embeddings()
    except Exception as e:
        print(f"⚠️  Embeddings : {e}\n")

    # 3. LLM (nécessite le réseau ESPRIT)
    try:
        await test_llm()
        print("✅ LLM opérationnel\n")
    except Exception as e:
        print(f"⚠️  LLM : {e}\n")
        print("   Vérifiez votre connexion au réseau ESPRIT.")

    print("Tests terminés.")


if __name__ == "__main__":
    asyncio.run(main())
