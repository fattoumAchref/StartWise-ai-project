"""
Point d'entrée — Agent Légal IA pour startups tunisiennes.
Lance le serveur FastAPI, initialise la DB et le vector store.

Démarrage : uvicorn main:app --reload
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import structlog

from config import cfg
from database import init_db
from vector_store import vector_store
from api import router

log = structlog.get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialisation au démarrage, nettoyage à l'arrêt."""
    log.info("starting", env=cfg.app_env, model=cfg.llm_model)

    # 1. Création des tables SQL
    await init_db()
    log.info("database_ready")

    # 2. Création des collections ChromaDB
    await vector_store.async_setup()
    log.info("vector_store_ready")

    yield  # L'application tourne ici

    log.info("shutdown")


app = FastAPI(
    title="Agent Légal IA — Tunisie",
    description=(
        "Conseiller juridique intelligent pour startups et entreprises tunisiennes. "
        "Création d'entreprise · Protection IP · Contrats · Levée de fonds · Conformité."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Agent Légal IA — Tunisie",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "model": cfg.llm_model}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Avoid noisy 404 logs when the browser automatically requests favicon.
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=cfg.app_host, port=cfg.app_port, reload=cfg.app_debug)
