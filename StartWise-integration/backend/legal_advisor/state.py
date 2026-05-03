"""
Module-level singletons initialised once at Django startup (via AppConfig.ready).
All views import `collection` and `embedding_service` from here.
"""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

log = logging.getLogger("legal_advisor.state")

log.info("Initialisation du service d'embeddings local…")
try:
    from embeddings import embedding_service  # noqa: E402
    log.info("Service d'embeddings prêt.")
except Exception as e:
    log.error("Impossible d'initialiser le service d'embeddings: %s", e)
    raise

import chromadb  # noqa: E402
from django.conf import settings  # noqa: E402

CHROMA_PATH = getattr(settings, "CHROMA_PATH", "./chroma_db")

log.info("Initialisation ChromaDB… path=%s", CHROMA_PATH)
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = chroma_client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )
    count = collection.count()
    log.info("ChromaDB prêt. %d chunks indexés.", count)
except Exception as e:
    log.error("Impossible d'initialiser ChromaDB: %s", e)
    raise
