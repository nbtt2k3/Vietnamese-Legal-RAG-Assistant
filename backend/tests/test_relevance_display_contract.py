from rag.generation.utils import chunk_to_citation
from rag.retrieval.models import RetrievedChunk
from rag.retrieval.pipeline import RetrievalPipeline


def _chunk(index: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{index}",
        doc_id="doc",
        text="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
        metadata={"citation": f"Bộ luật Dân sự, Điều {index}", "loai_van_ban": "bo_luat"},
        scores={"final": 0.01},
        sources=["test"],
    )


def test_display_relevance_uses_rank_not_raw_score():
    ranked = [_chunk(index) for index in range(1, 10)]

    RetrievalPipeline.__new__(RetrievalPipeline)._annotate_display_relevance(ranked)

    assert [item.relevance_label for item in ranked[:3]] == ["high", "high", "high"]
    assert [item.relevance_label for item in ranked[3:8]] == ["medium"] * 5
    assert ranked[8].relevance_label == "low"
    assert [item.relevance_rank for item in ranked[:4]] == [1, 2, 3, 4]


def test_citation_record_preserves_display_relevance_contract():
    chunk = _chunk(1)
    chunk.relevance_label = "high"
    chunk.relevance_rank = 1

    citation = chunk_to_citation(chunk)

    assert citation.relevance_score == 0.01
    assert citation.relevance_label == "high"
    assert citation.relevance_rank == 1
