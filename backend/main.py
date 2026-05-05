import asyncio
import logging
import os
import shutil
import uuid
from starlette.background import BackgroundTask

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT
from database import close_db, init_db
from documents import delete_document, list_documents
from file_watcher import ingest_document_with_hash, sync_documents, watch_loop
from agents.rag import stream_response
from agents.summary import summary_agent
from database import save_chat_message, get_recent_messages, get_latest_session_for_user

app = FastAPI()

# Watcher-Einstellungen: Falls WATCH_DIR gesetzt ist, wird ein Hintergrund-Sync gestartet.
WATCH_DIR = os.getenv("WATCH_DIR", "")
WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "30"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bwiki")

origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Neues Modell mit session_id ---
class ChatMessage(BaseModel):
    # message: eigentliche Nutzerfrage
    # profile: steuert, welcher Agent/Funktionspfad genutzt wird
    # session_id: verweist optional auf eine Upload-spezifische Vector-Collection
    message: str
    profile: str
    session_id: str | None = None  # Optional, für RAG-Uploads
    username: str | None = None


@app.on_event("shutdown")
async def shutdown():
    await close_db()

@app.get("/")
async def root():
    return {"status": "Backend läuft", "engine": "Ollama ready"}



@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Lädt ein Dokument hoch, parst es und gibt eine session_id zurück."""
    allowed_extensions = {"pdf", "docx", "txt", "md", "csv", "json", "xml", "html"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Dateiformat .{ext} nicht unterstützt. Erlaubt: {', '.join(sorted(allowed_extensions))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Die Datei ist leer.")
    if len(file_bytes) > 50 * 1024 * 1024:  # 50 MB Limit
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB).")

    # Jeder Upload bekommt eine eigene Collection-ID,
    # damit Dokumentfragen isoliert pro Upload beantwortet werden koennen.
    session_id = str(uuid.uuid4())

    try:
        # Hier übergeben wir die session_id an deine Ingest-Logik.
        # WICHTIG: Du musst in deiner file_watcher.py sicherstellen, 
        # dass ingest_document_with_hash die "collection_name" oder Metadaten auch verarbeitet!
        result = await ingest_document_with_hash(file.filename, file_bytes, "", collection_name=session_id)
        
        # Sende die session_id zurück ans Frontend
        return {"status": "success", "session_id": session_id, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents")
async def get_documents():
    docs = await list_documents()
    return {"documents": docs}

@app.delete("/documents/{filename}")
async def remove_document(filename: str):
    deleted = await delete_document(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
    return {"status": "deleted", "filename": filename}



@app.post("/chat")
async def chat(data: ChatMessage, request: Request):
    """Leitet Chat-Anfragen an den Stream weiter und speichert sicher im Hintergrund."""
    user_message = data.message
    selected_profile = getattr(data, "profile", "RAG-Suche") 
    session_id = getattr(data, "session_id", None)
    
    # NEU: Username sicher auslesen (Fall-Back, falls keiner gesendet wird)
    username = data.username or "anonym" 

    if not session_id:
        session_id = str(uuid.uuid4())

    # 1. ZUERST bisherigen Verlauf laden
    raw_history = await get_recent_messages(session_id, limit=4) 
    raw_history.reverse() 
    formatted_history = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in raw_history])

    # 2. DANN die neue User-Nachricht SOFORT in der DB speichern
    await save_chat_message(session_id, username, "user", user_message)

    # 3. Der neue, sichere Stream-Wrapper
    # Wir nutzen eine Liste als "Container", um den Text aus dem Stream abzufangen
    bot_response_container = [""] 

    async def stream_wrapper(generator):
        async for chunk in generator:
            bot_response_container[0] += chunk
            yield chunk

    # 4. Diese Funktion läuft als BackgroundTask, NACHDEM der Stream fertig ist
    async def save_bot_message_to_db():
        final_text = bot_response_container[0].strip()
        if final_text:
            # Jetzt speichern wir den kompletten Text ganz in Ruhe ab
            await save_chat_message(session_id, username, "assistant", final_text)

    # 5. Routing an die Agenten
    if selected_profile == "RAG-Suche":
        generator = stream_response(user_message, request, history=formatted_history)
    elif selected_profile == "Summary-Agent":
        generator = summary_agent(user_message, request, session_id=session_id, history=formatted_history)
    else:
        generator = stream_response(user_message, request, history=formatted_history)

    # 6. Stream mit angehängter Hintergrundaufgabe zurückgeben
    return StreamingResponse(
        stream_wrapper(generator),
        media_type="text/event-stream",
        background=BackgroundTask(save_bot_message_to_db) # <--- HIER passiert die Magie
    )

@app.on_event("startup")
async def startup():
    await init_db()
    if WATCH_DIR and os.path.isdir(WATCH_DIR):
        asyncio.create_task(watch_loop(WATCH_DIR, WATCH_INTERVAL))

@app.post("/sync")
async def trigger_sync():
    if not WATCH_DIR or not os.path.isdir(WATCH_DIR):
        raise HTTPException(status_code=400, detail="Kein Watch-Verzeichnis konfiguriert")
    stats = await sync_documents(WATCH_DIR)
    return {"status": "synced", **stats}

@app.get("/history/{username}")
async def get_history(username: str):
    """Gibt den letzten Chatverlauf eines Nutzers zurück."""
    data = await get_latest_session_for_user(username)
    if not data:
        return {"session_id": None, "messages": []}
    return data