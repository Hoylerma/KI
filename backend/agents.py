import logging
from typing import Literal, TypedDict, Annotated
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver 


from config import CHAT_MODEL, OLLAMA_BASE_URL, SYSTEM_PROMPT
from retrieval import rag_search_async

logger = logging.getLogger("bwiki.agent")

# 1. Der State (Das Gedächtnis)
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    destination: str 

class RouterDecision(TypedDict):
    route: Literal["rag_agent"]


llm = ChatOllama(model=CHAT_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)

# 3. Die Agenten-Knoten (Nodes)
async def orchestrator_node(state: AgentState):
    prompt = """Du bist der Chef-Orchestrator eines Firmen-Wikis. 
    Lies die Nachricht des Nutzers und entscheide strikt:
    - Fachliche Frage (Projekte, Handbuch, Firma, Tools, Anleitungen) -> 'rag_agent'"""
   
    router_llm = llm.with_structured_output(RouterDecision)
    decision = await router_llm.ainvoke([SystemMessage(content=prompt)] + state["messages"])
    
    return {"destination": decision["route"]}

async def rag_agent_node(state: AgentState):
    logger.info("📚 RAG-Agent durchsucht die Datenbank...")
    letzte_frage = state["messages"][-1].content
    
    # 1. RAG-Suche ausführen
    rag_context = await rag_search_async(letzte_frage)
    
    # 2. Die System-Regeln (NUR Anweisungen und Kontext)
    prompt_text = f"""{SYSTEM_PROMPT}

    Hier sind die bereitgestellten Dokumente:
    <kontext>
    {rag_context}
    </kontext>

    Erinnerung an deine oberste Regel: Beantworte die folgende Frage AUSSCHLIESSLICH basierend auf dem Text innerhalb der <kontext> Tags! 
    Frage des Nutzers: {letzte_frage}
    """
    
    
    nachrichten_fuer_llm = [
        SystemMessage(content=prompt_text),
        HumanMessage(content=letzte_frage)] + state["messages"][:-1] 
    
    # 4. LLM antworten lassen
    antwort = await llm.ainvoke(nachrichten_fuer_llm)
    
    return {"messages": [antwort]}



def route_decision(state: AgentState):
    return state["destination"]

# 4. Den Graphen zusammenbauen
workflow = StateGraph(AgentState)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("rag_agent", rag_agent_node)


workflow.set_entry_point("orchestrator")
workflow.add_conditional_edges("orchestrator", route_decision, {
    "rag_agent": "rag_agent",
    
})
workflow.add_edge("rag_agent", END)


# Gedächtnis einschalten
memory = MemorySaver() 
agent_app = workflow.compile(checkpointer=memory)

# 5. Die Schnittstelle für deine main.py
async def run_agent(session_id: str, user_message: str) -> str:
    config = {"configurable": {"thread_id": session_id}}
    inputs = {"messages": [HumanMessage(content=user_message)]}
    result = await agent_app.ainvoke(inputs, config=config)
    return result["messages"][-1].content