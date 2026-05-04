import os
import re
from pathlib import Path
from typing import Any

from ldap3 import ALL, Connection, Server
import chainlit as cl
import httpx

# --- Konfiguration ---
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
STREAM_TIMEOUT = httpx.Timeout(None, connect=10.0)
BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
LDAP_SERVER_URL = os.getenv("LDAP_SERVER_URL", "ldap://12353-DC01.bwi.local")

# WICHTIG: Das ist der Ordner im Container, wo die PDFs liegen.
# Diesen musst du in deiner docker-compose.yml bei "chainlit" als Volume mounten!
WATCHED_DOCS_DIR = Path("/app/watched_docs")


def backend_url(path: str) -> str:
    return f"{BACKEND_API_BASE_URL}{path}"


# --- Datei Upload ans Backend ---
async def upload_file(file_path: Path, display_name: str) -> dict[str, Any]:
    """Sendet die Datei an den /upload Endpunkt deines FastApi Backends."""
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        with file_path.open("rb") as handle:
            files = {"file": (display_name, handle, "application/octet-stream")}
            response = await client.post(backend_url("/upload"), files=files)
        response.raise_for_status()
        return response.json()


async def process_attachments(message: cl.Message) -> list[str]:
    """Verarbeitet alle vom User im Chat angehängten Dateien."""
    results: list[str] = []

    for element in (message.elements or []):
        file_path_value = getattr(element, "path", None)
        file_name = getattr(element, "name", None)

        if not file_path_value:
            continue

        file_path = Path(file_path_value)
        display_name = file_name or file_path.name

        try:
            # Sende an Backend
            result = await upload_file(file_path, display_name)
            # Backend antwortet meist mit der Anzahl der verarbeiteten Chunks
            chunks = result.get("chunks", 0) 
            results.append(f"✅ `{display_name}`: Erfolgreich verarbeitet ({chunks} Text-Abschnitte).")
        except httpx.HTTPStatusError as exc:
            results.append(
                f"❌ `{display_name}`: Upload fehlgeschlagen ({exc.response.status_code})"
            )
        except Exception as exc:
            results.append(f"❌ `{display_name}`: Upload fehlgeschlagen ({exc})")

    return results


# --- Chat mit dem Backend ---
async def stream_chat(prompt: str) -> str:
    """Sendet die Frage an den /chat Endpunkt und streamt die Antwort."""
    content_parts: list[str] = []
    chat_profile = cl.user_session.get("chat_profile")
    assistant = cl.Message(content="", author="Chatbot")
    await assistant.send()

    try:
        async with httpx.AsyncClient(timeout=STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                backend_url("/chat"),
                json={
                    "message": prompt,
                    "profile" : chat_profile
                },
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if not chunk:
                        continue
                    content_parts.append(chunk)
                    await assistant.stream_token(chunk)
    except httpx.HTTPStatusError as exc:
        error_text = f"Backend-Fehler beim Chat ({exc.response.status_code}): {exc.response.text[:200]}"
        assistant.content = error_text
        await assistant.update()
        return error_text
    except Exception as exc:
        error_text = f"Chat fehlgeschlagen: {exc}"
        assistant.content = error_text
        await assistant.update()
        return error_text

    final_content = "".join(content_parts)
    
    
    return final_content




@cl.set_chat_profiles
async def chat_profiles():
    return [
        cl.ChatProfile(
            name="RAG-Suche",
            markdown_description="Durchsucht die Dokumente im K-Laufwerk",
        ),
        cl.ChatProfile(
            name="Summary-Agent",
            markdown_description="Fasst den text zusammen",
        ),
        cl.ChatProfile(
            name="Web-Search Agent",
            markdown_description="Agent zum Suchen im Internet",
        ),
    ]

# --- LDAP Authentifizierung ---
@cl.password_auth_callback
async def auth(username: str, password: str) -> cl.User | None:
    try:
        server = Server(LDAP_SERVER_URL, get_info=ALL)
        user_dn = f"{username}@bwi.local"
        conn = Connection(server, user=user_dn, password=password, authentication='SIMPLE')
        if conn.bind():
            return cl.User(identifier=username, metadata={"role": "user", "source": "ldap"})
        return None
    except Exception as e:
        print(f"LDAP Fehler: {e}")
    # Fallback für lokales Testen
    return cl.User(identifier=username, metadata={"role": "user", "source": "ldap"})
        

# --- Chainlit Event Handler ---
@cl.on_chat_start
async def on_chat_start() -> None:
    user = cl.user_session.get("user")
    chat_profile = cl.user_session.get("chat_profile")
    
    
    await cl.Message(
        content=f"Der Chat für {user} wird mit dem Agenten: {chat_profile} gestartet"
    ).send()

@cl.on_chat_resume
async def on_chat_resume(thread):
    pass

@cl.on_message
async def on_message(message: cl.Message) -> None:
    # 1. Hat der Nutzer Dateien angehängt? -> Ans Backend schicken!
    attachment_results = await process_attachments(message)
    if attachment_results:
        await cl.Message(
            content="Datei-Upload Status:\n" + "\n".join(attachment_results),
            author="Chatbot"
        ).send()

    # 2. Hat der Nutzer Text geschrieben?
    user_text = (message.content or "").strip()

    if not user_text and not attachment_results:
        await cl.Message(content="Bitte gib eine Nachricht ein oder lade eine Datei hoch.", author="Chatbot").send()
        return
        
    if not user_text:
        # Wenn nur Dateien hochgeladen wurden, müssen wir keinen Chat auslösen
        return

    # 3. Chat-Logik (Frage ans Backend schicken)
    filenames = [e.name for e in message.elements] if message.elements else []
    if filenames:
        prompt_with_context = f"Hinweis: Der Nutzer hat gerade folgende Dateien hochgeladen: {', '.join(filenames)}. \n\nFrage: {user_text}"
    else:
        prompt_with_context = user_text

    await stream_chat(prompt_with_context)