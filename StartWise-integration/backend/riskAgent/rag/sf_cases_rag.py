import json
import numpy as np
import faiss
import os
from sentence_transformers import SentenceTransformer

# =========================================================
# MODEL
# =========================================================
model = SentenceTransformer("all-MiniLM-L6-v2")

_DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "data")
INDEX_FILE = os.path.join(_DATA_DIR, "startup_index.faiss")
DATA_FILE  = os.path.join(_DATA_DIR, "sf_cases.json")


# =========================================================
# LOAD DATA
# =========================================================
def load_data(path=None):
    if path is None:
        path = os.path.join(_DATA_DIR, "startup_failure_cases_cleaned.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["structured_data"]


# =========================================================
# BUILD DOCUMENT
# =========================================================
def build_doc(item):
    return f"""
Sector: {item.get('sector','')}
Country: {item.get('country','')}
Funding: {item.get('funding','')}
Causes: {', '.join(item.get('cause', []))}
Description: {item.get('description','')}
Founded: {item.get('founded','')}
Closed: {item.get('closed','')}
""".strip()


# =========================================================
# RAG SYSTEM
# =========================================================
class StartupRAG:

    def __init__(self, data):

        self.data = data
        self.docs = [build_doc(d) for d in data]

        # check if index exists
        if os.path.exists(INDEX_FILE):
            print("[RAG] Loading FAISS index...")
            self.index = faiss.read_index(INDEX_FILE)

        else:
            print("[RAG] Building FAISS index...")

            embeddings = model.encode(
                self.docs,
                show_progress_bar=True,
                normalize_embeddings=True
            )

            embeddings = np.array(embeddings).astype("float32")

            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dim)
            self.index.add(embeddings)

            # SAVE INDEX
            faiss.write_index(self.index, INDEX_FILE)

            # SAVE DATA (important sync)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)

        print(f"[RAG] Ready with {len(self.data)} startups")


    # =====================================================
    # RUN  (convenience wrapper used by risk_agent.py)
    # =====================================================
    def run(self, description: str, k: int = 5) -> dict:
        """Returns {"similar_cases": [...]} with score field mapped from similarity."""
        results = self.search(description, k=k)
        cases = []
        for r in results:
            cases.append({
                "startup":     r.get("startup"),
                "sector":      r.get("sector"),
                "country":     r.get("country"),
                "funding":     r.get("funding"),
                "cause":       r.get("cause", []),
                "description": r.get("description", ""),
                "score":       r.get("similarity", 0.0),
            })
        return {"similar_cases": cases}

    # =====================================================
    # SEARCH
    # =====================================================
    def search(self, query, k=5):

        query_vec = model.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec).astype("float32")

        scores, indices = self.index.search(query_vec, k)

        results = []

        for i, idx in enumerate(indices[0]):

            item = self.data[idx]

            results.append({
                "startup": item.get("startup"),
                "sector": item.get("sector"),
                "country": item.get("country"),
                "funding": item.get("funding"),
                "cause": item.get("cause"),
                "description": item.get("description"),
                "similarity": float(scores[0][i])
            })

        return results


    # =====================================================
    # RISK CONTEXT (NO WEIGHTS)
    # =====================================================
    def get_risk_context(self, startup, k=5):

        query = self._build_query(startup)

        results = self.search(query, k=k)

        context = []

        for r in results:
            context.append({
                "startup": r["startup"],
                "sector": r["sector"],
                "country": r["country"],
                "funding": r["funding"],
                "cause": r["cause"],
                "similarity": round(r["similarity"], 3)
            })

        return context


    # =====================================================
    # QUERY BUILDER (CRITICAL FIX)
    # =====================================================
    def _build_query(self, startup):

        return f"""
Sector: {startup.get('sector','')}
Country: {startup.get('country','')}
Funding: {startup.get('funding','')}
Idea: {startup.get('idea','')}
Team: {startup.get('team','')}
"""


# =========================================================
# BUILD RAG
# =========================================================
def build_rag():
    data = load_data()
    return StartupRAG(data)


# =========================================================
# TEST 
# =========================================================
if __name__ == "__main__":

    rag = build_rag()

    new_startup = {
        "sector": "Transportation",
        "country": "United States",
        "funding": "$2M",
        "idea": "AI bus optimization platform",
        "team": "small technical team"
    }

    context = rag.get_risk_context(new_startup)

    print("\n=== RISK CONTEXT ===\n")

    for c in context:
        print(c)