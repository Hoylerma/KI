import os
from pathlib import Path
from typing import Any
from urllib.parse import quote
from ldap3 import Server, Connection, ALL

import chainlit as cl
import httpx

BACKEND_API_BASE_URL = os.getenv("BACKEND_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
STREAM_TIMEOUT = httpx.Timeout(None, connect=10.0)



LDAP_SERVER_URL = 'ldap://12353-DC01.bwi.local'




def backend_url(path: str) -> str:
    return f"{BACKEND_API_BASE_URL}{path}"


async def get_backend_status() -> str:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(backend_url("/"))
            response.raise_for_status()
            payload = response.json()
        return payload.get("status", "Verbunden")
    except Exception:
        return "Backend nicht erreichbar"


async def list_documents() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.get(backend_url("/documents"))
        response.raise_for_status()
        payload = response.json()

    docs = payload.get("documents", [])
    return docs if isinstance(docs, list) else []


async def delete_document(filename: str) -> None:
    encoded = quote(filename, safe="")
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.delete(backend_url(f"/documents/{encoded}"))
        response.raise_for_status()


async def upload_file(file_path: Path, display_name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        with file_path.open("rb") as handle:
            files = {"file": (display_name, handle, "application/octet-stream")}
            response = await client.post(backend_url("/upload"), files=files)
        response.raise_for_status()
        return response.json()


async def upload_attachments(message: cl.Message) -> list[str]:
    results: list[str] = []

    for element in (message.elements or []):
        file_path_value = getattr(element, "path", None)
        file_name = getattr(element, "name", None)

        if not file_path_value:
            continue

        file_path = Path(file_path_value)
        display_name = file_name or file_path.name

        try:
            result = await upload_file(file_path, display_name)
            chunks = result.get("chunks", 0)
            results.append(f"- {display_name}: {chunks} Chunks verarbeitet")
        except httpx.HTTPStatusError as exc:
            results.append(
                f"- {display_name}: Upload fehlgeschlagen ({exc.response.status_code})"
            )
        except Exception as exc:
            results.append(f"- {display_name}: Upload fehlgeschlagen ({exc})")

    return results


async def stream_chat(prompt: str, filenames: list[str] = None, source_elements: list = None, user_id: str = None) -> str:
    content_parts: list[str] = []
    assistant = cl.Message(content="", elements=source_elements or [])
    await assistant.send()

    try:
        async with httpx.AsyncClient(timeout=STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                backend_url("/chat"),
                # Wir schicken die Dateinamen jetzt ans Backend mit!
                json={
                    "message": prompt,
                    "active_files": filenames or [] 
                },
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if not chunk:
                        continue
                    content_parts.append(chunk)
                    await assistant.stream_token(chunk)
    except httpx.HTTPStatusError as exc:
        error_text = (
            f"Backend-Fehler beim Chat ({exc.response.status_code}): "
            f"{exc.response.text[:200]}"
        )
        assistant.content = error_text
        await assistant.update()
        return error_text
    except Exception as exc:
        error_text = f"Chat fehlgeschlagen: {exc}"
        assistant.content = error_text
        await assistant.update()
        return error_text

    final_content = "".join(content_parts)
    assistant.content = final_content
    await assistant.update()
    return final_content



@cl.password_auth_callback
async def auth(username: str, password: str) -> bool:
    try:
        server = Server(LDAP_SERVER_URL, get_info=ALL)
        
        user_dn = f"{username}@bwi.local" 
        conn = Connection(server, user=user_dn, password=password, authentication='SIMPLE')
        
        if conn.bind():
           
            return cl.User(identifier=username, metadata={"role": "user", "source": "ldap"})
        else:
            return None
    except Exception as e:
        print(f"LDAP Fehler: {e}")
        return None

@cl.on_chat_start
async def on_chat_start() -> None:
    status = await get_backend_status()
    await cl.Message(
        content=(
            "BW-i KI Chatbot gestartet\n"           
            "Hinweise:\n"
            "- Dateien koennen direkt am Prompt angehaengt werden.\n"
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user = cl.user_session.get("user")
    user_id = user.identifier if user else "anonymous"

    # 1. Zuerst den Lade-Indikator setzen (Großes 'M' beachten!)
    await cl.Message(content="Ich denke nach...").send()
    
    source_elements = []
    
    
    attachment_results = await upload_attachments(message)
    if attachment_results:
        await cl.Message(content="Datei-Upload erfolgreich:\n" + "\n".join(attachment_results)).send()
        
    user_text = (message.content or "").strip()
    
    
    uploaded_filenames = [e.name for e in message.elements] if message.elements else []

   
    await stream_chat(prompt=user_text, filenames=uploaded_filenames, source_elements=source_elements, user_id=user_id)
