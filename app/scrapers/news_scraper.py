from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import trafilatura
from app.config.settings import settings
import httpx
import trafilatura
import asyncio

class MacroCommodityNews(BaseModel):
    title: str
    summary: str
    url: str
    published_at: datetime
    source: str
    content: Optional[str] = None
    related_commodities: List[str] = []
    related_stocks: List[str] = []
    embedding_source: Optional[str] = None

async def extract_full_article_async(client: httpx.AsyncClient, url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        # Gunakan timeout sedikit lebih lama untuk situs berita yang berat
        response = await client.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            return ""
        
        # Trafilatura bekerja lebih baik jika diberi hint url
        text = trafilatura.extract(
            response.text, 
            include_comments=False, 
            include_tables=False,
            no_fallback=False, # Biarkan dia mencoba berbagai metode
            favor_precision=True
        )
        return text or ""
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""
    
class CommodityNewsScraper:

    COMMODITY_KEYWORDS = [
        "batubara", "coal", "minyak", "oil", "crude",
        "emas", "gold", "nikel", "nickel", "timah", "tin", 
        "copper", "aluminium", "aluminum", "cpo", "palm oil",
        "gas", "lng"
    ]
    
    SEARCH_QUERY = (
        "saham | IHSG | BEI | emiten | OJK "
        "batubara | minyak | emas | nikel | "
        "\"ekonomi Indonesia\""
    )

    TOP_SAHAM = {
        # --- Perbankan ---  
        "BBCA": ["Bank Central Asia Tbk"],
        "BBRI": ["Bank Rakyat Indonesia (Persero) Tbk"],
        "BMRI": ["Bank Mandiri (Persero) Tbk"],
        "BBNI": ["Bank Negara Indonesia (Persero) Tbk"],
        "BBTN": ["Bank Tabungan Negara (Persero) Tbk"],
        "ARTO": ["Bank Jago Tbk"],
        "AGRO": ["Bank Raya Indonesia Tbk"],
        "BBYB": ["Bank NeoCommerce Tbk"],
        "BNLI": ["Bank Permata Tbk"],
        "BDMN": ["Bank Danamon Indonesia Tbk"],
        "BNGA": ["Bank CIMB Niaga Tbk"],
        "BACA": ["Bank Capital Indonesia Tbk"],
        "BBHI": ["Allo Bank Indonesia Tbk"],
        "BJBR": ["Bank Pembangunan Daerah Jawa Barat dan Banten Tbk"],
        "BJTM": ["Bank Pembangunan Daerah Jawa Timur Tbk"],
        "NISP": ["Bank OCBC NISP Tbk"],
        "BRIS": ["Bank Syariah Indonesia Tbk"],
        "BTPS": ["Bank BTPN Syariah Tbk"],
        "BBKP": ["Bank KB Bukopin Tbk"],
        "BBMD": ["Bank Mestika Dharma Tbk"],
        "BNBA": ["Bank Bumi Arta Tbk"],
        "BANK": ["Bank Aladin Syariah Tbk"],
        "AMAR": ["Bank Amar Indonesia Tbk"],
        "AGRS": ["Bank IBK Indonesia Tbk"],       

        # --- Telekomunikasi & Menara ---
        "TLKM": ["Telkom Indonesia"],
        "ISAT": ["Indosat Ooredoo Hutchison"], 
        "EXCL": ["XL Axiata"],                 
        "TOWR": ["Sarana Menara Nusantara"],   
        "MTEL": ["Dayamitra Telekomunikasi"],  
        "DCII": ["DCI Indonesia"],           

        # --- Energi, Tambang & Mineral ---
        "ADRO": ["Alamtri Resources Indonesia"],
        "AADI": ["Adaro Andalan Indonesia"],    
        "BYAN": ["Bayan Resources"],            
        "ADMR": ["Adaro Minerals Indonesia"],    
        "ITMG": ["Indo Tambangraya Megah"],
        "PTBA": ["Bukit Asam"],
        "PGAS": ["Perusahaan Gas Negara"],
        "AKRA": ["AKR Corporindo"],              
        "MEDC": ["Medco Energi Internasional"],  
        "BUMI": ["Bumi Resources"],              

        # --- Logam & Hilirisasi ---
        "AMMN": ["Amman Mineral Internasional"], 
        "ANTM": ["Aneka Tambang"],
        "MDKA": ["Merdeka Copper Gold"],
        "MBMA": ["Merdeka Battery Materials"],   
        "NCKL": ["Trimegah Bangun Persada"],     
        "INCO": ["Vale Indonesia"],              
        "BRMS": ["Bumi Resources Minerals"],     

        # --- Barito Group (Prajogo Pangestu) ---
        "BREN": ["Barito Renewables Energy"],     
        "TPIA": ["Chandra Asri Pacific"],        
        "BRPT": ["Barito Pacific"],              
        "CUAN": ["Petrindo Jaya Kreasi"],        

        # --- Consumer Goods & Retail ---
        "UNVR": ["Unilever Indonesia"],
        "ICBP": ["Indofood CBP"],
        "INDF": ["Indofood Sukses Makmur"],
        "GGRM": ["Gudang Garam"],                
        "HMSP": ["HM Sampoerna"],                
        "MYOR": ["Mayora Indah"],                
        "AMRT": ["Sumber Alfaria Trijaya"],     
        "ACES": ["Aspirasi Hidup Indonesia"],   

        # --- Konglomerasi & Industri Lainnya ---
        "ASII": ["Astra International"],
        "UNTR": ["United Tractors"],             
        "GOTO": ["GoTo Gojek Tokopedia"],
        "EMTK": ["Elang Mahkota Teknologi"],     
        "DSSA": ["Dian Swastatika Sentosa"],     
        "SMGR": ["Semen Indonesia"],
        "INKP": ["Indah Kiat Pulp & Paper"],     
        "TKIM": ["Pabrik Kertas Tjiwi Kimia"],   
        "CPIN": ["Charoen Pokphand Indonesia"],  

        # --- Farmasi ---
        "DVLA": ["Darya-Varia Laboratoria Tbk"],         
        "INAF": ["Indofarma (Persero) Tbk"],           
        "KAEF": ["Kimia Farma (Persero) Tbk"],           
        "MERK": ["Merck Indonesia Tbk"],                  
        "PEHA": ["Phapros Tbk"],                        
        "PEVE": ["Penta Valent Tbk"],                     
        "PYFA": ["Pyridam Farma Tbk"],                  
        "SOHO": ["Soho Global Health Tbk"],               
        "TSPC": ["Tempo Scan Pacific Tbk"],              
        "SIDO": ["Industri Jamu & Farmasi Sido Muncul Tbk"],  

        # --- Properti ---
        "ASRI": ["Alam Sutera Realty Tbk"],
        "BKSL": ["Sentul City Tbk"],
        "KJIA": ["Kawasan Industri Jababeka Tbk"],   
        "KPIG": ["MNC Tourism Indonesia Tbk"],               
        "TRIN": ["Perintis Triniti Properti Tbk"],       
        "PANI": ["Pantai Indah Kapuk Dua Tbk"],            
        "PWON": ["Pakuwon Jati Tbk"],                     
        "CBDK": ["Bangun Kosambi Sukses Tbk"],               
        "INPP": ["Indonesian Paradise Property Tbk"],        

    }

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.thenewsapi.com/v1/news/all"

    def detect_commodities(self, text: str) -> List[str]:
        text_l = text.lower()
        return list(set([k for k in self.COMMODITY_KEYWORDS if k in text_l]))

    def detect_saham(self, text: str) -> List[str]:
        text_l = text.lower()
        found = set()
        for ticker, names in self.TOP_SAHAM.items():
            if f" {ticker.lower()} " in f" {text_l} ":
                found.add(ticker)
                continue
            for name in names:
                if name.lower() in text_l:
                    found.add(ticker)
                    break
        return list(found)

    async def fetch_news(self, **kwargs) -> List[MacroCommodityNews]:
        params = {
            "api_token": self.api_key,
            "search": self.SEARCH_QUERY,
            "countries": "id",
            "limit": 20,
        }
        if kwargs:
            params.update(kwargs)

        async with httpx.AsyncClient() as client: # Buka client
            try:
                r = await client.get(self.base_url, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"[ERROR] API Request failed: {e}")
                return []
        
            items = data.get("data", [])
            # GATHER HARUS DI DALAM BLOK 'async with'
            tasks = [extract_full_article_async(client, item.get("url", "")) for item in items]
            all_contents = await asyncio.gather(*tasks)

            results: List[MacroCommodityNews] = []

            for item, full_article_text in zip(items, all_contents):
                url = item.get("url", "")
                title = item.get("title", "")
                description = item.get("description", "") or ""
                snippet = item.get("snippet", "") 
                
                # Gunakan teks hasil scraping atau fallback ke description
                raw_text = full_article_text.strip() if full_article_text else f"{description} {snippet}"
                rich_content = raw_text[:1000] # Limit 500 karakter sesuai permintaan

                # Deteksi menggunakan teks gabungan agar lebih akurat
                detection_context = f"{title} {description} {rich_content}"
                detected_commods = self.detect_commodities(detection_context)
                detected_stocks = self.detect_saham(detection_context)

                # Format string untuk embedding
                related_info = f"Emiten: {', '.join(detected_stocks)}" if detected_stocks else "Market: Umum"
                commodity_info = f"Komoditas: {', '.join(detected_commods)}" if detected_commods else ""

                rich_embedding_text = (
                    f"JUDUL: {title}. "
                    f"ENTITAS: {related_info} {commodity_info}. "
                    f"KONTEKS: {rich_content[:300]}"
                ).replace("\n", " ").strip()

                try:
                    pub_date = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                except:
                    pub_date = datetime.now()
                
                results.append(MacroCommodityNews(
                    title=title,
                    summary=description,
                    url=url,
                    published_at=pub_date,
                    source=item.get("source", "TheNewsAPI"),
                    content=rich_content,
                    related_commodities=detected_commods,
                    related_stocks=detected_stocks,
                    embedding_source=rich_embedding_text 
                ))

            return results

    async def get_latest_news(self, hours: int = 24) -> List[MacroCommodityNews]:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        published_after_str = cutoff_time.strftime('%Y-%m-%dT%H:%M:%S')

        print(f"⏳ Mengambil berita sejak: {published_after_str} (UTC)")

        return await self.fetch_news(published_after=published_after_str)

