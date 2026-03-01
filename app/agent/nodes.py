from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from app.agent.state import AgentState
from app.agent.executor import handle_tool_call
from app.config.settings import settings
from app.tools.stock_tool import TOOLS
import json

from langchain_groq import ChatGroq

_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.LLM_MODEL,
    temperature=0,
)

SYSTEM_PROMPT = """Kamu adalah asisten investasi saham Indonesia yang expert.
Berikan analisis yang tajam, akurat, dan mudah dipahami investor retail.
Gunakan data dari tools untuk mendukung jawabanmu. Jangan mengarang data."""

async def run_tool_call(state: AgentState) -> AgentState:
    """Node: LLM memutuskan tool mana yang dipanggil."""
    llm_with_tools = _llm.bind_tools(TOOLS)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}

# ToolNode menangani eksekusi, termasuk parallel
tool_node = ToolNode(TOOLS)

async def generate_final_answer(state: AgentState) -> AgentState:
    """Node: Generate jawaban final berdasarkan semua context yang terkumpul."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = await _llm.ainvoke(messages)
    return {"messages": [response]}

async def direct_answer(state: AgentState) -> AgentState:
    """Node: Jawab langsung tanpa tool (untuk pertanyaan general)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = await _llm.ainvoke(messages)
    return {"messages": [response]}

async def ask_clarification(state: AgentState) -> AgentState:
    """Node: Minta klarifikasi jika ticker tidak jelas."""
    response = AIMessage(
        content="Mohon sebutkan kode saham (ticker) yang ingin Anda tanyakan. "
                "Contoh: BBCA, TLKM, GOTO, BBRI, ASII."
    )
    return {"messages": [response]}

def route_after_tool(state: AgentState) -> str:
    """Setelah tool call selesai, selalu generate final answer."""
    return "generate_final_answer"

