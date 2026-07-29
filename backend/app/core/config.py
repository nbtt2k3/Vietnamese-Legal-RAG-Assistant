from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vietnamese Legal RAG Assistant"

    project_root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = project_root / "data"
    raw_dir: Path = data_dir / "raw"
    parsed_dir: Path = data_dir / "parsed"
    cleaned_dir: Path = data_dir / "cleaned"
    metadata_dir: Path = data_dir / "metadata"
    chunks_dir: Path = data_dir / "chunks"
    embeddings_dir: Path = data_dir / "embeddings"
    qdrant_db_path: Path = data_dir / "qdrant_db"

    embedding_model_name: str = "bge-m3:latest"
    llm_model_name: str = "llama3"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    cross_encoder_reranking_enabled: bool = True

    candidate_limit: int = 18
    top_k: int = 40
    embed_batch_size: int = 32

    groq_api_key: str | None = None
    cohere_api_key: str | None = None
    api_key: str | None = None

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

    secret_key: str = "supersecretkey"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080

    database_url: str | None = None
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"production", "prod"}

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_security(self):
        if not self.is_production:
            return self
        if self.secret_key == "supersecretkey" or len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be overridden with at least 32 characters in production")
        if not self.api_key or len(self.api_key) < 16:
            raise ValueError("API_KEY must be set with at least 16 characters in production")
        if "*" in self.cors_origins:
            raise ValueError("ALLOWED_ORIGINS must not include '*' in production")
        return self

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
