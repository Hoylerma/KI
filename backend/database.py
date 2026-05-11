import asyncpg
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
import datetime

from config import (
    COLLECTION_NAME,
    DATABASE_URL,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
)

# Gemeinsamer Async-Pool fuer direkte SQL-Operationen.
_pool: asyncpg.Pool | None = None


def async_psycopg_url() -> str:
    """Convert a standard postgresql:// URL to psycopg3 format."""
    return DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)




def get_vector_store(collection_name: str = None) -> PGVector:
    """
    Erstellt ein PGVector Objekt.
    Wenn collection_name übergeben wird, nutzt es diese spezifische Collection (z.B. session_id).
    Ansonsten nutzt es die globale Standard-Collection für das K-Laufwerk.
    """
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    
    # Entscheide, welche Collection genutzt werden soll
    target_collection = collection_name if collection_name else COLLECTION_NAME
    
    # Wir instanziieren PGVector hier dynamisch. 
    # Das ist performant, da die eigentlichen DB-Verbindungen 
    # im Hintergrund über den async_psycopg Treiber / Connection Pool laufen.
    return PGVector(
        embeddings=embeddings,
        collection_name=target_collection,
        connection=async_psycopg_url(),
        use_jsonb=True,
        async_mode=True,
    )


async def get_pool() -> asyncpg.Pool:
    """Liefert (und cached) den asyncpg Connection-Pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def init_db() -> None:
    """Create extension, initialize PGVector tables and Chat History asynchronously."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Ensure the vector extension exists
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # 2. Chat-Historie Tabelle und Index erstellen (NEU)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_session_id ON chat_history(session_id);
        """)
    
    # 3. Get the vector store instance for the default collection
    vs = get_vector_store()
    
    # 4. Safely create tables and the collection asynchronously
    await vs.acreate_tables_if_not_exists()
    await vs.acreate_collection()


# --- NEUE FUNKTIONEN FÜR DIE CHAT-HISTORIE ---

async def get_latest_session_for_user(username: str) -> dict | None:
    """Sucht die aktuellste session_id eines Nutzers und lädt den Verlauf."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Finde die letzte Session-ID des Nutzers
        session_row = await conn.fetchrow(
            "SELECT session_id FROM chat_history WHERE username = $1 ORDER BY created_at DESC LIMIT 1",
            username
        )
        if not session_row:
            return None
            
        session_id = session_row["session_id"]
        
        # Lade alle Nachrichten dieser Session (aufsteigend sortiert für die UI)
        rows = await conn.fetch(
            "SELECT role, content FROM chat_history WHERE session_id = $1 ORDER BY created_at ASC",
            session_id
        )
        messages = [{"role": row["role"], "content": row["content"]} for row in rows]
        
        return {"session_id": session_id, "messages": messages}

async def save_chat_message(session_id: str, username: str, role: str, content: str) -> None:
    """Speichert eine Nachricht inklusive Nutzernamen."""
    pool = await get_pool()
    async with pool.acquire() as conn:
       
        await conn.execute(
            "INSERT INTO chat_history (session_id, username, role, content) VALUES ($1, $2, $3, $4)",
            session_id, username, role, content
        )

async def get_recent_messages(session_id: str, limit: int = 6) -> list[dict]:
    """Holt die letzten X Nachrichten einer Session. Gibt eine Liste von Dicts zurück."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT role, content FROM chat_history WHERE session_id = $1 ORDER BY created_at DESC LIMIT $2",
            session_id, limit
        )
        return [{"role": row["role"], "content": row["content"]} for row in rows]


async def close_db() -> None:
    """Release shared resources."""
    global _pool
    if _pool:
        # Beim Shutdown aktive Verbindungen sauber schliessen.
        await _pool.close()
        _pool = None