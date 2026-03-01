import yfinance as yf
from langchain.tools import tool
import asyncio
from app.config.settings import settings
from app.services.db_service import QdrantService

@tool
async def get_stock_analysis(ticker: str) -> str:
    """
    Mengambil data fundamental terbaru. 
    Wajib digunakan untuk mendapatkan nama perusahaan dan laporan keuangan terakhir.
    """
    symbol = f"{ticker.upper()}.JK" if not ticker.upper().endswith(".JK") else ticker.upper()
    
    try:
        stock = yf.Ticker(symbol)
        
        # 1. Ambil Info Dasar (Nama & Profil)
        info = await asyncio.to_thread(lambda: stock.info)
        company_name = info.get('longName', f"Perusahaan {ticker}")
        summary = info.get('longBusinessSummary', 'Deskripsi tidak tersedia.')[:200]

        # 2. Ambil Laporan Keuangan Kuartalan (Paling Update)
        income_stmt = await asyncio.to_thread(lambda: stock.quarterly_income_stmt)
        
        if not income_stmt.empty:
            # Ambil tanggal terbaru dari kolom pertama (misal: 2025-09-30 atau 2025-12-31)
            latest_date = income_stmt.columns[0]
            date_str = latest_date.strftime('%d %B %Y')
            
            # Ambil angka laba bersih (Net Income)
            net_income = income_stmt.iloc[:, 0].get('Net Income', 0)
            net_income_formatted = f"Rp{net_income / 1e9:.2f} Miliar" if abs(net_income) < 1e12 else f"Rp{net_income / 1e12:.2f} Triliun"
        else:
            date_str = "Tidak terdeteksi"
            net_income_formatted = "N/A"

        # 3. Harga Terkini (Februari 2026)
        hist = await asyncio.to_thread(lambda: stock.history(period="1d"))
        current_price = hist['Close'].iloc[-1] if not hist.empty else 0

        return (
            f"✅ **Konfirmasi Identitas:** {company_name} ({symbol})\n"
            f"📅 **Laporan Keuangan Terakhir:** {date_str}\n"
            f"💰 **Laba Bersih:** {net_income_formatted}\n"
            f"📈 **Harga Saham (2026):** Rp{current_price:,.0f}\n\n"
            f"**Ringkasan Bisnis:**\n{summary}...\n\n"
            f"*(Data ditarik secara real-time dari yfinance)*"
        )
            
    except Exception as e:
        return f"⚠️ Kesalahan pada {ticker}: {str(e)}"


@tool
async def get_latest_news(ticker: str) -> str:
    """
    Mencari berita terbaru terkait emiten tertentu dari database berita.
    Gunakan ini untuk memahami sentimen pasar dan kejadian terkini.
    """
    try:
        service = QdrantService(collection_name="saham_news")        
        search_results = await service.search(
            collection_name="saham_news", 
            query_text=ticker, 
            limit=3
        )
        
        if not search_results:
            return f"Tidak ditemukan berita terbaru untuk {ticker} di database."

        formatted_news = []
        for i, res in enumerate(search_results, 1):
            p = res.payload
            news_item = (
                f"{i}. [{p.get('source', 'N/A').upper()}] {p.get('title')}\n"
                f"   Ringkasan: {p.get('content')[:200]}...\n"
                f"   Link: {p.get('url')}"
            )
            formatted_news.append(news_item)

        return f"📰 **Berita Terkini {ticker.upper()}**:\n\n" + "\n\n".join(formatted_news)

    except Exception as e:
        return f"Gagal mengambil berita untuk {ticker}: {str(e)}"
    

TOOLS = [get_stock_analysis, get_latest_news]
