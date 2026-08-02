from types import SimpleNamespace

from rag.retrieval.repository import QdrantRepository, clear_payload_cache
from rag.retrieval.retrievers.lexical_retriever import (
    clear_bm25_cache,
)


class FakeClient:
    def __init__(self):
        self.scroll_calls = 0
        self.points = [SimpleNamespace(payload={"chunk_id": "a", "text": "alpha"})]

    def count(self, **kwargs):
        return SimpleNamespace(count=len(self.points))

    def scroll(self, **kwargs):
        self.scroll_calls += 1
        return self.points, None


def test_payload_snapshot_is_shared_between_repository_contexts():
    clear_payload_cache()
    first_client = FakeClient()
    second_client = FakeClient()

    first = QdrantRepository(db_path="cache-test", collection_name="legal_docs")
    first.client = first_client
    second = QdrantRepository(db_path="cache-test", collection_name="legal_docs")
    second.client = second_client

    assert first.all_payloads() == second.all_payloads()
    assert first_client.scroll_calls == 1
    assert second_client.scroll_calls == 0


def test_payload_snapshot_invalidation_forces_refresh():
    clear_payload_cache()
    client = FakeClient()
    repository = QdrantRepository(db_path="cache-test", collection_name="legal_docs")
    repository.client = client

    repository.all_payloads()
    clear_payload_cache(collection_name="legal_docs")
    repository.all_payloads()

    assert client.scroll_calls == 2


def test_bm25_cache_can_be_invalidated():
    # Public smoke test: the invalidation hook must be callable during an
    # index rebuild without requiring a live Qdrant connection.
    clear_bm25_cache()
