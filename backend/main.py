from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel
import os

app = FastAPI()


origins = [
    "http://localhost",         
    "http://127.0.0.1",       
    "http://localhost:5173",   
    "http://127.0.0.1:5173",
    "http://localhost:80",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      
    allow_credentials=True,
    allow_methods=["*"],         
    allow_headers=["*"],         
)

class ChatMessage(BaseModel):
    message: str

OLLAMA_API = os.getenv("OLLAMA_API", "http://localhost:11434")

@app.get("/")
async def root():
    return {"status": "Backend läuft", "engine": "Ollama ready"}

@app.post("/chat")
async def chat(data: ChatMessage):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_API}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": data.message,
                    "stream": False
                },
                timeout=60.0
            )
            result = response.json()
            
            if "error" in result:
                return {"error": f"Ollama Fehler: {result['error']}"}
            
            return {"response": result.get("response", "Keine Antwort")}
    except Exception as e:
        return {"error": f"Fehler beim Verbinden mit Ollama: {str(e)}"}
