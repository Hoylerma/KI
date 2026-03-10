import os

from anyio import Path

# Support both OLLAMA_BASE_URL (preferred) and legacy OLLAMA_API
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL") or os.getenv(
    "OLLAMA_API", "http://localhost:11434"
)
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "llama3.1")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://raguser:ragpass@postgres:5432/ragdb"
)

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "2000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "400"))
MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "4000"))
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "15"))
MIN_SIMILARITY: float = float(os.getenv("MIN_SIMILARITY", "0.5"))

COLLECTION_NAME = "documents"
_CONTEXT_SEPARATOR = "\n\n---\n\n"

PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    """Lädt einen Prompt aus dem prompts/ Ordner."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# Beim Import einmal laden
SYSTEM_PROMPT = load_prompt("system")
