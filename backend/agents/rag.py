import os

from langchain_postgres.vectorstores import PGVector
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from retrieval import rag_search_async
import logging
from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT
import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG")


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