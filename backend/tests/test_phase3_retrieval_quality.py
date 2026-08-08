from rag.retrieval.models import QueryIntent, RetrievalResult, RetrievedChunk
from rag.retrieval.evidence_builder import EvidenceBuilder
from rag.retrieval.pipeline import RetrievalPipeline
from rag.retrieval.constraints import exact_constraints, payload_matches_exact_constraints
from rag.retrieval.query_analyzer import QueryAnalyzer
from rag.retrieval.document_resolver import resolve_document_ids, source_types_from_text
from rag.retrieval.retrievers.lexical_retriever import LexicalRetriever
from rag.retrieval.retrievers.metadata_retriever import MetadataRetriever
from rag.retrieval.text_utils import contains_normalized, tokenize_for_bm25
from rag.generation.rule_based_generator import RuleBasedLegalGenerator
from evaluation.utils import citation_matches


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


def test_target_constraints_do_not_inherit_another_document_id():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="tai nan giao thong",
        normalized_query="tai nan giao thong",
        loai_yeu_cau="scenario_application",
        citation_targets=[
            "Bộ luật Hình sự, Điều 260",
            "Bộ luật Dân sự, Điều 590",
        ],
    )

    criminal = pipeline._target_constraints(intent, intent.citation_targets[0])
    civil = pipeline._target_constraints(intent, intent.citation_targets[1])

    assert "bo_luat_91_2015_QH13" not in criminal["doc_ids"]
    assert "bo_luat_91_2015_QH13" in civil["doc_ids"]


def test_explicit_authority_injection_deduplicates_parent_payloads():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="dang ky bien phap bao dam",
        normalized_query="dang ky bien phap bao dam",
        loai_yeu_cau="validity_question",
        citation_targets=["Bộ luật Dân sự, Điều 319, Khoản 2"],
    )

    class RepositoryStub:
        def all_payloads(self):
            return [
                {
                    "chunk_id": "civil-319-parent",
                    "doc_id": "bo_luat_91_2015_QH13",
                    "text": "Điều 319. Hiệu lực đối kháng với người thứ ba.",
                    "citation": "Bộ luật Dân sự, Điều 319",
                    "dieu_number": "319",
                    "node_type": "dieu",
                    "loai_van_ban": "bo_luat",
                },
                {
                    "chunk_id": "civil-319-k2",
                    "doc_id": "bo_luat_91_2015_QH13",
                    "text": "Khoản 2. Hiệu lực đối kháng phát sinh từ thời điểm đăng ký.",
                    "citation": "Bộ luật Dân sự, Điều 319, Khoản 2",
                    "dieu_number": "319",
                    "khoan_number": "2",
                    "node_type": "khoan",
                    "loai_van_ban": "bo_luat",
                },
            ]

    merged = {}
    pipeline._inject_explicit_authority_candidates(RepositoryStub(), intent, merged, {})

    assert list(merged) == ["civil-319-parent", "civil-319-k2"]


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

def test_exact_constraints_require_the_requested_clause():
    intent = QueryAnalyzer().analyze(
        "Theo Kho\u1ea3n 1 \u0110i\u1ec1u 117 B\u1ed9 lu\u1eadt D\u00e2n s\u1ef1, giao d\u1ecbch c\u00f3 hi\u1ec7u l\u1ef1c kh\u00f4ng?",
        force_deterministic=True,
    )
    constraints = exact_constraints(intent)
    base = {
        "doc_id": "bo_luat_91_2015_QH13",
        "loai_van_ban": "bo_luat",
        "dieu_number": "117",
        "citation": "B\u1ed9 lu\u1eadt D\u00e2n s\u1ef1, \u0110i\u1ec1u 117",
    }
    assert payload_matches_exact_constraints({**base, "khoan_number": "1"}, constraints)
    assert not payload_matches_exact_constraints({**base, "khoan_number": "2"}, constraints)

def test_rule_analyzer_routes_unseen_article_query_to_citation_lookup():
    intent = QueryAnalyzer().analyze(
        "\u0110i\u1ec1u 352 B\u1ed9 lu\u1eadt H\u00ecnh s\u1ef1 quy \u0111\u1ecbnh g\u00ec?",
        force_deterministic=True,
    )
    assert intent.loai_yeu_cau == "citation_lookup"
    assert "352" in intent.citation_targets[0]

