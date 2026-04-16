import chromadb
import asyncio
from embeddings import EmbeddingService

async def test_search():
    # Utiliser le même service d'embeddings que l'application
    embedding_service = EmbeddingService()

    client = chromadb.PersistentClient('./chroma_db')
    collection = client.get_collection('documents')

    # Test recherche Instadeep avec le bon modèle
    query_text = 'Instadeep marque'
    query_embedding = await embedding_service.embed_query(query_text)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
        include=['metadatas', 'documents', 'distances']
    )

    print("=== Recherche 'Instadeep marque' ===")
    print(f"Nombre de résultats: {len(results['documents'][0])}")

    for i in range(min(3, len(results['documents'][0]))):
        meta = results['metadatas'][0][i]
        doc = results['documents'][0][i]
        dist = results['distances'][0][i]
        
        print(f"\nRésultat {i+1}:")
        print(f"  Distance: {dist:.3f}")
        print(f"  Domain: {meta.get('domain', '?')}")
        print(f"  Source: {meta.get('source_type', '?')}")
        print(f"  Content: {doc[:200]}...")

    # Vérifier les domaines disponibles
    all_results = collection.get(limit=100, include=['metadatas'])
    domains = {}
    for meta in all_results['metadatas']:
        domain = meta.get('domain', 'UNKNOWN')
        domains[domain] = domains.get(domain, 0) + 1

    print(f"\n=== Domaines disponibles ===")
    for domain, count in domains.items():
        print(f"{domain}: {count} chunks")

# Lancer le test
if __name__ == "__main__":
    asyncio.run(test_search())