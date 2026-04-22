import logging
from typing import List

from database import get_vector_store
from config import RAG_TOP_K

logger = logging.getLogger("bwiki.retrieval")

async def rag_search_async(query: str) -> str:
    """Führt eine asynchrone RAG-Suche durch und gibt die gefundenen Dokumente als Text zurück.
    """
    vs = get_vector_store()
    
    try:
        logger.info(f"🔍 Reine Vektor-Suche gestartet für: {query}")
        
        # Direkte Abfrage der Vektor-Datenbank
        # RAG_TOP_K definiert, wie viele Chunks wir zurückerhalten (meist 3-5)
        docs = await vs.asimilarity_search(query, k=RAG_TOP_K)
        
        if not docs:
            logger.warning("⚠️ Keine Dokumente in der Vektor-DB gefunden.")
            return ""

        kontext_bloecke = []
        for doc in docs:
            # Metadaten auslesen
            quelle = doc.metadata.get("filename", doc.metadata.get("source", "Unbekannt"))
            
            # Block für das LLM formatieren
            block = f"--- QUELLE: {quelle} ---\n{doc.page_content}"
            kontext_bloecke.append(block)
            
            logger.info(f"📄 Gefunden: {quelle}")
            
        return "\n\n".join(kontext_bloecke)
        
    except Exception as e:
         logger.error(f"Vektor-Suche fehlgeschlagen: {e}")
         return ""