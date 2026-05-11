import os
import logging
import time
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from langchain_postgres.vectorstores import PGVector
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from retrieval import rag_search_async
from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG")


async def contextualize_query(prompt: str, history: str) -> str:
    """Schreibt Nachfragen mithilfe der Historie in eigenständige Suchanfragen um."""
    if not history.strip():
        return prompt # Keine Historie? Dann bleibt die Frage wie sie ist.

    # Temperatur auf 0 setzen, damit das LLM hier sehr faktisch und nicht kreativ ist
    llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.0)
    
    rewrite_prompt = f"""
    Analysiere den folgenden Chat-Verlauf und die NEUE Frage des Nutzers.
    
    DEINE REGELN:
    1. THEMENWECHSEL ERKENNEN: Wenn die neue Frage ein komplett neues Thema anspricht und auch OHNE den Verlauf verständlich ist, musst du exakt die neue Frage zurückgeben. Verknüpfe sie NICHT mit dem alten Thema!
    2. NACHFRAGEN UMSCHREIBEN: Wenn die neue Frage unvollständig ist und sich offensichtlich auf das vorherige Thema bezieht (z.B. weil sie Wörter wie "er", "sie", "es", "dafür", "den Link", oder ähnliche enthält), formuliere sie in eine eigenständige Suchanfrage um.
    
    WICHTIG: Antworte AUSSCHLIESSLICH mit der finalen (umgeschriebenen oder originalen) Frage. Keine Begrüßung, keine Erklärungen, keine Anführungszeichen.

    Verlauf:
    {history}

    Neue Frage: {prompt}

    Umgeschriebene Frage:
    """
    
    response = await llm.ainvoke(rewrite_prompt)
    rewritten_query = response.content.strip()
    return rewritten_query

async def stream_response(prompt: str, request: Request, history: str = ""):
    """Baut den RAG-Prompt und streamt tokenweise die Modellantwort."""
    
    # 1. NEU: Frage umschreiben lassen (Query Rewriting)
    standalone_query = await contextualize_query(prompt, history)
    
    logger.info("=" * 60)
    logger.info(f"🗣️ ORIGINALE FRAGE: {prompt}")
    if standalone_query != prompt:
        logger.info(f"🔄 UMGESCHRIEBENE SUCHE: {standalone_query}")
    
    # 2. RAG-Kontext holen (Wir suchen jetzt mit der UMGESCHRIEBENEN Frage!)
    try:
        rag_context = await rag_search_async(standalone_query)
    except Exception as e:
        logger.warning(f"RAG-Kontext fehlgeschlagen: {e}")
        rag_context = ""

    # ── Kontext loggen ──────────────────────────────────────
    if rag_context:
        logger.info(f"📚 RAG-KONTEXT ({len(rag_context)} Zeichen):")
        logger.info(rag_context[:500] + ("..." if len(rag_context) > 500 else ""))
    else:
        logger.info("📚 RAG-KONTEXT: Keiner gefunden")
    logger.info("=" * 60)

    system_content = SYSTEM_PROMPT

    if rag_context:
        user_content = f"""Du bist ein hilfreicher Assistent der BWI.
        Nutze den folgenden Kontext, um die Frage zu beantworten.
        Berücksichtige auch den bisherigen Chat-Verlauf, falls die Frage sich darauf bezieht.
    
        [Bisheriger Verlauf]
        {history}
    
        [Gefundener Kontext]
        {rag_context}
        
        Frage: {prompt}
        """
    else:
        if history:
            user_content = f"""Berücksichtige den bisherigen Chat-Verlauf, falls die Frage sich darauf bezieht.
            
        [Bisheriger Verlauf]
        {history}
        
        Frage: {prompt}
        """
        else:
            user_content = prompt

    # ChatOllama liefert einen asynchronen Token-Stream.
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