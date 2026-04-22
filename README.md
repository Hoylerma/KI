# BW-i KI - Chainlit + FastAPI + RAG

Dieses Projekt nutzt jetzt Chainlit als vollstaendige Benutzeroberflaeche.
Das bisherige React/Vite Frontend ist nicht mehr Teil des Laufzeit-Stacks.

## Architektur

```
Chainlit (chainlit_app.py)
       |
       | HTTP
       v
FastAPI Backend (backend/main.py)
  - /upload
  - /documents
  - /documents/{filename}
  - /chat (streaming)

FastAPI verwendet:
  - LangChain + PGVector (Postgres/pgvector)
  - Ollama fuer Chat und Embeddings
```

## Schnellstart (Docker)

1. Umgebungsvariablen in .env setzen oder pruefen.
2. Stack starten:

```bash
docker compose up --build
```

3. UI im Browser oeffnen:

```text
http://localhost:8001
```

## Wichtige Umgebungsvariablen

| Variable | Default | Beschreibung |
|---|---|---|
| POSTGRES_USER | - | Postgres Benutzer |
| POSTGRES_PASSWORD | - | Postgres Passwort |
| POSTGRES_DB | - | Postgres Datenbank |
| OLLAMA_BASE_URL | http://host.docker.internal:11434 | Ollama URL |
| EMBEDDING_MODEL | nomic-embed-text | Embedding Modell |
| CHAT_MODEL | llama3.1 | Chat Modell |
| BACKEND_PORT | 8000 | Externer FastAPI Port |
| CHAINLIT_PORT | 8001 | Externer Chainlit Port |
| BACKEND_API_BASE_URL | http://backend:8000 | Backend-URL aus Sicht von Chainlit |

## Chainlit Bedienung

- Dateien koennen direkt am Prompt angehaengt werden.
- /docs listet ingestierte Dokumente.
- /delete <dateiname> loescht ein Dokument.

## API Endpunkte (Backend)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | / | Healthcheck |
| POST | /upload | Dokument ingestieren |
| GET | /documents | Dokumentliste |
| DELETE | /documents/{filename} | Dokument entfernen |
| POST | /chat | Streaming Chatantwort |

## Lokale Entwicklung ohne Docker

Abhaengigkeiten installieren:

```bash
pip install -r backend/requirements.txt
pip install -r requirements-chainlit.txt
```

Backend starten:

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Chainlit starten:

```bash
chainlit run chainlit_app.py -w
```
