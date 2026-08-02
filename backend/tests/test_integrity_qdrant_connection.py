from pathlib import Path

from ingestion import integrity


def test_compare_qdrant_chunks_uses_remote_qdrant_when_configured(monkeypatch, tmp_path):
    expected_chunk = {"chunk_id": "chunk-1"}
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "chunks.json").write_text(
        '[{"chunk_id": "chunk-1"}]', encoding="utf-8"
    )

    class FakePoint:
        payload = {"chunk_id": "chunk-1"}

    class FakeClient:
        init_kwargs = None

        def __init__(self, **kwargs):
            FakeClient.init_kwargs = kwargs

        def scroll(self, **kwargs):
            return [FakePoint()], None

        def close(self):
            pass

    monkeypatch.setattr(integrity, "settings", type(
        "Settings", (), {
            "qdrant_url": "http://qdrant:6333",
            "qdrant_api_key": "test-key",
        }
    )())
    monkeypatch.setattr("qdrant_client.QdrantClient", FakeClient)

    result = integrity.compare_qdrant_chunks(
        chunks_dir,
        Path("unused-local-path"),
        "legal_docs",
    )

    assert result["is_consistent"] is True
    assert FakeClient.init_kwargs == {
        "url": "http://qdrant:6333",
        "api_key": "test-key",
    }
