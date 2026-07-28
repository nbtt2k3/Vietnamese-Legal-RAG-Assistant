from retrieval.models import QueryIntent, RetrievalResult, RetrievedChunk
from retrieval.evidence_builder import EvidenceBuilder
from retrieval.pipeline import RetrievalPipeline
from retrieval.query_analyzer import QueryAnalyzer
from retrieval.constraints import exact_constraints
from retrieval.document_resolver import resolve_document_ids, source_types_from_text
from retrieval.retrievers.lexical_retriever import LexicalRetriever
from retrieval.retrievers.metadata_retriever import MetadataRetriever
from retrieval.text_utils import contains_normalized, tokenize_for_bm25
from generation.rule_based_generator import RuleBasedLegalGenerator


def test_document_resolver_uses_registry_aliases_instead_of_code_doc_id_constants():
    registry = {
        "documents": [
            {
                "doc_id": "renamed_civil_code_id",
                "loai_van_ban": "bo_luat",
                "official_number": "91/2015/QH13",
                "aliases": ["Bộ luật Dân sự", "BLDS 2015"],
            }
        ]
    }

    doc_ids = resolve_document_ids("Điều 117 BLDS 2015", registry=registry)

    assert doc_ids == {"renamed_civil_code_id"}


def test_exact_constraints_resolves_bundled_document_registry_entries():
    intent = QueryIntent(
        raw_query="Điều 117 Bộ luật Dân sự 2015",
        normalized_query="Điều 117 Bộ luật Dân sự 2015",
        loai_yeu_cau="citation_lookup",
        citation_targets=["Điều 117"],
    )

    constraints = exact_constraints(intent)

    assert constraints["article_numbers"] == {"117"}
    assert constraints["doc_ids"] == {"bo_luat_91_2015_QH13"}
    assert constraints["source_types"] == {"bo_luat"}


def test_exact_constraints_resolves_numbered_documents_from_registry_metadata():
    intent = QueryIntent(
        raw_query="Nghị định 21/2021/NĐ-CP quy định gì?",
        normalized_query="Nghị định 21/2021/NĐ-CP quy định gì?",
        loai_yeu_cau="citation_lookup",
    )

    constraints = exact_constraints(intent)

    assert constraints["doc_ids"] == {"nghi_dinh_21_2021_ND_CP"}
    assert constraints["source_types"] == {"nghi_dinh"}


def test_source_type_detection_does_not_require_doc_id_mapping():
    assert source_types_from_text("Điều 117 Bộ luật Hình sự") == {"bo_luat"}


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


def test_query_analyzer_handles_unaccented_civil_transaction_validity_question():
    intent = QueryAnalyzer().analyze(
        "giao dich dan su co hieu luc khi nao",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "validity_question"
    assert "Điều 117" in intent.citation_targets
    assert "giao dịch dân sự" in intent.key_phrases


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


def test_exact_citation_lookup_filter_removes_cross_domain_noise():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="dieu 117 bo luat dan su 2015",
        normalized_query="dieu 117 bo luat dan su 2015",
        loai_yeu_cau="citation_lookup",
        citation_targets=["Dieu 117"],
        source_priority=["bo_luat"],
    )
    merged = {
        "civil-117": RetrievedChunk(
            chunk_id="civil-117",
            doc_id="bo_luat_91_2015_QH13",
            text="Giao dich dan su co hieu luc...",
            metadata={
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Dân sự, Điều 117",
                "dieu_number": "117",
            },
        ),
        "criminal-decree": RetrievedChunk(
            chunk_id="criminal-decree",
            doc_id="nghi_dinh_19_2018_ND_CP",
            text="Trách nhiệm thi hành nghị định hình sự",
            metadata={
                "loai_van_ban": "nghi_dinh",
                "citation": "Nghị định 19/2018/NĐ-CP, Điều 8",
                "dieu_number": "8",
            },
        ),
    }
    debug = {}

    filtered = pipeline._filter_exact_lookup_candidates(intent, merged, debug)

    assert list(filtered) == ["civil-117"]
    assert debug["exact_lookup_filtered_candidates"] == 1


