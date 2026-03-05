import os

# Support both OLLAMA_BASE_URL (preferred) and legacy OLLAMA_API
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL") or os.getenv(
    "OLLAMA_API", "http://localhost:11434"
)
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "llama3.2")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://raguser:ragpass@postgres:5432/ragdb"
)

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
MIN_SIMILARITY: float = float(os.getenv("MIN_SIMILARITY", "0.3"))

COLLECTION_NAME = "documents"
_CONTEXT_SEPARATOR = "\n\n---\n\n"
