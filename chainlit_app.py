import os
import re
from pathlib import Path
from typing import Any
import uuid

from ldap3 import ALL, Connection, Server
import chainlit as cl
import httpx

# --- Konfiguration ---
# REQUEST_TIMEOUT: normale API-Aufrufe
# STREAM_TIMEOUT: Streaming-Requests ohne Gesamt-Timeout
REQUEST_TIMEOUT = httpx.Timeout(None, connect=None)
STREAM_TIMEOUT = httpx.Timeout(None, connect=None)
BACKEND_URL = os.getenv("BACKEND_API_BASE_URL", "http:127.0.0.1//:8000",).rstrip("/")
LDAP_SERVER_URL = os.getenv("LDAP_SERVER_URL", "ldap://12353-DC01.bwi.local")

def backend_url(path: str) -> str:
    """Hilfsfunktion fuer sauberes URL-Building zu Backend-Routen."""
    return f"{BACKEND_URL}{path}"

# --- Chat mit dem Backend ---
async def stream_chat(prompt: str) -> str:
    """Sendet die Frage an den /chat Endpunkt und streamt die Antwort."""
    content_parts: list[str] = []
    
    # Session-Daten aus Chainlit laden (Profil + optionale Upload-Collection-ID).
    chat_profile = cl.user_session.get("chat_profile")
    backend_session_id = cl.user_session.get("backend_session_id") # <-- NEU
    
    assistant = cl.Message(content="", author="Chatbot")
    await assistant.send()

    try:
        async with httpx.AsyncClient(timeout=STREAM_TIMEOUT) as client:
            async with client.stream(
                "POST",
                backend_url("/chat"),
                json={
                    "message": prompt,
                    "profile" : chat_profile,
                    "session_id": backend_session_id 
                },
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_text():
                    if not chunk:
                        continue
                    content_parts.append(chunk)
                    await assistant.stream_token(chunk)
    except httpx.HTTPStatusError as exc:
        await exc.response.aread()
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
        cl.ChatProfile(name="RAG-Suche", markdown_description="Durchsucht die Dokumente"),
        cl.ChatProfile(name="Allgemein", markdown_description="Für allgemeine Anfragen"),
        cl.ChatProfile(name="Web-Search Agent", markdown_description="Agent zum Suchen im Internet"),
    ]

# --- LDAP Authentifizierung ---
@cl.password_auth_callback
async def auth(username: str, password: str) -> cl.User | None:
    """Authentifiziert Nutzer gegen LDAP und erstellt einen Chainlit-User."""
    try:
        server = Server(LDAP_SERVER_URL, get_info=ALL)
        user_dn = f"{username}@bwi.local"
        conn = Connection(server, user=user_dn, password=password, authentication='SIMPLE')
        if conn.bind():
            return cl.User(identifier=username, metadata={"role": "user", "source": "ldap"})
        return None
    except Exception as e:
        print(f"LDAP Fehler: {e}")
    return cl.User(identifier=username, metadata={"role": "user", "source": "ldap"})

