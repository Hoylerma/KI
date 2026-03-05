from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from config import CHAT_MODEL, OLLAMA_BASE_URL
from database import close_db, init_db
from documents import delete_document, ingest_document, list_documents
from retrieval import rag_search_async

app = FastAPI()


origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:80",
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


@app.on_event("startup")
async def startup():
    await init_db()


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
            detail=f"Dateiformat .{ext} nicht unterstützt. Erlaubt: {', '.join(allowed_extensions)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Die Datei ist leer.")
    if len(file_bytes) > 50 * 1024 * 1024:  # 50 MB Limit
        raise HTTPException(status_code=400, detail="Datei zu groß (max. 50 MB).")

    try:
        result = await ingest_document(file.filename, file_bytes)
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
    # Deterministic RAG: retrieve context first, then stream LLM response.
    try:
        rag_context = await rag_search_async(prompt)
    except Exception as e:
        print(f"RAG-Kontext konnte nicht abgerufen werden: {e}")
        rag_context = ""

    system_content = "Du bist ein hilfreicher Assistent. Antworte immer auf Deutsch."

    if rag_context:
        user_content = (
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

    try:
        async for chunk in llm.astream(messages):
            if await request.is_disconnected():
                print("Client hat die Verbindung getrennt")
                return
            yield chunk.content
    except Exception as e:
        print(f"Fehler bei der Anfrage an Ollama: {e}")
        yield "\n\n[Fehler: Verbindung zu Ollama fehlgeschlagen]"


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


