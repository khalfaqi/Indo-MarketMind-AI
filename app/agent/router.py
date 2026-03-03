from langchain_groq import ChatGroq
from app.agent.state import AgentState, IntentPlan
from app.config.settings import settings

_classifier_llm = ChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.LLM_MODEL,
    temperature=0,
)

CLASSIFIER_PROMPT = """Kamu adalah asisten cerdas untuk sistem analisa saham Bursa Efek Indonesia (BEI/IDX).

## Tugasmu
Pahami maksud query user, lalu tentukan:
1. Apa yang user inginkan (intent)
2. Kode saham IDX yang relevan (ticker)
3. Apakah query ini bisa dilayani atau tidak

---

## Kategori Intent
- `analysis`  : user ingin analisis teknikal (RSI, MACD, Bollinger Bands), tren harga,
                rekomendasi beli/jual/hold, atau pergerakan historis suatu saham
- `news`      : user ingin berita terkini, pengumuman emiten, laporan keuangan,
                aksi korporasi (dividen, right issue, merger), atau sentimen pasar
- `hybrid`    : query butuh analisis DAN berita sekaligus —
                contoh: "kenapa BBCA turun hari ini?", "apakah layak beli Telkom sekarang?"
- `reject`    : saham yang dimaksud bukan dari BEI/IDX (bursa asing seperti NYSE, NASDAQ, dll.),
                atau query sama sekali tidak berkaitan dengan saham

---

## Resolusi Nama Perusahaan → Ticker IDX
Kenali nama umum, merek, dan singkatan perusahaan Indonesia dan ubah ke kode IDX-nya:

| Yang user sebut                      | Ticker IDX |
|--------------------------------------|------------|
| BCA, Bank Central Asia               | BBCA       |
| Mandiri, Bank Mandiri                | BMRI       |
| BRI, Bank Rakyat Indonesia           | BBRI       |
| BNI, Bank Negara Indonesia           | BBNI       |
| Telkom, Telkomsel, Telekomunikasi    | TLKM       |
| Gojek, GoTo, Tokopedia               | GOTO       |
| Astra, Astra International           | ASII       |
| Indofood                             | INDF       |
| Unilever Indonesia                   | UNVR       |
| Antam, Aneka Tambang                 | ANTM       |
| Bukit Asam                           | PTBA       |
| Semen Indonesia                      | SMGR       |
| Kalbe, Kalbe Farma                   | KLBF       |
| Bank Jago                            | ARTO       |
| BSI, Bank Syariah Indonesia          | BRIS       |
| Pertamina Geothermal                 | PGEO       |
| Vale Indonesia                       | INCO       |
| Barito Pacific                       | BRPT       |
| Charoen Pokphand Indonesia           | CPIN       |
| Merdeka Copper Gold                  | MDKA       |

Gunakan pengetahuanmu tentang emiten BEI untuk mengenali nama lain yang tidak tercantum di atas.

---

## Aturan
- Jika user menyebut nama/merek perusahaan lokal (bukan kode ticker), resolusikan ke kode IDX yang tepat.
- Jika tidak ada ticker/perusahaan yang bisa diidentifikasi, set `needs_clarification = true`.
- Jika saham yang dimaksud adalah saham asing (bukan IDX), set `intent = "reject"` dan isi `ticker` dengan kode asingnya (misal: TSLA, AAPL).
- Jika query tidak berhubungan dengan saham sama sekali, set `intent = "reject"`.
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
    
    if intent == "reject":
        return "reject_query"

    return "direct_answer"
