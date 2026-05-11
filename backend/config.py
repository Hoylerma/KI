import os

from anyio import Path

# Zentrale Laufzeit-Konfiguration: Alle Werte sind per ENV ueberschreibbar.
# Support both OLLAMA_BASE_URL (preferred) and legacy OLLAMA_API
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL") or os.getenv(
    "OLLAMA_API", "http://localhost:11434"
)
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
CHAT_MODEL: str = os.getenv("CHAT_MODEL", "qwen3:8b")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://raguser:ragpass@postgres:5432/ragdb"
)

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))

COLLECTION_NAME = "documents"

# Prompt-Dateien liegen unter backend/prompts/.
PROMPTS_DIR = Path(__file__).parent / "prompts"

def load_prompt(name: str) -> str:
    """Lädt einen Prompt aus dem prompts/ Ordner."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Prompt nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


# Beim Import einmal laden, damit der Prompt spaeter nicht pro Request gelesen wird.
SYSTEM_PROMPT = load_prompt("system")
