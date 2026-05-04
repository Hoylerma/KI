from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama
from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT

def summary_agent():
    """Baut eine Chain, die strikt auf Zusammenfassungen getrimmt ist."""
    
    llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Du bist ein Experte für das Zusammenfassen von Texten. "
                   "Fasse den folgenden Text in 3-5 prägnanten Stichpunkten zusammen. "
                   "Antworte IMMER auf Deutsch."),
        ("human", "{question}"),
    ])
    
    # Eine einfache LCEL (LangChain Expression Language) Chain
    chain = prompt | llm | StrOutputParser()
    
    return chain