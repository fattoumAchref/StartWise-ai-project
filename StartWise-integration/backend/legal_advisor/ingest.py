"""
Ingestion — lance tous les scrapers et charge les données dans ChromaDB.
Usage : python ingest.py
        python ingest.py --only jort
        python ingest.py --only dgi
        python ingest.py --only spdx
        python ingest.py --only innorpi
        python ingest.py --only jurisprudence
"""

import asyncio
import sys
import uuid
import os
import chromadb

EMBED_MODEL = "intfloat/multilingual-e5-base"
# Toujours pointer vers backend/chroma_db/ peu importe d'où on lance le script
CHROMA_PATH = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "chroma_db")

# ── Setup ─────────────────────────────────────────────────────────────────────

print("Chargement modèle embeddings...")


def load_embedding_model():
    """Charge SentenceTransformer avec des garde-fous sur les dépendances optionnelles."""
    # Evite le chargement des backends TF/Flax si présents mais incompatibles.
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(EMBED_MODEL)
    except Exception as e:
        raise RuntimeError(
            "Impossible de charger sentence-transformers. "
            "Cause probable: versions incompatibles entre torch/torchvision/transformers. "
            "Correctif recommande: desinstaller torchvision si inutile, puis reinstalller "
            "un couple compatible torch/torchvision et relancer pip install -r requirements.txt. "
            f"Erreur originale: {e}"
        ) from e


model = load_embedding_model()
print("OK")

chroma = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"},
)


def embed_batch(texts: list[str]) -> list[list[float]]:
    vecs = model.encode(
        [f"passage: {t[:512]}" for t in texts],
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=16,
    )
    return vecs.tolist()


def chunk_text(text: str, size: int = 600, overlap: int = 80) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        c = " ".join(words[i:i + size])
        if len(c) > 60:
            chunks.append(c)
        i += size - overlap
    return chunks


def store_chunks(chunks_data: list[dict]):
    """
    chunks_data : liste de {"content": str, "source_label": str, "metadata": dict}
    """
    if not chunks_data:
        return 0

    ids, embeddings, metadatas, documents = [], [], [], []
    texts = [c["content"] for c in chunks_data]
    vecs  = embed_batch(texts)

    for i, (chunk, vec) in enumerate(zip(chunks_data, vecs)):
        ids.append(str(uuid.uuid4()))
        embeddings.append(vec)
        meta = {**chunk.get("metadata", {}), "source_label": chunk.get("source_label", "?")}
        # ChromaDB n'accepte que str/int/float/bool dans les metadata
        meta = {k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                for k, v in meta.items()}
        metadatas.append(meta)
        documents.append(chunk["content"])

    collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    return len(ids)


# ── Scrapers ──────────────────────────────────────────────────────────────────

async def ingest_jort():
    print("\n[JORT] Démarrage scraping legislation.tn...")
    from scrapers.jort import JORTScraper
    scraper = JORTScraper()
    texts = await scraper.scrape_all()
    print(f"[JORT] {len(texts)} textes récupérés")

    total = 0
    for text in texts:
        title = text.get("title_fr", "Texte JORT")
        jort  = text.get("jort_number", "")
        date  = text.get("publication_date", "")
        status = text.get("status", "EN_VIGUEUR")
        articles = text.get("articles", [])

        chunks_data = []
        for art in articles:
            content = (
                f"{title}\n"
                f"JORT : {jort} | Date : {date} | Statut : {status}\n"
                f"Hiérarchie : {art.get('hierarchy_path', '')}\n\n"
                f"{art.get('content_fr', '')}"
            )
            for chunk in chunk_text(content):
                chunks_data.append({
                    "content": chunk,
                    "source_label": f"{art.get('article_number', '')} — {title} ({jort})",
                    "metadata": {
                        "domain": "LEGAL",
                        "status": status,
                        "jort_number": jort,
                        "publication_date": date,
                        "source_type": "JORT",
                    },
                })

        if chunks_data:
            n = store_chunks(chunks_data)
            total += n

    print(f"[JORT] {total} chunks indexés dans ChromaDB")


async def ingest_dgi():
    print("\n[DGI/CNSS] Démarrage scraping...")
    from scrapers.dgi_cnss import scrape_all
    raw_chunks = await scrape_all()
    print(f"[DGI/CNSS] {len(raw_chunks)} pages récupérées")

    chunks_data = []
    for rc in raw_chunks:
        for chunk in chunk_text(rc["content"]):
            chunks_data.append({
                "content": chunk,
                "source_label": rc["source_label"],
                "metadata": rc["metadata"],
            })

    n = store_chunks(chunks_data)
    print(f"[DGI/CNSS] {n} chunks indexés dans ChromaDB")


async def ingest_spdx():
    print("\n[SPDX] Démarrage scraping API spdx.org...")
    from scrapers.spdx import scrape_all
    raw_chunks = await scrape_all()
    print(f"[SPDX] {len(raw_chunks)} licences récupérées")

    chunks_data = []
    for rc in raw_chunks:
        for chunk in chunk_text(rc["content"]):
            chunks_data.append({
                "content": chunk,
                "source_label": rc["source_label"],
                "metadata": rc["metadata"],
            })

    n = store_chunks(chunks_data)
    print(f"[SPDX] {n} chunks indexés dans ChromaDB")


