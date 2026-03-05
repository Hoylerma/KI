from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME
from database import get_pool, get_vector_store
from parsers import parse_document


async def ingest_document(filename: str, file_bytes: bytes) -> dict:
    """Parse, split, embed, and store a document via LangChain PGVector."""
    text = parse_document(filename, file_bytes)
    if not text.strip():
        raise ValueError("Dokument ist leer oder konnte nicht gelesen werden.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_text(text)
    if not chunks:
        raise ValueError("Konnte keine Text-Chunks erstellen.")

    documents = [
        Document(
            page_content=chunk,
            metadata={"source": filename, "filename": filename, "chunk_index": i},
        )
        for i, chunk in enumerate(chunks)
    ]

    # Remove previous version of this document, then add fresh chunks.
    await delete_document(filename)
    vs = get_vector_store()
    await vs.aadd_documents(documents)

    return {
        "filename": filename,
        "chunks": len(chunks),
        "characters": len(text),
    }


async def list_documents() -> List[dict]:
    """List all documents stored in the vector store (grouped by filename)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                e.cmetadata->>'filename' AS filename,
                COUNT(*) AS chunks
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = $1
              AND e.cmetadata->>'filename' IS NOT NULL
            GROUP BY e.cmetadata->>'filename'
            ORDER BY MAX(e.id) DESC
            """,
            COLLECTION_NAME,
        )
    return [{"filename": r["filename"], "chunks": r["chunks"]} for r in rows]


async def delete_document(filename: str) -> bool:
    """Delete all chunks belonging to *filename* from the vector store."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM langchain_pg_embedding
            WHERE collection_id = (
                SELECT uuid FROM langchain_pg_collection WHERE name = $1
            )
            AND cmetadata->>'filename' = $2
            """,
            COLLECTION_NAME,
            filename,
        )
    return result != "DELETE 0"
