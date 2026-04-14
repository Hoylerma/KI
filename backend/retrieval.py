from json import tool
from typing import List
import logging

from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

from database import get_vector_store
from config import MAX_CONTEXT_CHARS, MIN_SIMILARITY, RAG_TOP_K, _CONTEXT_SEPARATOR

logger = logging.getLogger("bwiki.retrieval")

_bm25_retriever = None

def init_bm25_retriever(vector_store):
    global _bm25_retriever
    logger.info("⚙️ Baue BM25 Keyword-Index auf (CPU)...")
    
    alle_docs = vector_store.similarity_search("", k=10000) 
    
    if alle_docs:
        _bm25_retriever = BM25Retriever.from_documents(alle_docs)
        _bm25_retriever.k = 3 
        logger.info(f"✅ BM25 Index mit {len(alle_docs)} Chunks erstellt!")
    else:
        logger.warning("Keine Dokumente in der DB gefunden.")

async def rag_search_async(query: str) -> str:
    global _bm25_retriever
    vs = get_vector_store() 
    
    vector_retriever = vs.as_retriever(search_kwargs={"k": 3})
    
    if _bm25_retriever is None:
        init_bm25_retriever(vs)
        
    if _bm25_retriever is None:
         docs = await vector_retriever.ainvoke(query)
         return "\n\n".join([doc.page_content for doc in docs])

    ensemble_retriever = EnsembleRetriever(
        retrievers=[_bm25_retriever, vector_retriever],
        weights=[0.5, 0.5] 
    )
    
    beste_dokumente = await ensemble_retriever.ainvoke(query)
    return "\n\n".join([doc.page_content for doc in beste_dokumente])
