import cohere
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

class CohereEmbedder:
    """
    Class giao tiếp với Cohere API để sinh Vector.
    Mặc định sử dụng model embed-multilingual-v3.0.
    """
    def __init__(self, api_key: str, model_name: str = "embed-multilingual-v3.0"):
        self.model_name = model_name
        self.client = cohere.Client(api_key=api_key)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=False)
    def embed_text(self, text: str) -> List[float]:
        """
        Gửi 1 đoạn text lên Cohere API. (Dành cho câu truy vấn của người dùng)
        """
        try:
            response = self.client.embed(
                texts=[text],
                model=self.model_name,
                input_type="search_query"
            )
            return response.embeddings[0]
        except Exception as e:
            from app.logger import logger
            logger.warning(f"Cohere embedding failed for query: {e}")
            return []
            
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Nhúng nhiều đoạn text. (Dành cho tài liệu pháp luật lúc Ingestion)
        """
        if not texts:
            return []
        
        response = self.client.embed(
            texts=texts,
            model=self.model_name,
            input_type="search_document"
        )
        return response.embeddings
