from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Vietnamese Legal RAG Assistant"
    
    # Paths
    project_root: Path = Path(__file__).parent.parent
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    parsed_dir: Path = data_dir / "parsed"
    cleaned_dir: Path = data_dir / "cleaned"
    metadata_dir: Path = data_dir / "metadata"
    chunks_dir: Path = data_dir / "chunks"
    embeddings_dir: Path = data_dir / "embeddings"
    qdrant_db_path: Path = data_dir / "qdrant_db"
    
    # Models
    embedding_model_name: str = "bge-m3:latest"
    llm_model_name: str = "llama3"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    cross_encoder_reranking_enabled: bool = True
    # Pipeline Tuning
    candidate_limit: int = 18
    top_k: int = 40
    embed_batch_size: int = 32
    # API Keys
    groq_api_key: str | None = None
    cohere_api_key: str | None = None
    api_key: str | None = None

    # Infrastructure
    redis_url: str = "redis://localhost:6379/0"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    request_body_limit_bytes: int = 1024 * 1024
    rate_limit_capacity: float = 50.0
    rate_limit_refill_per_second: float = 2.0
    rate_limit_ttl_seconds: int = 60
    llm_judge_enabled: bool = False
    llm_judge_timeout_seconds: float = 15.0
    llm_judge_max_attempts: int = 1

    environment: str = "development"
    
    # Auth Settings
    secret_key: str = "supersecretkey" # Default for dev, override in prod
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080 # 7 days
    
    # Database Settings (Environment Variables Override)
    database_url: str | None = None
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