def test_exact_validity_filter_removes_cross_domain_noise():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="Điều kiện có hiệu lực của giao dịch dân sự là gì?",
        normalized_query="Điều kiện có hiệu lực của giao dịch dân sự là gì?",
        loai_yeu_cau="validity_question",
        citation_targets=["Điều 117"],
        key_phrases=["điều kiện có hiệu lực", "giao dịch dân sự"],
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    merged = {
        "civil-117": RetrievedChunk(
            chunk_id="civil-117",
            doc_id="bo_luat_91_2015_QH13",
            text="Giao dịch dân sự có hiệu lực khi có đủ các điều kiện...",
            metadata={
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Dân sự, Điều 117",
                "dieu_number": "117",
            },
        ),
        "criminal-117": RetrievedChunk(
            chunk_id="criminal-117",
            doc_id="bo_luat_100_2015_QH13",
            text="Quy định khác trong Bộ luật Hình sự",
            metadata={
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Hình Sự, Điều 117",
                "dieu_number": "117",
            },
        ),
        "resolution-noise": RetrievedChunk(
            chunk_id="resolution-noise",
            doc_id="nghi_quyet_noise",
            text="Điều kiện trong văn bản hình sự",
            metadata={
                "loai_van_ban": "nghi_quyet",
                "citation": "Nghị quyết hình sự, Điều 8",
                "dieu_number": "8",
            },
        ),
    }
    debug = {}

    filtered = pipeline._filter_exact_lookup_candidates(intent, merged, debug)

    assert list(filtered) == ["civil-117"]
    assert debug["exact_lookup_filtered_candidates"] == 2


def test_generator_orders_clauses_within_same_article():
    generator = RuleBasedLegalGenerator()
    items = [
        RetrievedChunk(
            chunk_id="k2",
            doc_id="bo_luat_91_2015_QH13",
            text="Khoản 2",
            metadata={"dieu_number": "117", "khoan_number": "2"},
            scores={"final": 10.0},
        ),
        RetrievedChunk(
            chunk_id="k1",
            doc_id="bo_luat_91_2015_QH13",
            text="Khoản 1",
            metadata={"dieu_number": "117", "khoan_number": "1"},
            scores={"final": 9.0},
        ),
    ]

    ordered = generator._order_same_article_units(items)

    assert [item.chunk_id for item in ordered] == ["k1", "k2"]