def test_rule_analyzer_routes_natural_language_paraphrases():
    analyzer = QueryAnalyzer()
    assert analyzer.analyze(
        "Khi nào hợp đồng phải lập bằng văn bản hoặc phải công chứng, chứng thực?",
        force_deterministic=True,
    ).loai_yeu_cau == "validity_question"
    assert analyzer.analyze(
        "Người làm hư hỏng tài sản của người khác phải bồi thường những khoản nào?",
        force_deterministic=True,
    ).loai_yeu_cau == "scenario_application"
    assert analyzer.analyze(
        "Quyền sử dụng đất và tài sản gắn liền với đất có thể dùng để bảo đảm nghĩa vụ như thế nào?",
        force_deterministic=True,
    ).loai_yeu_cau == "citation_lookup"

def test_scenario_promotes_existing_case_law_candidate_into_top_eight():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryAnalyzer().analyze("Tình huống thế chấp tài sản", force_deterministic=True)
    ranked = [
        RetrievedChunk(str(i), f"doc-{i}", "text", {"loai_van_ban": "bo_luat"}, {"final": 10.0 - i})
        for i in range(8)
    ]
    ranked.append(
        RetrievedChunk(
            "case",
            "case-doc",
            "case text",
            {"loai_van_ban": "an_le", "document_role": "case_law"},
            {"final": 2.0},
        )
    )
    result = pipeline._promote_case_law_coverage(intent, ranked)
    assert result[0].chunk_id == "case"


def test_insufficient_scenario_does_not_promote_case_law():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryAnalyzer().analyze(
        "Hợp đồng của tôi có vô hiệu không nếu tôi chỉ nói là bên kia không giữ lời?",
        force_deterministic=True,
    )
    ranked = [
        RetrievedChunk(str(i), f"doc-{i}", "text", {"loai_van_ban": "bo_luat"}, {"final": 10.0 - i})
        for i in range(8)
    ]
    ranked.append(
        RetrievedChunk(
            "case",
            "case-doc",
            "case text",
            {"loai_van_ban": "an_le", "document_role": "case_law"},
            {"final": 2.0},
        )
    )
    result = pipeline._promote_case_law_coverage(intent, ranked)
    assert result[0].chunk_id == "0"


def test_insufficient_facts_keeps_retrieved_case_law_as_citation():
    intent = QueryIntent(
        raw_query="Tình huống thế chấp nhưng chưa đủ tình tiết",
        normalized_query="tinh huong the chap nhung chua du tinh tiet",
        loai_yeu_cau="scenario_application",
        insufficient_facts=True,
        missing_fact_hints=["thời điểm", "chủ thể"],
        scenario_terms=["thế chấp"],
    )
    case_law = RetrievedChunk(
        chunk_id="case-43",
        doc_id="an_le_43_2021_AL",
        text="Án lệ số 43/2021/AL về hợp đồng thế chấp.",
        metadata={
            "citation": "Án lệ số 43/2021/AL",
            "loai_van_ban": "an_le",
            "document_role": "case_law",
            "legal_domain_tags": ["bao_dam", "hop_dong"],
        },
        scores={"final": 1.0},
    )
    result = RetrievalResult(
        query_intent=intent,
        candidates=[case_law],
        confidence={"level": "low"},
    )

    answer = RuleBasedLegalGenerator().generate(intent.raw_query, result)

    assert answer.citations
    assert any("43/2021/AL" in item.citation for item in answer.citations)
    assert "43/2021/AL" in answer.short_answer


def test_exact_third_party_scenario_anchor_filters_to_civil_code_clause():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryAnalyzer().analyze(
        "Neu tai san the chap chua dang ky thi co doi khang voi nguoi thu ba khong?",
        force_deterministic=True,
    )
    debug = {}
    ranked = {
        "civil-319-2": RetrievedChunk(
            "civil-319-2", "bo_luat_91_2015_QH13", "text",
            {"loai_van_ban": "bo_luat", "dieu_number": "319", "khoan_number": "2", "citation": "Bộ luật Dân sự, Điều 319, Khoản 2"},
            {"metadata": 10.0},
        ),
        "criminal-319-2": RetrievedChunk(
            "criminal-319-2", "bo_luat_100_2015_QH13", "text",
            {"loai_van_ban": "bo_luat", "dieu_number": "319", "khoan_number": "2", "citation": "Bộ luật Hình sự, Điều 319, Khoản 2"},
            {"metadata": 10.0},
        ),
    }

    filtered = pipeline._filter_exact_lookup_candidates(intent, ranked, debug)

    assert list(filtered) == ["civil-319-2"]


