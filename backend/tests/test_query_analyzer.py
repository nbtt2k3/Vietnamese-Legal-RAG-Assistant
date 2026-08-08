import pytest
from rag.retrieval.evidence_builder import EvidenceBuilder
from rag.retrieval.models import RetrievedChunk
from rag.retrieval.query_analyzer import QueryAnalyzer, QueryIntent

def test_query_analyzer_basic_extraction():
    analyzer = QueryAnalyzer()
    
    # We use force_deterministic=True with a mocked LLM response if needed, 
    # but the rule-based fallback can be tested directly if we pass force_deterministic
    # Wait, force_deterministic uses the LLM if not specified? 
    # Let's test the fallback path for determinism
    intent = analyzer.analyze("hành vi trộm cắp tài sản bị xử phạt như thế nào", force_deterministic=True)
    
    assert intent.loai_yeu_cau == "scenario_application"
    assert intent.citation_targets
    # Actually, the fallback extracts words > 2 chars. 
    # "trộm cắp" might be split to "trộm", "cắp", but it does extract keywords.

def test_query_analyzer_history_injection():
    analyzer = QueryAnalyzer()
    
    from app.api.v1.schemas.chat import Message
    history = [
        Message(role="user", content="Tôi muốn hỏi về tội giết người"),
        Message(role="ai", content="Tội giết người được quy định tại Bộ luật Hình sự."),
    ]
    
    # Even in fallback, we can check if it runs without crashing
    intent = analyzer.analyze("Người này bị phạt bao nhiêu năm tù?", force_deterministic=True, history=history)
    assert intent.loai_yeu_cau == "general_legal_question"

def test_query_analyzer_out_of_scope():
    analyzer = QueryAnalyzer()
    
    intent = analyzer.analyze("Thời tiết hôm nay thế nào?", force_deterministic=True)
    assert intent.loai_yeu_cau == "out_of_scope"


