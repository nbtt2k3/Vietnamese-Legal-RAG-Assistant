import ollama
import httpx
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

class OllamaEmbedder:
    """
    Class giao tiếp với Ollama server để sinh Vector.
    Mặc định sử dụng model bge-m3:latest
    """
    def __init__(self, model_name: str = "bge-m3:latest", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.client = ollama.Client(host=host, timeout=httpx.Timeout(30.0))
        
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=2), reraise=False)
    def embed_text(self, text: str) -> List[float]:
        """
        Gửi 1 đoạn text (Chunk) lên Ollama và lấy về mảng float (Vector).
        """
        try:
            response = self.client.embeddings(model=self.model_name, prompt=text)
            return response.get("embedding", [])
        except Exception as e:
            from app.logger import logger
            logger.warning(f"Ollama embedding failed for model {self.model_name}: {e}")
            return []
            
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=2), reraise=True)
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Nhúng nhiều đoạn text (Dành cho việc tối ưu tốc độ nếu cần).
        Lưu ý: API /api/embeddings của Ollama mặc định xử lý từng text, 
        nên ta lặp qua danh sách.
        """
        if not texts:
            return []
        # ollama==0.1.x exposes only the single-prompt embeddings endpoint.
        # Keep batch semantics for callers while using the compatible transport.
        if hasattr(self.client, "embed"):
            response = self.client.embed(model=self.model_name, input=texts)
            return list(response.get("embeddings", []))
        return [self.client.embeddings(model=self.model_name, prompt=text).get("embedding", []) for text in texts]
