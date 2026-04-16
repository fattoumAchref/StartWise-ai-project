"""
Connexion SQLAlchemy async + session factory — SQLite local.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from config import cfg

engine = create_async_engine(
    cfg.database_url,
    echo=False,
    connect_args={"check_same_thread": False},  # requis pour SQLite
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency FastAPI — session DB par requête."""
    async with SessionLocal() as session:
        yield session


async def init_db():
    """Crée toutes les tables au démarrage."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
