from typing import Any
from app.config import settings

class EmbedderFactory:
    """
    Factory để khởi tạo Embedder.
    Ưu tiên sử dụng Cohere nếu có API Key trong file .env, 
    nếu không sẽ tự động lùi về (fallback) dùng Ollama nội bộ.
    """
    @staticmethod
    def get_embedder(model_name: str | None = None) -> Any:
        # Nếu có API Key Cohere, luôn ưu tiên Cohere
        if settings.cohere_api_key:
            from ingestion.embedding.cohere_embedder import CohereEmbedder
            return CohereEmbedder(
                api_key=settings.cohere_api_key, 
                model_name="embed-multilingual-v3.0"
            )
            
        # Fallback về Ollama
        from ingestion.embedding.ollama_embedder import OllamaEmbedder
        model_to_use = model_name or settings.embedding_model_name
        return OllamaEmbedder(model_name=model_to_use)
