from datetime import date

from evaluation.evaluator import LegalRAGEvaluator
from ingestion.chunker.legal_chunker import LegalChunker
from rag.retrieval.error_taxonomy import classify_retrieval_errors
from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.temporal import resolve_temporal_conflicts, temporal_state


def _intent(query="quy dinh hien hanh", year=None):
    return QueryIntent(
        raw_query=query,
        normalized_query=query,
        loai_yeu_cau="validity_question",
        time_context={"year_hint": str(year)} if year else {},
    )


def test_temporal_state_respects_historical_year_and_current_status():
    expired = {"validity_status": "het_hieu_luc", "effective_from": "2015-01-01", "effective_to": "2020-12-31"}
    assert temporal_state(expired, _intent(year=2018)) == "expired"
    assert temporal_state(expired, _intent("van ban cu het hieu luc")) == "expired"


def test_conflict_resolution_prefers_active_replacement_for_current_query():
    old = RetrievedChunk(
        "old",
        "old_doc",
        "old text",
        {"validity_status": "het_hieu_luc", "so_hieu": "01/old", "replaced_documents": []},
        {"final": 10.0},
    )
    current = RetrievedChunk(
        "new",
        "new_doc",
        "new text",
        {
            "validity_status": "dang_co_hieu_luc",
            "so_hieu": "02/new",
            "replaced_documents": ["01/old"],
        },
        {"final": 1.0},
    )
    ranked, debug = resolve_temporal_conflicts(_intent(), [old, current])

    assert debug["conflict_detected"] is True
    assert ranked[0].chunk_id == "new"
    assert all(item.chunk_id != "old" for item in ranked)


def test_retrieval_error_taxonomy_distinguishes_missing_related_document():
    case = type(
        "Case",
        (),
        {
            "query": "ap dung hai van ban",
            "expected_citations": ["Bo luat Dan su, Dieu 1", "Nghi dinh 2/2020"],
            "expected_source_types": ["bo_luat", "nghi_dinh"],
        },
    )()
    retrieval = type(
        "Retrieval",
        (),
        {
            "candidates": [
                RetrievedChunk(
                    "c1",
                    "doc",
                    "text",
                    {"citation": "Bo luat Dan su, Dieu 1", "loai_van_ban": "bo_luat"},
                )
            ]
        },
    )()

    assert classify_retrieval_errors(case, retrieval) == ["missing_related_document"]


def test_legal_chunker_adds_parent_context_and_part_metadata():
    data = {
        "doc_id": "doc1",
        "metadata": {"document": {"ten": "Bo luat test", "loai_van_ban": "bo_luat"}},
        "dieu": [
            {
                "number": "10",
                "title": "Dieu kien",
                "chuong_number": "I",
                "chuong_title": "Quy dinh chung",
                "text": "Mo dau cua dieu",
                "khoan": [{"number": "1", "text": "Noi dung khoan", "diem": []}],
            }
        ],
    }
    chunks = LegalChunker().chunk(data)
    intro = next(item for item in chunks if item.metadata.get("node_type") == "dieu")
    child = next(item for item in chunks if item.metadata.get("node_type") == "khoan")

    assert child.metadata["parent_id"] == intro.metadata["node_id"]
    assert child.metadata["parent_chunk_id"] == intro.chunk_id
    assert child.metadata["parent_context"]
    assert child.metadata["chunk_part"] == 1
    assert child.metadata["chunk_parts"] == 1