def test_scenario_evidence_excludes_criminal_noise_for_civil_security_context():
    intent = QueryIntent(
        raw_query="Nếu bên mua chưa thanh toán mà tài sản đang thế chấp ngân hàng thì hợp đồng có hiệu lực không?",
        normalized_query="Nếu bên mua chưa thanh toán mà tài sản đang thế chấp ngân hàng thì hợp đồng có hiệu lực không?",
        loai_yeu_cau="scenario_application",
        key_phrases=["thế chấp", "quyền định đoạt", "hiệu lực giao dịch"],
        scenario_terms=["thanh toán", "ngân hàng", "hợp đồng", "thế chấp", "tài sản"],
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    ranked = [
        RetrievedChunk(
            chunk_id="civil",
            doc_id="bo_luat_91_2015_QH13",
            text="Hiệu lực của thế chấp tài sản",
            metadata={
                "loai_van_ban": "bo_luat",
                "legal_domain_tags": ["hop_dong", "bao_dam", "tai_san"],
                "citation": "Bộ luật Dân sự, Điều 319",
            },
            scores={"final": 1.0},
        ),
        RetrievedChunk(
            chunk_id="criminal",
            doc_id="bo_luat_100_2015_QH13",
            text="Tội sử dụng mạng máy tính chiếm đoạt tài sản",
            metadata={
                "loai_van_ban": "bo_luat",
                "legal_domain_tags": ["tai_san", "hinh_su"],
                "ten": "Bộ luật Hình Sự",
                "citation": "Bộ luật Hình Sự, Điều 290",
            },
            scores={"final": 2.0},
        ),
    ]

    evidence = EvidenceBuilder().build(intent, ranked)

    assert [item.chunk_id for item in evidence.core_authorities] == ["civil"]


def test_scenario_generator_excludes_criminal_noise_for_civil_security_context():
    intent = QueryIntent(
        raw_query="Nếu bên mua chưa thanh toán mà tài sản đang thế chấp ngân hàng thì hợp đồng có hiệu lực không?",
        normalized_query="Nếu bên mua chưa thanh toán mà tài sản đang thế chấp ngân hàng thì hợp đồng có hiệu lực không?",
        loai_yeu_cau="scenario_application",
        key_phrases=["thế chấp", "quyền định đoạt", "hiệu lực giao dịch"],
        scenario_terms=["thanh toán", "ngân hàng", "hợp đồng", "thế chấp", "tài sản"],
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    result = RetrievalResult(
        query_intent=intent,
        candidates=[
            RetrievedChunk(
                chunk_id="criminal",
                doc_id="bo_luat_100_2015_QH13",
                text="Tội sử dụng mạng máy tính chiếm đoạt tài sản",
                metadata={
                    "loai_van_ban": "bo_luat",
                    "legal_domain_tags": ["tai_san", "hinh_su"],
                    "ten": "Bộ luật Hình Sự",
                    "citation": "Bộ luật Hình Sự, Điều 290",
                },
                scores={"final": 2.0},
            ),
            RetrievedChunk(
                chunk_id="civil",
                doc_id="bo_luat_91_2015_QH13",
                text="Hiệu lực của thế chấp tài sản",
                metadata={
                    "loai_van_ban": "bo_luat",
                    "legal_domain_tags": ["hop_dong", "bao_dam", "tai_san"],
                    "citation": "Bộ luật Dân sự, Điều 319",
                },
                scores={"final": 1.0},
            ),
        ],
    )

    primary = RuleBasedLegalGenerator()._select_primary_authorities(result)

    assert [item.chunk_id for item in primary] == ["civil"]


def test_scenario_evidence_keeps_criminal_sources_for_criminal_context():
    intent = QueryIntent(
        raw_query="hành vi trộm cắp tài sản bị xử phạt như thế nào",
        normalized_query="hành vi trộm cắp tài sản bị xử phạt như thế nào",
        loai_yeu_cau="scenario_application",
        key_phrases=["trộm cắp tài sản", "hình phạt"],
        scenario_terms=["trộm cắp", "giá trị tài sản"],
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    ranked = [
        RetrievedChunk(
            chunk_id="criminal",
            doc_id="bo_luat_100_2015_QH13",
            text="Tội trộm cắp tài sản",
            metadata={
                "loai_van_ban": "bo_luat",
                "legal_domain_tags": ["hinh_su", "tai_san"],
                "ten": "Bộ luật Hình Sự",
                "citation": "Bộ luật Hình Sự, Điều 173",
            },
            scores={"final": 1.0},
        )
    ]

    evidence = EvidenceBuilder().build(intent, ranked)

    assert [item.chunk_id for item in evidence.core_authorities] == ["criminal"]


def test_scenario_evidence_excludes_civil_noise_for_criminal_context():
    intent = QueryIntent(
        raw_query="hành vi trộm cắp tài sản bị xử phạt như thế nào",
        normalized_query="hành vi trộm cắp tài sản bị xử phạt như thế nào",
        loai_yeu_cau="scenario_application",
        key_phrases=["trộm cắp tài sản", "hình phạt"],
        scenario_terms=["trộm cắp", "giá trị tài sản"],
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    ranked = [
        RetrievedChunk(
            chunk_id="civil",
            doc_id="bo_luat_91_2015_QH13",
            text="Quy định dân sự về tài sản",
            metadata={
                "loai_van_ban": "bo_luat",
                "legal_domain_tags": ["bao_dam", "tai_san"],
                "ten": "Bộ luật Dân sự",
                "citation": "Bộ luật Dân sự, Điều 173",
            },
            scores={"final": 2.0},
        ),
        RetrievedChunk(
            chunk_id="criminal",
            doc_id="bo_luat_100_2015_QH13",
            text="Tội trộm cắp tài sản",
            metadata={
                "loai_van_ban": "bo_luat",
                "legal_domain_tags": ["hinh_su", "tai_san"],
                "ten": "Bộ luật Hình Sự",
                "citation": "Bộ luật Hình Sự, Điều 173",
            },
            scores={"final": 1.0},
        ),
    ]

    evidence = EvidenceBuilder().build(intent, ranked)

    assert [item.chunk_id for item in evidence.core_authorities] == ["criminal"]


def test_scenario_short_answer_is_domain_neutral():
    generator = RuleBasedLegalGenerator()
    primary = [
        RetrievedChunk(
            chunk_id="criminal",
            doc_id="bo_luat_100_2015_QH13",
            text="Tội trộm cắp tài sản",
            metadata={"citation": "Bộ luật Hình Sự, Điều 173"},
        )
    ]

    short_answer = generator._build_scenario_short_answer(primary, [])

    assert "Bộ luật Hình Sự, Điều 173" in short_answer
    assert "giao dịch vô hiệu" not in short_answer
    assert "thế chấp" not in short_answer


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
