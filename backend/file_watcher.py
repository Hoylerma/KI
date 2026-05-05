"""
Überwacht einen Ordner und ingestiert neue/geänderte Dateien
automatisch in die RAG-Pipeline.
"""

import asyncio
from datetime import datetime
import hashlib
import logging
import os
from typing import Dict


from config import CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION_NAME
from database import get_pool, get_vector_store
from documents import delete_document
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from parsers import parse_document

logger = logging.getLogger("bwiki.watcher")

# Nur diese Formate werden automatisch aus dem Watch-Ordner ingestiert.
ALLOWED_EXTENSIONS = {"pdf", "docx", "jpg", "jpeg", "png"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def file_hash(filepath: str) -> str:
    """Berechnet MD5-Hash einer Datei zur Änderungserkennung."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_directory(watch_dir: str) -> Dict[str, dict]:
    """Scannt den Ordner und gibt alle gültigen Dateien zurück."""
    files = {}
    for root, _, filenames in os.walk(watch_dir):
        for filename in filenames:
            if filename.startswith(("~$", ".", "~", "._")):
                continue

            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ALLOWED_EXTENSIONS:
                continue

            filepath = os.path.join(root, filename)

            try:
                if os.path.getsize(filepath) > MAX_FILE_SIZE:
                    logger.warning(f"Datei zu groß, übersprungen: {filename}")
                    continue

                rel_path = os.path.relpath(filepath, watch_dir)

                files[rel_path] = {
                    "filepath": filepath,
                    "hash": file_hash(filepath),
                }
            except (PermissionError, OSError) as e:
                logger.warning(f"Zugriff verweigert auf '{filename}', wird übersprungen. Grund: {e}")
                continue

    return files


async def get_indexed_files() -> Dict[str, str]:
    """Holt alle bereits indizierten Dateien mit ihrem Hash aus der DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT
                e.cmetadata->>'filename' AS filename,
                e.cmetadata->>'file_hash' AS file_hash
            FROM langchain_pg_embedding e
            JOIN langchain_pg_collection c ON e.collection_id = c.uuid
            WHERE c.name = $1
              AND e.cmetadata->>'filename' IS NOT NULL
            """,
            COLLECTION_NAME,
        )
    return {r["filename"]: r["file_hash"] for r in rows}


async def sync_documents(watch_dir: str) -> dict:
    """
    Synchronisiert den Ordner mit der Vektordatenbank.
    - Neue Dateien → ingestieren
    - Geänderte Dateien → neu ingestieren
    - Gelöschte Dateien → aus DB entfernen
    """
    stats = {"added": 0, "updated": 0, "deleted": 0, "unchanged": 0, "errors": 0}

    # Aktuelle Dateien im Ordner
    current_files = scan_directory(watch_dir)

    # Bereits indizierte Dateien
    indexed_files = await get_indexed_files()

    # 1) Neue und geaenderte Dateien verarbeiten.
    #    Vergleich erfolgt ueber den gespeicherten Datei-Hash.
    for rel_path, info in current_files.items():
        try:
            old_hash = indexed_files.get(rel_path)

            if old_hash == info["hash"]:
                stats["unchanged"] += 1
                continue

            # Datei lesen und ingestieren
            with open(info["filepath"], "rb") as f:
                file_bytes = f.read()

            # Metadata mit Hash für spätere Änderungserkennung
            result = await ingest_document_with_hash(
                rel_path, file_bytes, info["hash"]
            )

            if old_hash is None:
                stats["added"] += 1
                logger.info(f"✅ Neu: {rel_path} ({result['chunks']} Chunks)")
            else:
                stats["updated"] += 1
                logger.info(f"🔄 Aktualisiert: {rel_path} ({result['chunks']} Chunks)")

        except (PermissionError, OSError) as e:
            stats["errors"] += 1
            logger.error(f"❌ Fehler bei {rel_path}: {e}")

    # 2) Gelöschte Dateien aus der DB entfernen.
    for indexed_name in indexed_files:
        if indexed_name not in current_files:
            await delete_document(indexed_name)
            stats["deleted"] += 1
            logger.info(f"🗑️ Gelöscht: {indexed_name}")

    return stats


# file_watcher.py (nur diese Funktion ersetzen)

async def ingest_document_with_hash(
    filename: str, file_bytes: bytes, file_hash: str, collection_name: str = None, filepath: str = None, timestamp: datetime = None) -> dict:
    """
    Parse -> Split -> Metadaten setzen -> in PGVector speichern.
    file_hash wird mitgespeichert, damit spaetere Aenderungen erkannt werden.
    """

    # 1. Dokument parsen (z.B. mit Docling zu Markdown)
    text = parse_document(filename, file_bytes)
    if not text.strip():
        logger.warning(f"Dokument ist leer oder unlesbar, wird übersprungen: {filename}")
        return {"filename": filename, "chunks": 0}

    # 2. Definiere, welche Markdown-Überschriften zum Splitten genutzt werden sollen
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]

    # 3. Zuerst nach der logischen Struktur (Markdown-Überschriften) splitten
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_splits = markdown_splitter.split_text(text)

    # 4. Optional: Falls einige Kapitel extrem lang sind, zerschneide sie zusätzlich nach Länge
    # (Damit du die maximale Token-Größe für dein Embedding-Modell nicht überschreitest)
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    final_chunks = char_splitter.split_documents(md_splits)

    # 5. Erstelle die LangChain Documents und behalte die Metadaten!
    documents = []
    for i, chunk in enumerate(final_chunks):
        # Der markdown_splitter hat bereits Metadaten wie {"Header 1": "Kapitel 1"} generiert.
        # Wir fügen unsere eigenen Metadaten (Dateiname, Hash) einfach hinzu.
        metadata = chunk.metadata.copy() # Kopiere die Header-Metadaten
        metadata.update({
            "source": filename,
            "filename": filename,
            "filepath": filepath,
            "file_hash": file_hash,
            "last_modified": timestamp,
            "chunk_index": i,
        })
        
        documents.append(
            Document(
                page_content=chunk.page_content,
                metadata=metadata,
            )
        )

    # 6. In die Vector-DB laden
    target_collection = collection_name if collection_name else COLLECTION_NAME
    vs = get_vector_store(collection_name=target_collection)
    
    if not collection_name:
        # In der Standard-Collection wird vor dem Re-Import die alte Version geloescht,
        # damit keine doppelten Chunks fuer denselben Dateinamen entstehen.
        await delete_document(filename)
        
    await vs.aadd_documents(documents)

    return {"filename": filename, "chunks": len(documents)}


async def watch_loop(watch_dir: str, interval: int = 300):
    """Endlosschleife: Synchronisiert alle X Sekunden."""
    logger.info(f"👁️ File Watcher gestartet: {watch_dir} (alle {interval}s)")

    while True:
        try:
            stats = await sync_documents(watch_dir)
            if any(v > 0 for key, v in stats.items() if key != "unchanged"):
                logger.info(
                    f"📊 Sync: +{stats['added']} neu, "
                    f"~{stats['updated']} aktualisiert, "
                    f"-{stats['deleted']} gelöscht, "
                    f"={stats['unchanged']} unverändert, "
                    f"!{stats['errors']} Fehler"
                )
        except (PermissionError, OSError) as e:
            logger.error(f"Sync-Fehler: {e}")

        await asyncio.sleep(interval)