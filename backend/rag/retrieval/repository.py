from qdrant_client import QdrantClient, models
from app.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential
from pathlib import Path
import threading


# Payloads are used by both metadata and lexical retrieval.  Keep one
# process-wide snapshot so a new repository context does not scroll the whole
# Qdrant collection for every user query.
_PAYLOAD_CACHE: dict[tuple[str, str], tuple[int, list[dict]]] = {}
_PAYLOAD_CACHE_LOCK = threading.RLock()


def clear_payload_cache(db_path: str | None = None, collection_name: str | None = None) -> None:
    """Invalidate payload snapshots after an index/alias rebuild."""
    with _PAYLOAD_CACHE_LOCK:
        if db_path is None and collection_name is None:
            _PAYLOAD_CACHE.clear()
            return

        normalized_db = str(Path(db_path).resolve()) if db_path is not None else None
        for key in list(_PAYLOAD_CACHE):
            cache_db, cache_collection = key
            if normalized_db is not None and cache_db != normalized_db:
                continue
            if collection_name is not None and cache_collection != collection_name:
                continue
            _PAYLOAD_CACHE.pop(key, None)


class QdrantRepository:
    def __init__(self, db_path: str = str(settings.qdrant_db_path), collection_name: str = "legal_docs"):
        self.db_path = db_path
        self.collection_name = collection_name
        self.client: QdrantClient | None = None
        self._payloads: list[dict] | None = None

    @property
    def _payload_cache_key(self) -> tuple[str, str]:
        # The URL/path is part of the key so local and remote deployments do
        # not accidentally share snapshots.
        connection = settings.qdrant_url or str(Path(self.db_path).resolve())
        return str(connection), self.collection_name

    def __enter__(self):
        if settings.qdrant_url:
            client_kwargs = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                client_kwargs["api_key"] = settings.qdrant_api_key
            self.client = QdrantClient(**client_kwargs)
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

        # Count is cheap and detects normal incremental updates.  Alias swaps
        # explicitly invalidate this cache in the indexer, which also covers
        # rebuilds where the new collection happens to have the same count.
        current_count = self.client.count(
            collection_name=self.collection_name,
            exact=True,
        ).count
        cache_key = self._payload_cache_key

        with _PAYLOAD_CACHE_LOCK:
            cached = _PAYLOAD_CACHE.get(cache_key)
            if cached is not None and cached[0] == current_count:
                self._payloads = cached[1]
                return self._payloads

            payloads: list[dict] = []
            next_page_offset = None
            while True:
                points, next_page_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=10000,
                    offset=next_page_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                payloads.extend(point.payload or {} for point in points)
                if next_page_offset is None:
                    break

            _PAYLOAD_CACHE[cache_key] = (len(payloads), payloads)
            self._payloads = payloads
            return self._payloads
