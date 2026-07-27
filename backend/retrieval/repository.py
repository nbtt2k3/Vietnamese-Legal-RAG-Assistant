from qdrant_client import QdrantClient, models
from app.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential


class QdrantRepository:
    def __init__(self, db_path: str = str(settings.qdrant_db_path), collection_name: str = "legal_docs"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.client: QdrantClient | None = None
        self._payloads: list[dict] | None = None

    def __enter__(self):
        if settings.qdrant_url:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key
            )
        else:
            self.client = QdrantClient(path=self.db_path)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.client is not None:
            self.client.close()
            self.client = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    def vector_search(self, vector: list[float], limit: int = 20, query_filter: models.Filter | None = None):
        if self.client is None:
            raise RuntimeError("QdrantRepository must be opened with a context manager.")
        return self.client.query_points(
            collection_name=self.collection_name,
            query=vector,
            limit=limit,
            query_filter=query_filter,
        ).points

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    def all_payloads(self) -> list[dict]:
        if self.client is None:
            raise RuntimeError("QdrantRepository must be opened with a context manager.")
        if self._payloads is not None:
            return self._payloads
        self._payloads = []
        next_page_offset = None
        
        while True:
            points, next_page_offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                offset=next_page_offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                self._payloads.append(point.payload or {})
                
            if next_page_offset is None:
                break
                
        return self._payloads
