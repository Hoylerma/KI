
import asyncio
import logging
import os
import time

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from auth import check_ldap_login
from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT
from database import close_db, init_db
from documents import delete_document, list_documents
from file_watcher import ingest_document_with_hash, sync_documents, watch_loop
from retrieval import rag_search_async

app = FastAPI()

WATCH_DIR = os.getenv("WATCH_DIR", "")
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "30"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bwiki")


origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:80",
    "http://localhost:8080",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.on_event("shutdown")
async def shutdown():
    await close_db()


@app.get("/")
async def root():
    return {"status": "Backend läuft", "engine": "Ollama ready"}


# ---------------------------------------------------------------------------
# Dokument-Upload & Verwaltung
# ---------------------------------------------------------------------------

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Lädt ein Dokument hoch und speichert es in der RAG-Pipeline."""
    allowed_extensions = {"pdf", "docx", "txt", "md", "csv", "json", "xml", "html"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dateiformat .{ext} nicht unterstützt. "
                f"Erlaubt: {', '.join(sorted(allowed_extensions))}"
            ),
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Die Datei ist leer.")
    if len(file_bytes) > 50 * 1024 * 1024:  # 50 MB Limit
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB).")

    try:
        result = await ingest_document_with_hash(file.filename, file_bytes, "")
        return {"status": "success", **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def get_documents():
    """Listet alle hochgeladenen Dokumente auf."""
    docs = await list_documents()
    return {"documents": docs}


@app.delete("/documents/{filename}")
async def remove_document(filename: str):
    """Löscht ein Dokument aus der RAG-Datenbank."""
    deleted = await delete_document(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return {"status": "deleted", "filename": filename}


# ---------------------------------------------------------------------------
# Chat mit RAG-Kontext
# ---------------------------------------------------------------------------


async def stream_response(prompt: str, request: Request):
    # 1. RAG-Kontext holen
    try:
        rag_context = await rag_search_async(prompt)
    except Exception as e:
        logger.warning(f"RAG-Kontext fehlgeschlagen: {e}")
        rag_context = ""

    # ── Kontext loggen ──────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"📝 FRAGE: {prompt}")
    if rag_context:
        logger.info(f"📚 RAG-KONTEXT ({len(rag_context)} Zeichen):")
        logger.info(rag_context[:500] + ("..." if len(rag_context) > 500 else ""))
    else:
        logger.info("📚 RAG-KONTEXT: Keiner gefunden")
    logger.info("=" * 60)

    system_content = SYSTEM_PROMPT

    if rag_context:
        user_content = (
            "Du bist ein interner Wissens-Assistent. "
            "Beantworte die folgende Frage basierend auf dem bereitgestellten Kontext. "
            "Wenn der Kontext nicht ausreicht, nutze dein allgemeines Wissen, aber weise darauf hin. "
            "Nenne am Ende die verwendeten Quellen.\n\n"
            f"--- KONTEXT ---\n{rag_context}\n--- ENDE KONTEXT ---\n\n"
            f"Frage: {prompt}"
        )
    else:
        user_content = prompt

    llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL)
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]

    # ── Token-Zählung & Geschwindigkeit ─────────────────────
    token_count = 0
    start_time = time.perf_counter()
    first_token_time = None

    try:
        async for chunk in llm.astream(messages):
            if await request.is_disconnected():
                logger.info("Client hat die Verbindung getrennt")
                return

            token_count += 1
            if first_token_time is None:
                first_token_time = time.perf_counter()

            yield chunk.content

    except Exception as e:
        logger.error(f"Fehler bei Ollama: {e}")
        yield "\n\n[Fehler: Verbindung zu Ollama fehlgeschlagen]"

    finally:
        # ── Statistiken ausgeben ────────────────────────────
        total_time = time.perf_counter() - start_time
        ttft = (first_token_time - start_time) if first_token_time else 0
        tps = token_count / total_time if total_time > 0 else 0

        logger.info("-" * 60)
        logger.info(f"⚡ PERFORMANCE:")
        logger.info(f"   Modell:              {CHAT_MODEL}")
        logger.info(f"   Tokens generiert:    {token_count}")
        logger.info(f"   Gesamtzeit:          {total_time:.2f}s")
        logger.info(f"   Time to first token: {ttft:.2f}s")
        logger.info(f"   Tokens/Sekunde:      {tps:.1f} t/s")
        logger.info(f"   Kontext-Länge:       {len(user_content)} Zeichen")
        logger.info("-" * 60)


@app.post("/chat")
async def chat(data: ChatMessage, request: Request):
    return StreamingResponse(
        stream_response(data.message, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Content-Type-Options": "nosniff",
        },
    )

@app.post("/api/login")
async def login_endpoint(req: LoginRequest):
    login_ok = check_ldap_login(req.username, req.password)

    if not login_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falscher Benutzername oder Passwort",
        )

    return {"message": "Login erfolgreich", "access_token": "ldap-okay-token"}

@app.on_event("startup")
async def startup():
    await init_db()

    # File Watcher starten (wenn Ordner konfiguriert)
    if WATCH_DIR and os.path.isdir(WATCH_DIR):
        asyncio.create_task(watch_loop(WATCH_DIR, WATCH_INTERVAL))


# Manueller Sync-Endpunkt
@app.post("/sync")
async def trigger_sync():
    """Erzwingt eine sofortige Synchronisierung des Dokumentenordners."""
    if not WATCH_DIR or not os.path.isdir(WATCH_DIR):
        raise HTTPException(status_code=400, detail="Kein Watch-Verzeichnis konfiguriert")

    stats = await sync_documents(WATCH_DIR)
    return {"status": "synced", **stats}


