from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.reranker import LegalReranker
from pytest import approx


def _intent() -> QueryIntent:
    return QueryIntent(
        raw_query="dieu kien hop dong",
        normalized_query="dieu kien hop dong",
        loai_yeu_cau="validity_question",
    )


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id=f"doc-{chunk_id}",
        text=f"Noi dung {chunk_id}",
        metadata={"loai_van_ban": "bo_luat", "citation": f"Dieu {chunk_id}"},
    )


def test_jina_scores_are_applied_and_metadata_bonus_is_preserved(monkeypatch):
    reranker = LegalReranker.__new__(LegalReranker)
    reranker.encoder = None
    reranker.using_jina = True
    reranker.jina_api_key = "test-key"
    reranker.meta_bonus_weights = {"bo_luat": 0.8}
    monkeypatch.setattr(reranker, "_jina_predict", lambda query, documents: [0.2, 0.9])

    result = reranker.rerank(_intent(), [_chunk("1"), _chunk("2")], top_k=2)

    assert [item.chunk_id for item in result] == ["2", "1"]
    assert result[0].scores["cross_encoder"] == 0.9
    assert result[0].scores["final"] == approx(2.1)


def test_jina_failure_falls_back_without_exposing_key(monkeypatch):
    reranker = LegalReranker.__new__(LegalReranker)
    reranker.encoder = None
    reranker.using_jina = True
    reranker.jina_api_key = "secret-key"
    reranker.meta_bonus_weights = {"bo_luat": 0.8}

    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(reranker, "_jina_predict", fail)
    result = reranker.rerank(_intent(), [_chunk("1")])

    assert result[0].chunk_id == "1"
    assert reranker.using_jina is False
    assert "secret-key" not in str(result)

def test_jina_scores_use_request_cache(monkeypatch):
    reranker = LegalReranker.__new__(LegalReranker)
    reranker.encoder = None
    reranker.using_jina = True
    reranker.jina_api_key = "test-key"
    reranker.meta_bonus_weights = {"bo_luat": 0.8}
    calls = []

    def predict(query, documents):
        calls.append(len(documents))
        return [0.5 for _ in documents]

    monkeypatch.setattr(reranker, "_jina_predict", predict)
    cache = {}
    reranker.rerank(_intent(), [_chunk("1"), _chunk("2")], score_cache=cache)
    reranker.rerank(_intent(), [_chunk("1"), _chunk("2")], score_cache=cache)

    assert calls == [2]
