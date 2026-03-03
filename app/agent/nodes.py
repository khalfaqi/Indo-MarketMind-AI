import asyncio
from langchain_core.messages import AIMessage
from app.agent.state import AgentState
from app.config.settings import settings
from app.tools.stock_tool import TOOLS
from langchain_groq import ChatGroq

_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.LLM_MODEL,
    temperature=0,
)

FOREIGN_STOCK_REJECTION = (
    "Mohon maaf, {ticker} adalah saham yang diperdagangkan di bursa luar negeri, "
    "sehingga kami belum dapat menganalisisnya. Sistem kami saat ini hanya mendukung "
    "saham-saham yang terdaftar di Bursa Efek Indonesia (BEI/IDX). "
    "Silakan coba tanyakan tentang emiten IDX, misalnya BBCA, TLKM, GOTO, atau BMRI."
)

GENERAL_REJECTION = (
    "Mohon maaf, pertanyaan ini di luar cakupan sistem kami. "
    "Kami hanya dapat membantu analisis saham dan berita emiten "
    "yang terdaftar di Bursa Efek Indonesia (BEI/IDX)."
)

SYSTEM_PROMPT = """Kamu adalah asisten investasi saham Indonesia yang expert.
Berikan analisis yang tajam, akurat, dan mudah dipahami investor retail.
Gunakan data dari tools untuk mendukung jawabanmu. Jangan mengarang data."""

INTENT_INSTRUCTION = {
    "analysis": "Fokus pada analisis teknikal. Gunakan tool analisis untuk ticker {ticker}.",
    "news"    : "Fokus pada berita dan sentimen terkini. Gunakan tool berita untuk ticker {ticker}.",
    "hybrid"  : (
        "Gunakan KEDUA tool — analisis teknikal DAN berita terkini — untuk ticker {ticker}. "
        "Gabungkan hasilnya menjadi satu jawaban yang komprehensif."
    ),
}


async def run_tool_call(state: AgentState) -> AgentState:
    """Node: LLM memutuskan tool mana yang dipanggil, dipandu intent & ticker."""
    intent = state.get("intent", "hybrid")
    ticker = state.get("ticker", "")

    intent_ctx = INTENT_INSTRUCTION.get(intent, "").format(ticker=ticker)
    enriched_system = f"{SYSTEM_PROMPT}\n\n## Instruksi Sesi Ini\n{intent_ctx}"

    llm_with_tools = _llm.bind_tools(TOOLS)
    messages = [{"role": "system", "content": enriched_system}] + state["messages"]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


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
        content="Mohon sebutkan saham yang ingin Anda tanyakan. "
                "Contoh: BBCA, TLKM, GOTO, BBRI, atau nama perusahaannya."
    )
    return {"messages": [response]}


async def reject_query(state: AgentState) -> AgentState:
    """Node: Tolak query saham asing atau query tidak relevan."""
    ticker = state.get("ticker")
    message = FOREIGN_STOCK_REJECTION.format(ticker=ticker) if ticker else GENERAL_REJECTION
    return {"messages": [AIMessage(content=message)]}


async def run_hybrid_tools(state: AgentState) -> AgentState:
    """Node khusus hybrid: panggil dua tool secara paralel, deterministik."""
    ticker = state.get("ticker", "")

    analysis_tool = next(t for t in TOOLS if t.name == "get_stock_analysis")
    news_tool     = next(t for t in TOOLS if t.name == "get_stock_news")

    analysis_result, news_result = await asyncio.gather(
        analysis_tool.ainvoke({"ticker": ticker}),
        news_tool.ainvoke({"ticker": ticker}),
    )

    context = (
        f"## Data Analisis Teknikal\n{analysis_result}\n\n"
        f"## Berita Terkini\n{news_result}"
    )
    return {"messages": [AIMessage(content=context)]}
