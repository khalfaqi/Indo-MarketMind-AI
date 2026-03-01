from langchain_groq import ChatGroq
from app.agent.state import AgentState, IntentPlan
from app.config.settings import settings

_classifier_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.LLM_MODEL,
    temperature=0,
)

CLASSIFIER_PROMPT = """
Kamu adalah intent classifier untuk sistem analisa saham Indonesia.

Klasifikasikan query user ke dalam salah satu kategori berikut:
- "analysis"  : user minta analisis harga, indikator teknikal (RSI/MACD), 
                rekomendasi beli/jual/hold, pergerakan harga saham
- "news"      : user minta berita terbaru, pengumuman, laporan keuangan,
                aksi korporasi, sentimen pasar terkini
- "hybrid"    : query butuh KEDUANYA, contoh: "kenapa BBCA turun hari ini?"

Jika ticker saham tidak disebutkan untuk kategori analysis/news/hybrid,
set needs_clarification = true.

Contoh ticker IDX: BBCA, TLKM, GOTO, BBRI, ASII, BMRI
"""

async def classify_intent(state: AgentState) -> AgentState:
    """Node: Klasifikasikan intent sebelum routing ke tool yang tepat."""

    user_query = state["messages"][-1].content

    structured_llm = _classifier_llm.with_structured_output(IntentPlan)
    plan: IntentPlan = await structured_llm.ainvoke([
        {"role": "system", "content": CLASSIFIER_PROMPT},
        {"role": "user", "content": user_query}
    ])
    
    return {
        "intent": plan.intent,
        "ticker": plan.ticker,
        "needs_clarification": plan.needs_clarification,
    }

def route_by_intent(state: AgentState) -> str:
    if state.get("needs_clarification"):
        return "ask_clarification"
    
    intent = state.get("intent")
    if intent in ["analysis", "news", "hybrid"]:
        return "run_tool_call"
    
    return "direct_answer"