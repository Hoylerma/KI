from typing import List

from database import get_vector_store
from config import MAX_CONTEXT_CHARS, MIN_SIMILARITY, RAG_TOP_K, _CONTEXT_SEPARATOR


async def rag_search_async(query: str, top_k: int = RAG_TOP_K) -> str:
    """
    Search the vector store and return a formatted context string with sources.
    Returns an empty string if nothing relevant is found.
    """
    vs = get_vector_store()
    results = await vs.asimilarity_search_with_relevance_scores(query, k=top_k)

    context_parts: List[str] = []
    total_len = 0
    for doc, score in results:
        if score < MIN_SIMILARITY:
            continue
        filename = doc.metadata.get("filename") or doc.metadata.get(
            "source", "Unbekannt"
        )
        part = f"[Quelle: {filename} | Relevanz: {score:.2f}]\n{doc.page_content}"
        if total_len + len(part) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_len
            if remaining > 100:
                context_parts.append(part[:remaining] + "...")
            break
        context_parts.append(part)
        total_len += len(part) + len(_CONTEXT_SEPARATOR)

    return _CONTEXT_SEPARATOR.join(context_parts)
