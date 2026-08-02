from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.reranker import LegalReranker


class FakeCrossEncoder:
    def __init__(self):
        self.predict_calls: list[int] = []

    def predict(self, pairs, batch_size=32):
        self.predict_calls.append(len(pairs))
        return [0.1 + index / 100 for index, _ in enumerate(pairs)]


def _intent() -> QueryIntent:
    return QueryIntent(
        raw_query="Điều kiện hợp đồng dân sự có hiệu lực?",
        normalized_query="Điều kiện hợp đồng dân sự có hiệu lực",
        loai_yeu_cau="validity_question",
    )


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id=f"doc-{chunk_id}",
        text=f"Nội dung pháp luật {chunk_id}",
        metadata={"loai_van_ban": "bo_luat", "citation": f"Điều {chunk_id}"},
    )


def test_cross_encoder_cache_reuses_exact_scores_without_changing_results():
    reranker = LegalReranker.__new__(LegalReranker)
    reranker.encoder = FakeCrossEncoder()
    reranker.meta_bonus_weights = {"bo_luat": 0.8}
    score_cache = {}

    first = reranker.rerank(_intent(), [_chunk("1"), _chunk("2")], score_cache=score_cache)
    second = reranker.rerank(
        _intent(),
        [_chunk("1"), _chunk("2"), _chunk("3")],
        score_cache=score_cache,
    )

    assert reranker.encoder.predict_calls == [2, 1]
    assert first[0].scores["cross_encoder"] == second[0].scores["cross_encoder"]
    assert first[1].scores["cross_encoder"] == second[1].scores["cross_encoder"]
    assert all("final" in item.scores for item in second)
