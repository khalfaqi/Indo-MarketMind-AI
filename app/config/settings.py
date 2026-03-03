from pydantic_settings import BaseSettings
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent  
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    # LLM
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.3-70b-versatile" 
    LLM_MAX_TOKENS: int = 1024

    # Embeddings
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DEBUG: bool = False
    THENEWSAPI_KEY: str

    # Qdrant (database vector)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str 
    QDRANT_CLUSTER_ENDPOINT: str 

    # Telegram Bot
    TELE_BOT_TOKEN: str | None = None
    

    class Config:
        env_file = str(ENV_FILE) if ENV_FILE.exists() else None
        env_file_encoding = 'utf-8'
        extra = 'ignore'

settings = Settings()