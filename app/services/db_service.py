from qdrant_client import AsyncQdrantClient
from sentence_transformers import SentenceTransformer
from qdrant_client.models import MatchAny, PointStruct, Distance, VectorParams, PayloadSchemaType
from datetime import datetime
from app.config.settings import settings
from groq import AsyncGroq
from qdrant_client.models import Filter, FieldCondition, Range
import time
from app.tools.cleaning import preprocess_with_chunks
from zoneinfo import ZoneInfo

class QdrantService:
    def __init__(self, collection_name: str = "saham_news"):
        self.collection_name = collection_name
        self._embed_model = None

        if "http" in settings.QDRANT_CLUSTER_ENDPOINT: # Kalau ada "http" → endpoint adalah full URL (cloud/remote)
            self.qdrant = AsyncQdrantClient(
                url=settings.QDRANT_CLUSTER_ENDPOINT, 
                api_key=settings.QDRANT_API_KEY # Cloud pakai API key
            )
        else: # Kalau tidak ada "http" → endpoint hanya hostname/IP (local/docker)
            self.qdrant = AsyncQdrantClient(
                host=settings.QDRANT_CLUSTER_ENDPOINT, 
                port=settings.QDRANT_PORT # Port wajib diisi (default: 6333)
            )

    @property
    def embed_model(self):
        """Lazy load — model hanya diinisialisasi sekali saat pertama dipakai"""
        if self._embed_model is None:
            
            self._embed_model = SentenceTransformer(
                settings.EMBEDDING_MODEL
            )
        return self._embed_model

    async def _ensure_collection(self):
        collections = (await self.qdrant.get_collections()).collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            await self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            # Buat index untuk scraped_at agar filter cepat
            await self.qdrant.create_payload_index(
                collection_name=self.collection_name,
                field_name="scraped_at",
                field_schema=PayloadSchemaType.INTEGER,  # karena pakai Unix timestamp
            )

    async def upsert_data(self, data_list: list, source_type: str):
        """
        data_list: Bisa list dari News API atau hasil Scraping YT
        source_type: 'news_api' atau 'youtube'
        """
        await self._ensure_collection()
        points = []
        scraped_timestamp = int(datetime.now(ZoneInfo("Asia/Jakarta")).timestamp())


        for item in data_list:
            raw = item.model_dump() if hasattr(item, 'model_dump') else item
            chunk_articles = preprocess_with_chunks(raw)

            if not chunk_articles:    
                continue

            for article in chunk_articles:    
                text_to_embed = f"[{source_type.upper()}] {article['embedding_source']}"
                vector = self.embed_model.encode(text_to_embed.replace("\n", " ")).tolist()

                points.append(
                    PointStruct(
                        id=article["point_id"], 
                        vector=vector,
                        payload={
                            "title":               article["title"],
                            "url":                 article["url"],
                            "source":              source_type,
                            "content":             article["content"],
                            "summary":             article["summary"],
                            "published_at":        article["published_at"],
                            "related_commodities": article["related_commodities"],
                            "related_stocks":      article["related_stocks"],
                            "scraped_at":          scraped_timestamp,
                            "chunk_index":         article.get("chunk_index", 0),   
                            "total_chunks":        article.get("total_chunks", 1),  
                        }
                    )
                )
        
        await self.qdrant.upsert(collection_name=self.collection_name, points=points)
        print(f"Upserted {len(points)} points to Qdrant from {source_type}")

    async def prune_old_data(self, days: int = 7):
        """Hapus data yang scraped_at-nya lebih dari 7 hari yang lalu"""
        cutoff_timestamp = int(time.time()) - (days * 24 * 3600)
        
        # Delete points dengan scraped_at < cutoff
        await self.qdrant.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="scraped_at",
                        range=Range(lt=cutoff_timestamp)  # less than cutoff
                    )
                ]
            )
        )
        print(f"Pruned data older than {days} days (before timestamp {cutoff_timestamp})")

    async def search(self, query_text: str, limit: int = 5, filter_commodity: str = None, filter_stock: str = None):
        query_vector = self.embed_model.encode(
                       query_text.replace("\n", " ")
                       ).tolist()
                        

        search_result = await self.qdrant.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            # query_filter=
        )
        return search_result.points

