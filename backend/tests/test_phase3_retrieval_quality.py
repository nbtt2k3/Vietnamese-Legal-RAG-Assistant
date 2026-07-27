from retrieval.models import QueryIntent, RetrievedChunk
from retrieval.pipeline import RetrievalPipeline
from retrieval.query_analyzer import QueryAnalyzer
from retrieval.retrievers.lexical_retriever import LexicalRetriever
from retrieval.retrievers.metadata_retriever import MetadataRetriever
from retrieval.text_utils import contains_normalized, tokenize_for_bm25


def test_query_analyzer_handles_unaccented_validity_question():
    intent = QueryAnalyzer().analyze(
        "the chap co hieu luc khi nao theo bo luat dan su",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "validity_question"
    assert "thế chấp" in intent.key_phrases


def test_query_analyzer_handles_unaccented_article_lookup():
    intent = QueryAnalyzer().analyze("dieu 117 bo luat dan su 2015", force_deterministic=True)

    assert intent.loai_yeu_cau == "citation_lookup"
    assert "Điều 117" in intent.citation_targets


def test_text_matching_and_bm25_tokens_are_accent_insensitive():
    assert contains_normalized("Điều kiện có hiệu lực của giao dịch dân sự", "dieu kien hieu luc")

    tokens = tokenize_for_bm25("thế chấp")
    assert "thế" in tokens
    assert "the" in tokens
    assert "chấp" in tokens
    assert "chap" in tokens


def test_lexical_scoring_accepts_unaccented_query_terms():
    intent = QueryIntent(
        raw_query="the chap co hieu luc khong",
        normalized_query="the chap co hieu luc khong",
        loai_yeu_cau="validity_question",
        keywords=["the", "chap", "hieu", "luc"],
        key_phrases=["the chap", "hieu luc"],
        source_priority=["bo_luat"],
    )
    payload = {"dieu_title": "Hiệu lực của thế chấp tài sản", "loai_van_ban": "bo_luat"}
    haystack = "Điều 319. Hiệu lực của thế chấp tài sản"

    assert LexicalRetriever()._score_text(haystack, intent, payload) > 0


def test_metadata_scoring_accepts_unaccented_citation_and_phrase():
    intent = QueryIntent(
        raw_query="dieu 117 dieu kien co hieu luc",
        normalized_query="dieu 117 dieu kien co hieu luc",
        loai_yeu_cau="citation_lookup",
        citation_targets=["Dieu 117"],
        key_phrases=["dieu kien co hieu luc"],
        source_priority=["bo_luat"],
    )
    payload = {
        "citation": "Bộ luật Dân sự 2015, Điều 117",
        "ten": "Bộ luật Dân sự",
        "dieu_title": "Điều kiện có hiệu lực của giao dịch dân sự",
        "loai_van_ban": "bo_luat",
        "validity_status": "co_ngay_hieu_luc",
    }

    assert MetadataRetriever()._score_payload(payload, intent) >= 7.0


class DummyRetriever:
    def __init__(self, name, count):
        self.name = name
        self.count = count

    def retrieve(self, repository, query_intent, limit=20):
        return [
            RetrievedChunk(
                chunk_id=f"{self.name}-{idx}",
                doc_id=f"{self.name}-doc-{idx}",
                text=f"{self.name} text {idx}",
                metadata={"loai_van_ban": "bo_luat", "citation": f"{self.name} {idx}"},
                scores={self.name: float(limit - idx)},
                sources=[self.name],
            )
            for idx in range(self.count)
        ]


def test_vector_fallback_runs_for_sparse_citation_lookup_candidates():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    pipeline.retrievers = [
        DummyRetriever("metadata", 1),
        DummyRetriever("lexical", 1),
        DummyRetriever("vector", 2),
    ]
    intent = QueryIntent(
        raw_query="Điều 117",
        normalized_query="Điều 117",
        loai_yeu_cau="citation_lookup",
        citation_targets=["Điều 117"],
        source_priority=["bo_luat"],
    )

    merged, debug = pipeline._collect_candidates(repository=object(), query_intent=intent)

    assert debug["retriever_hits"]["vector_fallback"] == 2
    assert any(item.sources == ["vector"] for item in merged.values())


def test_vector_fallback_is_skipped_when_exact_retrievers_are_sufficient():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    pipeline.retrievers = [
        DummyRetriever("metadata", 4),
        DummyRetriever("lexical", 4),
        DummyRetriever("vector", 2),
    ]
    intent = QueryIntent(
        raw_query="Điều 117",
        normalized_query="Điều 117",
        loai_yeu_cau="citation_lookup",
        citation_targets=["Điều 117"],
        source_priority=["bo_luat"],
    )

    _, debug = pipeline._collect_candidates(repository=object(), query_intent=intent)

    assert "vector_fallback" not in debug["retriever_hits"]