async def ingest_innorpi():
    print("\n[INNORPI] Démarrage scraping marques...")
    from scrapers.innorpi import INNORPIScraper
    scraper = INNORPIScraper()
    trademarks = await scraper.scrape_all()
    print(f"[INNORPI] {len(trademarks)} marques récupérées")

    chunks_data = []
    for tm in trademarks:
        # Page procédurale INNORPI
        if tm.get("_procedural"):
            for chunk in chunk_text(tm["_content"]):
                chunks_data.append({
                    "content": chunk,
                    "source_label": tm["_source_label"],
                    "metadata": {
                        "domain": "MARQUES",
                        "source_type": "INNORPI",
                        "url": tm["_url"],
                    },
                })
            continue

        # Marque enregistrée
        content = (
            f"Marque : {tm.get('name_exact', '')}\n"
            f"Titulaire : {tm.get('holder_name', '')}\n"
            f"Classes Nice : {tm.get('nice_classes', [])}\n"
            f"N° enregistrement : {tm.get('registration_number', '')}\n"
            f"Dépôt : {tm.get('filing_date', '')} | Expiration : {tm.get('expiry_date', '')}\n"
            f"Statut : {tm.get('status', '')}\n"
            f"Phonétique : {tm.get('name_phonetic', '')}"
        )
        chunks_data.append({
            "content": content,
            "source_label": f"Marque '{tm.get('name_exact')}' — INNORPI N°{tm.get('registration_number', '')}",
            "metadata": {
                "domain": "MARQUES",
                "status": tm.get("status", "ACTIF"),
                "source_type": "INNORPI",
            },
        })

    n = store_chunks(chunks_data)
    print(f"[INNORPI] {n} chunks indexés dans ChromaDB")


async def ingest_droit_societes():
    print("\n[DROIT SOCIÉTÉS] Démarrage scraping APII / Startup Act / RNE...")
    from scrapers.droit_societes import scrape_all
    raw_chunks = await scrape_all()
    print(f"[DROIT SOCIÉTÉS] {len(raw_chunks)} pages récupérées")

    chunks_data = []
    for rc in raw_chunks:
        for chunk in chunk_text(rc["content"]):
            chunks_data.append({
                "content": chunk,
                "source_label": rc["source_label"],
                "metadata": rc["metadata"],
            })

    n = store_chunks(chunks_data)
    print(f"[DROIT SOCIÉTÉS] {n} chunks indexés dans ChromaDB")


async def ingest_startups_db():
    print("\n[STARTUPS DB] Chargement base startups tunisiennes (API + CSV)...")
    from scrapers.startups_db import scrape_all
    raw_chunks = await scrape_all()
    print(f"[STARTUPS DB] {len(raw_chunks)} startups récupérées")

    chunks_data = []
    for rc in raw_chunks:
        for chunk in chunk_text(rc["content"]):
            chunks_data.append({
                "content": chunk,
                "source_label": rc["source_label"],
                "metadata": rc["metadata"],
            })

    n = store_chunks(chunks_data)
    print(f"[STARTUPS DB] {n} chunks indexés dans ChromaDB")


async def ingest_wipo():
    print("\n[WIPO CONSOLIDÉ] Démarrage scraping WIPO + F6S + Sources tunisiennes...")
    from scrapers.wipo import scrape_all
    raw_chunks = await scrape_all()
    print(f"[WIPO CONSOLIDÉ] {len(raw_chunks)} éléments récupérés")

    chunks_data = []
    for rc in raw_chunks:
        for chunk in chunk_text(rc["content"]):
            chunks_data.append({
                "content": chunk,
                "source_label": rc["source_label"],
                "metadata": rc["metadata"],
            })

    n = store_chunks(chunks_data)
    print(f"[WIPO CONSOLIDÉ] {n} chunks indexés dans ChromaDB")


# ── Main ──────────────────────────────────────────────────────────────────────

SCRAPERS = {
    "jort":            ingest_jort,
    "dgi":             ingest_dgi,
    "spdx":            ingest_spdx,
    "innorpi":         ingest_innorpi,
    "droit_societes":  ingest_droit_societes,
    "startups_db":     ingest_startups_db,
    "wipo":            ingest_wipo,
}


async def main():
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        idx = args.index("--only")
        if idx + 1 < len(args):
            only = args[idx + 1]

    before = collection.count()
    print(f"\nChromaDB : {before} chunks existants avant ingestion")

    if only:
        if only not in SCRAPERS:
            print(f"Scraper inconnu : {only}. Disponibles : {list(SCRAPERS)}")
            return
        await SCRAPERS[only]()
    else:
        for name, fn in SCRAPERS.items():
            try:
                await fn()
            except Exception as e:
                print(f"[{name.upper()}] ERREUR : {e}")

    after = collection.count()
    print(f"\nTerminé. ChromaDB : {after} chunks ({after - before} ajoutés)")


if __name__ == "__main__":
    asyncio.run(main())
