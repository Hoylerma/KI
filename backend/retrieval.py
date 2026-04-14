from typing import List
import logging
import torch

from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from database import get_vector_store
from config import MAX_CONTEXT_CHARS, MIN_SIMILARITY, RAG_TOP_K, _CONTEXT_SEPARATOR

logger = logging.getLogger("bwiki.retrieval")

_bm25_retriever = None
_reranker_retriever = None

async def init_bm25_retriever(vector_store):
    global _bm25_retriever
    logger.info("⚙️ Baue BM25 Keyword-Index auf (CPU)...")
    try:
        alle_docs = await vector_store.asimilarity_search("", k=10000) 
        if alle_docs:
            _bm25_retriever = BM25Retriever.from_documents(alle_docs)
            
            _bm25_retriever.k = 10 
            logger.info(f"✅ BM25 Index mit {len(alle_docs)} Chunks erstellt!")
        else:
            logger.warning("Keine Dokumente in der DB gefunden.")
    except Exception as e:
        logger.error(f"Fehler beim BM25 Aufbau: {e}")

def get_base_ensemble_retriever():
    """Erstellt das Basis-Ensemble aus Vektor und BM25."""
    global _bm25_retriever
    vs = get_vector_store()
    
    # Vektor-Suche ebenfalls mit höherem k für den Reranker
    vector_retriever = vs.as_retriever(search_kwargs={"k": 10})
    
    if _bm25_retriever is None:
        return vector_retriever

    return EnsembleRetriever(
        retrievers=[_bm25_retriever, vector_retriever],
        weights=[0.5, 0.5] 
    )

def get_reranker_retriever():
    global _reranker_retriever
    if _reranker_retriever is not None:
        return _reranker_retriever

    model = HuggingFaceCrossEncoder(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        model_kwargs={"device": "cpu"}
    )
    
    
    compressor = CrossEncoderReranker(model=model, top_n=3)
    
    base_ensemble = get_base_ensemble_retriever() 
    
    _reranker_retriever = ContextualCompressionRetriever(
        base_compressor=compressor, 
        base_retriever=base_ensemble
    )
    return _reranker_retriever

async def rag_search_async(query: str) -> str:
    global _bm25_retriever
    vs = get_vector_store() 
    
    # Sicherstellen, dass BM25 initialisiert ist
    if _bm25_retriever is None:
        await init_bm25_retriever(vs)
    
    # Jetzt nutzen wir den Reranker-Pfad
    retriever = get_reranker_retriever()
    
    try:
        logger.info(f"🔍 RAG-Suche mit Reranking für: {query}")
        beste_dokumente = await retriever.ainvoke(query)
        
        if not beste_dokumente:
            logger.warning("⚠️ Reranker hat alle Dokumente als irrelevant verworfen.")
            return ""

        kontext_bloecke = []
        # HIER STARTET METHODE 1: Wir nutzen enumerate, um den Platz (1, 2, 3) mitzuzählen
        for i, doc in enumerate(beste_dokumente):
            quelle = doc.metadata.get("filename", doc.metadata.get("source", "Unbekannt"))
            
            # Wir holen uns den Relevanz-Score, den der Reranker berechnet hat
            score = doc.metadata.get("relevance_score", "Kein Score")
            
            # Ausgabe im Docker-Log für dich zum Überprüfen
            logger.info(f"🏆 Platz {i+1} | Score: {score} | Datei: {quelle}")
            
            block = f"--- QUELLE: {quelle} ---\n{doc.page_content}"
            kontext_bloecke.append(block)
            
        return "\n\n".join(kontext_bloecke)
        
    except Exception as e:
         logger.error(f"Reranking-Suche fehlgeschlagen: {e}")
         return ""