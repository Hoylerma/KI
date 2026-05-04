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


def async_psycopg_url() -> str:
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
            connection=async_psycopg_url(),
            use_jsonb=True,
            async_mode=True,
        )
    return _vector_store


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db() -> None:
    """Create extension and initialize PGVector tables asynchronously."""
    # 1. Ensure the vector extension exists
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # 2. Get the vector store instance (NO await here)
    vs = get_vector_store()
    
    # 3. Safely create tables and the collection asynchronously
    await vs.acreate_tables_if_not_exists()
    await vs.acreate_collection()


async def close_db() -> None:
    """Release shared resources."""
    global _pool, _vector_store
    if _pool:
        await _pool.close()
        _pool = None
    _vector_store = None
