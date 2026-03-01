import asyncio
import logging
from app.config.settings import settings
from app.scrapers.news_scraper import CommodityNewsScraper
from app.services.db_service import QdrantService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("scraper_job")

async def run():
    logger.info("🚀 Scraping job dimulai...")

    scraper = CommodityNewsScraper(api_key=settings.THENEWSAPI_KEY)
    db      = QdrantService(collection_name="saham_news")

    # Ambil berita 25 jam terakhir (overlap 1 jam antisipasi keterlambatan)
    news_list = await scraper.get_latest_news(hours=25)
    logger.info(f"✅ Berhasil scrape {len(news_list)} artikel")

    if not news_list:
        logger.warning("⚠️  Tidak ada artikel baru.")
        return

    await db.upsert_data(news_list, source_type="news_api")
    logger.info("✅ Selesai. Proses exit.")

if __name__ == "__main__":
    asyncio.run(run())