def test_case_law_question_with_explicit_target_still_promotes_case_law():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="Án lệ số 43/2021/AL",
        normalized_query="Án lệ số 43/2021/AL",
        loai_yeu_cau="case_law_question",
        citation_targets=["Án lệ số 43/2021/AL"],
    )
    ranked = [
        RetrievedChunk(str(i), f"doc-{i}", "text", {"loai_van_ban": "bo_luat"}, {"final": 10.0 - i})
        for i in range(8)
    ]
    ranked.append(
        RetrievedChunk(
            "case",
            "case-doc",
            "case text",
            {"loai_van_ban": "an_le", "document_role": "case_law"},
            {"final": 2.0},
        )
    )
    result = pipeline._promote_case_law_coverage(intent, ranked)
    assert result[0].chunk_id == "case"


def test_exact_case_law_target_filters_semantically_similar_case_law_noise():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="Án lệ số 43/2021/AL liên quan gì đến thế chấp?",
        normalized_query="Án lệ số 43/2021/AL liên quan gì đến thế chấp?",
        loai_yeu_cau="case_law_question",
        citation_targets=["Án lệ số 43/2021/AL"],
    )
    merged = {
        "case-43": RetrievedChunk(
            "case-43", "an_le_so_43_2021_AL", "case text",
            {"loai_van_ban": "an_le", "document_role": "case_law", "citation": "Án lệ số 43/2021/AL"},
        ),
        "case-50": RetrievedChunk(
            "case-50", "an_le_so_50_2021_AL", "similar case text",
            {"loai_van_ban": "an_le", "document_role": "case_law", "citation": "Án lệ số 50/2021/AL"},
        ),
    }

    filtered = pipeline._filter_exact_case_law_candidates(intent, merged, {})

    assert list(filtered) == ["case-43"]


def test_citation_match_ignores_inserted_document_title():
    observed = "Nghị định 21/2021/NĐ-CP - NGHỊ ĐỊNH quy định thi hành Bộ luật Dân sự, Điều 7, Khoản 3"
    expected = "Nghị định 21/2021/NĐ-CP, Điều 7"

    assert citation_matches(observed, expected)


def test_exact_article_target_prefers_article_parent_over_child_clause():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="Người làm hư hỏng tài sản phải bồi thường những khoản nào?",
        normalized_query="Người làm hư hỏng tài sản phải bồi thường những khoản nào?",
        loai_yeu_cau="scenario_application",
        citation_targets=["Bộ luật Dân sự, Điều 589"],
        source_priority=["bo_luat"],
    )
    ranked = [
        RetrievedChunk(
            "child", "bo_luat_91_2015_QH13", "Khoản 1",
            {"loai_van_ban": "bo_luat", "dieu_number": "589", "khoan_number": "1", "citation": "Bộ luật Dân sự, Điều 589, Khoản 1"},
            {"final": 10.0},
        ),
        RetrievedChunk(
            "parent", "bo_luat_91_2015_QH13", "Điều 589",
            {"loai_van_ban": "bo_luat", "dieu_number": "589", "node_type": "dieu", "citation": "Bộ luật Dân sự, Điều 589"},
            {"final": 9.0},
        ),
    ]

    result = pipeline._ensure_exact_authority_coverage(intent, ranked)

    assert [item.chunk_id for item in result[:2]] == ["parent", "child"]


def test_exact_document_identity_excludes_same_number_article_from_other_code():
    pipeline = RetrievalPipeline.__new__(RetrievalPipeline)
    intent = QueryIntent(
        raw_query="Người từ đủ 14 tuổi đến dưới 16 tuổi chịu trách nhiệm hình sự",
        normalized_query="Người từ đủ 14 tuổi đến dưới 16 tuổi chịu trách nhiệm hình sự",
        loai_yeu_cau="validity_question",
        citation_targets=["Bộ luật Hình sự, Điều 12"],
    )
    merged = {
        "criminal-12": RetrievedChunk(
            "criminal-12",
            "bo_luat_100_2015_QH13",
            "text",
            {
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Hình sự, Điều 12",
                "dieu_number": "12",
            },
        ),
        "civil-12": RetrievedChunk(
            "civil-12",
            "bo_luat_91_2015_QH13",
            "text",
            {
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Dân sự, Điều 12",
                "dieu_number": "12",
            },
        ),
        "criminal-122": RetrievedChunk(
            "criminal-122",
            "bo_luat_100_2015_QH13",
            "text",
            {
                "loai_van_ban": "bo_luat",
                "citation": "Bộ luật Hình sự, Điều 122",
                "dieu_number": "122",
            },
        ),
    }

    filtered = pipeline._filter_exact_lookup_candidates(intent, merged, {})

    assert list(filtered) == ["criminal-12"]