def test_query_analyzer_deterministic_keeps_scenario_terms():
    analyzer = QueryAnalyzer()

    intent = analyzer.analyze(
        "Nếu bên mua chưa thanh toán mà tài sản đang thế chấp ngân hàng thì hợp đồng có hiệu lực không?",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "scenario_application"
    assert "thanh toán" in intent.scenario_terms
    assert "ngân hàng" in intent.scenario_terms
    assert "thế chấp" in intent.query_variants


def test_query_analyzer_llm_fallback_keeps_rule_scenario_terms(monkeypatch):
    analyzer = QueryAnalyzer()
    monkeypatch.setattr(analyzer, "_call_llm", lambda prompt: (_ for _ in ()).throw(RuntimeError("boom")))

    intent = analyzer.analyze(
        "Trong trường hợp bên mua chưa thanh toán tiền cho bên bán và ngân hàng đang giữ giấy chứng nhận, hợp đồng mua bán đất được xử lý thế nào?",
        force_deterministic=False,
    )

    assert "thanh toán" in intent.scenario_terms
    assert "ngân hàng" in intent.scenario_terms
    assert "thanh toán" in intent.query_variants


def test_query_analyzer_llm_fallback_keeps_rule_keywords(monkeypatch):
    analyzer = QueryAnalyzer()
    monkeypatch.setattr(analyzer, "_call_llm", lambda prompt: (_ for _ in ()).throw(RuntimeError("boom")))

    intent = analyzer.analyze(
        "Bộ luật Dân sự 2015 quy định gì?",
        force_deterministic=False,
    )

    assert intent.keywords
    assert "2015" in intent.keywords
    assert "Bộ luật Dân sự 2015 quy định gì?" in intent.query_variants


def test_evidence_builder_excludes_case_law_for_validity_question():
    builder = EvidenceBuilder()
    intent = QueryIntent(
        raw_query="Điều kiện có hiệu lực của hợp đồng là gì?",
        normalized_query="Điều kiện có hiệu lực của hợp đồng là gì?",
        loai_yeu_cau="validity_question",
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    ranked = [
        RetrievedChunk(
            chunk_id="case-1",
            doc_id="case-doc",
            text="Án lệ về hiệu lực hợp đồng",
            metadata={"document_role": "case_law", "loai_van_ban": "an_le"},
            scores={"final": 10.0},
        ),
        RetrievedChunk(
            chunk_id="law-1",
            doc_id="law-doc",
            text="Quy định về điều kiện có hiệu lực của giao dịch dân sự",
            metadata={"loai_van_ban": "bo_luat", "legal_role": "rule"},
            scores={"final": 1.0},
        ),
    ]

    evidence = builder.build(intent, ranked)

    assert evidence.case_law_support == []
    assert evidence.core_authorities[0].doc_id == "law-doc"


def test_evidence_builder_keeps_appendix_out_of_core_unless_requested():
    builder = EvidenceBuilder()
    intent = QueryIntent(
        raw_query="Điều kiện có hiệu lực của hợp đồng là gì?",
        normalized_query="Điều kiện có hiệu lực của hợp đồng là gì?",
        loai_yeu_cau="general_legal_question",
        source_priority=["bo_luat", "nghi_quyet", "nghi_dinh", "an_le"],
    )
    ranked = [
        RetrievedChunk(
            chunk_id="appendix-1",
            doc_id="appendix-doc",
            text="Mẫu biểu kèm theo văn bản",
            metadata={"loai_van_ban": "nghi_dinh", "legal_unit_type": "phu_luc", "legal_role": "appendix_form"},
            scores={"final": 10.0},
        ),
        RetrievedChunk(
            chunk_id="law-1",
            doc_id="law-doc",
            text="Quy định chung về hợp đồng",
            metadata={"loai_van_ban": "bo_luat", "legal_role": "rule"},
            scores={"final": 1.0},
        ),
    ]

    evidence = builder.build(intent, ranked)

    assert [item.doc_id for item in evidence.core_authorities] == ["law-doc"]
    assert all(item.doc_id != "appendix-doc" for item in evidence.supporting_authorities)


def test_query_analyzer_marks_insufficient_contract_facts_without_promoting_case_law():
    intent = QueryAnalyzer().analyze(
        "Hợp đồng của tôi có vô hiệu không nếu tôi chỉ nói là bên kia không giữ lời?",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "scenario_application"
    assert intent.insufficient_facts is True
    assert "Điều 117" in intent.citation_targets
    assert set(intent.missing_fact_hints) >= {"chủ thể", "tự nguyện", "mục đích", "nội dung"}


def test_query_analyzer_routes_unaccented_third_party_security_to_article_319_clause_2():
    intent = QueryAnalyzer().analyze(
        "Neu tai san the chap chua dang ky thi co doi khang voi nguoi thu ba khong?",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "scenario_application"
    assert "Khoản 2 Điều 319" in intent.citation_targets
    assert "đối kháng" in intent.scenario_terms


def test_query_analyzer_routes_high_signal_new_failure_clusters():
    analyzer = QueryAnalyzer()

    criminal_age = analyzer.analyze(
        "Người từ đủ 14 tuổi đến dưới 16 tuổi phải chịu trách nhiệm hình sự về những tội gì?",
        force_deterministic=True,
    )
    assert criminal_age.loai_yeu_cau == "validity_question"
    assert criminal_age.citation_targets == ["Bộ luật Hình sự, Điều 12"]

    decree_registration = analyzer.analyze(
        "Những trường hợp nào phải đăng ký biện pháp bảo đảm?",
        force_deterministic=True,
    )
    assert decree_registration.loai_yeu_cau == "citation_lookup"
    assert decree_registration.citation_targets == ["Nghị định 99/2022/NĐ-CP, Điều 4"]

    standard_contract = analyzer.analyze(
        "Điều khoản mẫu trong hợp đồng theo mẫu có ràng buộc người giao kết không?",
        force_deterministic=True,
    )
    assert standard_contract.loai_yeu_cau == "validity_question"
    assert "Điều 405" in standard_contract.citation_targets[0]


def test_query_analyzer_marks_missing_facts_after_topic_routing():
    intent = QueryAnalyzer().analyze(
        "Tôi chưa rõ thời điểm, chủ thể, giấy tờ và hành vi cụ thể của người từ đủ 14 tuổi đến dưới 16 tuổi phải chịu trách nhiệm hình sự. Có thể kết luận ngay không?",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "scenario_application"
    assert intent.insufficient_facts is True
    assert "Bộ luật Hình sự, Điều 12" in intent.citation_targets


def test_query_analyzer_routes_unsupported_domains_to_guardrail():
    intent = QueryAnalyzer().analyze(
        "Người lao động bị sa thải trái pháp luật được nhận lại việc và bồi thường thế nào?",
        force_deterministic=True,
    )

    assert intent.loai_yeu_cau == "out_of_scope"