@cl.on_chat_start
@cl.on_chat_start
async def on_chat_start() -> None:
    chat_profile = cl.user_session.get("chat_profile")
    user = cl.user_session.get("user")
    
    # Sicherer Fallback für den Usernamen
    username = user.identifier if user else "anonym"
    cl.user_session.set("username", username)
    
    history_loaded = False
    
    # Logge im Terminal, wer sich anmeldet
    print(f"\n--- Starte Chat für User: {username} ---")

    # 1. Prüfen, ob das Backend alte Nachrichten für diesen User hat
    try:
        async with httpx.AsyncClient() as client:
            url = backend_url(f"/history/{username}")
            print(f"Frage Historie ab: {url}")
            
            resp = await client.get(url)
            
            if resp.status_code == 200:
                data = resp.json()
                backend_session_id = data.get("session_id")
                messages = data.get("messages", [])
                
                print(f"✅ Gefundene Session: {backend_session_id}")
                print(f"✅ Anzahl geladener Nachrichten: {len(messages)}")

                # Wenn wir eine alte Session gefunden haben, stellen wir sie wieder her!
                if backend_session_id and messages:
                    cl.user_session.set("backend_session_id", backend_session_id)
                    history_loaded = True
                    
                    # Nachrichten-Blasen generieren
                    for msg in messages:
                        # HIER WAR DER FEHLER: Wir nutzen jetzt 'username' statt 'user.identifier'
                        author = "Chatbot" if msg["role"] == "assistant" else username
                        
                        # Nur Blasen anzeigen, die auch wirklich Text enthalten
                        if msg["content"].strip():
                            await cl.Message(content=msg["content"], author=author).send()
            else:
                print(f"⚠️ Backend antwortet mit Status: {resp.status_code}")
                
    except Exception as e:
        print(f"❌ FEHLER beim Laden der Historie: {e}")

    # 2. Wenn es ein GANZ NEUER Chat ist (keine Historie gefunden)
    if not history_loaded:
        print("Starte eine komplett neue Session.")
        cl.user_session.set("backend_session_id", str(uuid.uuid4()))
        await cl.Message(
            content=f"Willkommen! Der Chat wurde im Modus **{chat_profile}** gestartet.\n"
                    "Du kannst mir direkt eine Frage stellen oder über die Büroklammer (unten links) ein Dokument hochladen.",
            author="Chatbot"
        ).send()

@cl.on_chat_resume
async def on_chat_resume(thread):
    pass    

@cl.on_message
async def on_message(message: cl.Message) -> None:
    # Aktuelles Profil abfragen
    chat_profile = cl.user_session.get("chat_profile")
    
    # 1. Prüfen, ob Dateien angehängt wurden
    if message.elements:
        
        # --- NEUE TÜRSTEHER-LOGIK ---
        if chat_profile != "Summary-Agent":
            await cl.Message(
                content=f"❌ **Upload nicht erlaubt:** Du bist aktuell im Modus `{chat_profile}`. "
                        "Das Hochladen von eigenen Dokumenten ist **nur im Modus 'Summary-Agent'** möglich.\n\n"
                        "*Bitte starte einen neuen Chat (Neu-Laden) und wähle das Profil 'Summary-Agent', um diese Datei zu verarbeiten.*"
            ).send()
            return  # Bricht die Funktion hier ab! Die Datei geht NICHT ans Backend.
        # ----------------------------

        for element in message.elements:
            file_path = Path(getattr(element, "path", ""))
            
            if not file_path.exists():
                continue
                
            display_name = getattr(element, "name", file_path.name)
            
            msg = cl.Message(content=f"`{display_name}` wird an das Backend gesendet...")
            await msg.send()
            
            try:
                # Sende Upload ans Backend
                async with httpx.AsyncClient(timeout=None) as client: 
                    with file_path.open("rb") as f:
                        mime_type = "application/pdf" if display_name.lower().endswith(".pdf") else "text/plain"
                        files_payload = {"file": (display_name, f, mime_type)}
                        response = await client.post(f"{BACKEND_URL}/upload", files=files_payload)
                        
                if response.status_code == 200:
                    data = response.json()
                    
                    if "session_id" in data:
                        cl.user_session.set("backend_session_id", data["session_id"])
                        
                    msg.content = f"✅ `{display_name}` erfolgreich verarbeitet! Du kannst jetzt Fragen dazu stellen."
                    await msg.update()
                else:
                    msg.content = f"❌ Fehler beim Upload von `{display_name}` (Status: {response.status_code})."
                    await msg.update()
            except Exception as e:
                msg.content = f"❌ Backend-Verbindungsfehler beim Upload: {e}"
                await msg.update()

    # 2. Textnachricht verarbeiten und an den Chat-Stream weiterreichen.
    user_text = (message.content or "").strip()
    
    if not user_text:
        return

    await stream_chat(user_text)