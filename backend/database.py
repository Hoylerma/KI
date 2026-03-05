import asyncio

import asyncpg
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector

from config import (
    COLLECTION_NAME,
    DATABASE_URL,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
)

_vector_store: PGVector | None = None
_pool: asyncpg.Pool | None = None


def _psycopg_url() -> str:
    """Convert a standard postgresql:// URL to psycopg3 format."""
    return DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def get_vector_store() -> PGVector:
    global _vector_store
    if _vector_store is None:
        embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        _vector_store = PGVector(
            embeddings=embeddings,
            collection_name=COLLECTION_NAME,
            connection=_psycopg_url(),
            use_jsonb=True,
        )
    return _vector_store


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db() -> None:
    """Create the pgvector extension and initialize the PGVector tables."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # PGVector creates its own tables (langchain_pg_collection,
    # langchain_pg_embedding) on first use; trigger that now.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_vector_store)


async def close_db() -> None:
    """Release shared resources."""
    global _pool, _vector_store
    if _pool:
        await _pool.close()
        _pool = None
    _vector_store = None
