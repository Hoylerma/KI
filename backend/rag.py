"""
RAG Pipeline Module
- Dokument-Parsing (PDF, DOCX, TXT)
- Text-Chunking
- Embedding via Ollama
- Speicherung & Retrieval in pgvector
"""

import os
import asyncio
from typing import List, Tuple

import httpx
import asyncpg
from pypdf import PdfReader
from docx import Document as DocxDocument
import io

OLLAMA_API = os.getenv("OLLAMA_API", "http://ollama:11434")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpass@postgres:5432/ragdb")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
MAX_CHUNK_CHARS = 2000  # Maximale Zeichen pro Chunk, um pgvector-Limit zu vermeiden


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # Try to create the connection pool with retry/backoff.
        # This helps when the database container is still starting up.
        max_attempts = 12
        backoff = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
                return _pool
            except Exception as e:
                # Print to stdout so the docker logs show the attempts.
                print(f"DB connect attempt {attempt}/{max_attempts} failed: {e}")
                if attempt == max_attempts:
                    # Re-raise the last exception after exhausting retries.
                    raise
                # Wait before retrying (exponential backoff capped)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
    return _pool


async def init_db():
    """Erstellt die pgvector-Extension und die Dokumente-Tabelle."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector(768),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        # Index für Ähnlichkeitssuche
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx
            ON documents USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """)


async def close_db():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ---------------------------------------------------------------------------
# Document Parsing
# ---------------------------------------------------------------------------

def parse_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def parse_docx(file_bytes: bytes) -> str:
    doc = DocxDocument(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def parse_document(filename: str, file_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        return parse_pdf(file_bytes)
    elif ext in ("docx",):
        return parse_docx(file_bytes)
    elif ext in ("txt", "md", "csv", "json", "xml", "html"):
        return parse_txt(file_bytes)
    else:
        raise ValueError(f"Nicht unterstütztes Dateiformat: .{ext}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            # Nullbytes raus + harte Zeichenbegrenzung
            chunk = chunk.replace("\x00", "")
            if len(chunk) > MAX_CHUNK_CHARS:
                chunk = chunk[:MAX_CHUNK_CHARS]
            chunks.append(chunk)

        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Embeddings via Ollama
# ---------------------------------------------------------------------------

async def get_embedding(text: str) -> List[float]:
    """Erstellt ein Embedding über die Ollama API."""
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.post(
                f"{OLLAMA_API}/api/embeddings",
                json={"model": EMBEDDING_MODEL, 
                      "prompt": text
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embedding", [])
    except Exception as e:
        # Log helpful information for debugging in container logs
        print(f"Error requesting embedding from {OLLAMA_API}: {e}")
        raise


async def get_embeddings_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """Erstellt Embeddings in Batches."""
    embeddings: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        results = await asyncio.gather(*[get_embedding(t) for t in batch])
        embeddings.extend(results)
    return embeddings


# ---------------------------------------------------------------------------
# Ingest (Speicherung)
# ---------------------------------------------------------------------------

async def ingest_document(filename: str, file_bytes: bytes) -> dict:
    """
    Verarbeitet ein hochgeladenes Dokument:
    1. Parsen  2. Chunking  3. Embedding  4. Speichern in pgvector
    """
    text = parse_document(filename, file_bytes)
    if not text.strip():
        raise ValueError("Dokument ist leer oder konnte nicht gelesen werden.")

    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Konnte keine Text-Chunks erstellen.")

    embeddings = await get_embeddings_batch(chunks)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Alte Chunks desselben Dokuments löschen
        await conn.execute("DELETE FROM documents WHERE filename = $1", filename)

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            await conn.execute(
                """
                INSERT INTO documents (filename, chunk_index, content, embedding)
                VALUES ($1, $2, $3, $4::vector)
                """,
                filename,
                idx,
                chunk,
                emb_str,
            )

    return {
        "filename": filename,
        "chunks": len(chunks),
        "characters": len(text),
    }


# ---------------------------------------------------------------------------
# Retrieval (Suche)
# ---------------------------------------------------------------------------

async def search_similar(query: str, top_k: int = 5) -> List[Tuple[str, str, float]]:
    """
    Sucht die ähnlichsten Dokument-Chunks zur Anfrage.
    Gibt Liste von (filename, content, score) zurück.
    """
    query_embedding = await get_embedding(query)
    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT filename, content,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM documents
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            emb_str,
            top_k,
        )

    return [(r["filename"], r["content"], r["similarity"]) for r in rows]


MAX_CONTEXT_CHARS = 4000  # Maximale Zeichenlänge für RAG-Kontext


async def build_rag_context(query: str, top_k: int = 5, min_similarity: float = 0.3) -> str:
    """
    Baut den RAG-Kontext für einen Chat-Prompt auf.
    Gibt einen formatierten Kontext-String zurück oder leer wenn nichts gefunden.
    Begrenzt den Kontext auf MAX_CONTEXT_CHARS Zeichen.
    """
    results = await search_similar(query, top_k)
    relevant = [(fn, content, score) for fn, content, score in results if score >= min_similarity]

    if not relevant:
        return ""

    context_parts = []
    total_len = 0
    for fn, content, score in relevant:
        part = f"[Quelle: {fn} | Relevanz: {score:.2f}]\n{content}"
        if total_len + len(part) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_len
            if remaining > 100:
                context_parts.append(part[:remaining] + "...")
            break
        context_parts.append(part)
        total_len += len(part) + 7  # +7 für Separator

    return "\n\n---\n\n".join(context_parts)


async def list_documents() -> List[dict]:
    """Listet alle gespeicherten Dokumente auf."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT filename, COUNT(*) as chunks, MAX(created_at) as uploaded_at
            FROM documents
            GROUP BY filename
            ORDER BY MAX(created_at) DESC
        """)
    return [{"filename": r["filename"], "chunks": r["chunks"], "uploaded_at": str(r["uploaded_at"])} for r in rows]


async def delete_document(filename: str) -> bool:
    """Löscht ein Dokument und alle zugehörigen Chunks."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM documents WHERE filename = $1", filename)
    return result != "DELETE 0"
