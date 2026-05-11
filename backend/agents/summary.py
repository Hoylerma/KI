# agents/summary.py
from fastapi import Request
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from config import CHAT_MODEL, OLLAMA_BASE_URL
from database import get_vector_store # Importiere deine Vector-DB Logik

async def summary_agent(prompt_text: str, request: Request, session_id: str = None, history: str = ""):
    """Baut eine Chain für Zusammenfassungen und streamt die Antwort unter Berücksichtigung der Historie."""
    
    context = ""
    # Wenn der Nutzer ein Dokument hochgeladen hat (session_id existiert)
    if session_id:
        try:
            # Verbinde dich mit der temporären Datenbank des Uploads
            vs = get_vector_store(collection_name=session_id)
            # Hole die relevantesten Abschnitte des Dokuments (z.B. k=10 Abschnitte)
            docs = await vs.asimilarity_search(prompt_text, k=10)
            # Die Treffer werden als Lauftext kombiniert und in den Systemprompt eingefuegt.
            context = "\n\n".join([doc.page_content for doc in docs])
        except Exception as e:
            print(f"Fehler beim Abrufen des Dokuments: {e}")
            context = "Fehler: Konnte das hochgeladene Dokument nicht lesen."

    llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL)
    
    # Der Prompt enthält jetzt Variablen für {context} und {history}!
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "Du bist ein Experte für das Zusammenfassen von Texten. "
                   "Nutze den folgenden Dokumenten-Kontext, um die Frage des Nutzers zu beantworten. "
                   "Berücksichtige auch den bisherigen Chat-Verlauf, falls die Frage sich darauf bezieht.\n\n"
                   "[Bisheriger Verlauf]\n{history}\n\n"
                   "[Dokumenten-Kontext]\n{context}\n\n"
                   "Fasse die Informationen prägnant zusammen. Antworte IMMER auf Deutsch."),
        ("human", "{question}"),
    ])
    
    chain = prompt_template | llm | StrOutputParser()
    
    # Frage, Dokument-Kontext UND Historie werden gemeinsam in die Chain gestreamt.
    async for chunk in chain.astream({"question": prompt_text, "context": context, "history": history}):
        # Bricht den Stream ab, falls der Nutzer die Seite neu lädt oder schließt
        if await request.is_disconnected():
            break
        yield chunk