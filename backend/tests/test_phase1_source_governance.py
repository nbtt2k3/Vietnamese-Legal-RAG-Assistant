from generation.base_generator import BaseLLMGenerator
from generation.rule_based_generator import RuleBasedLegalGenerator
from retrieval.models import EvidenceBundle, QueryIntent, RetrievalResult, RetrievedChunk


def _unverified_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        doc_id="doc-1",
        text="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
        metadata={
            "citation": "Bộ luật Dân sự, Điều 117",
            "loai_van_ban": "bo_luat",
            "source_verification_status": "local_checksum_only",
            "source_of_validity": "unverified_parsed_text",
            "validity_status": "chua_xac_dinh",
            "validity_confidence": "low",
        },
        scores={"final": 1.0},
    )


def test_llm_generator_adds_source_and_validity_governance_flags():
    generator = BaseLLMGenerator()
    mock_data = {
        "short_answer": "Test",
        "quy_dinh_phap_luat": [
            {
                "claim": "Giao dịch dân sự có hiệu lực khi đáp ứng điều kiện luật định.",
                "reasoning": "Evidence E1 nêu điều kiện có hiệu lực.",
                "evidence_ids": ["E1"],
            }
        ],
        "conflict_detected": False,
    }
    evidence = EvidenceBundle(core_authorities=[_unverified_chunk()])
    retrieval_result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})

    answer = generator._parse_llm_response(mock_data, "Test", retrieval_result, "test")

    assert answer.confidence["source_verification_complete"] is False
    assert answer.confidence["validity_verification_complete"] is False
    assert answer.confidence["human_review_required"] is True
    assert "unverified_source" in answer.confidence["human_review_reasons"]
    assert "unverified_validity" in answer.confidence["human_review_reasons"]
    assert any("tệp nội bộ" in item for item in answer.disclaimers)
    assert not any("local checksum" in item or "parse" in item for item in answer.disclaimers)
    assert any("hiệu lực" in item for item in answer.disclaimers)


def test_rule_based_generator_adds_source_and_validity_governance_flags():
    generator = RuleBasedLegalGenerator()
    chunk = _unverified_chunk()
    retrieval_result = RetrievalResult(
        query_intent=QueryIntent(
            raw_query="Điều 117 là gì?",
            normalized_query="Điều 117 là gì?",
            loai_yeu_cau="citation_lookup",
            citation_targets=["Điều 117"],
            source_priority=["bo_luat"],
        ),
        candidates=[chunk],
        evidence=EvidenceBundle(core_authorities=[chunk]),
        confidence={"level": "high"},
    )

    answer = generator.generate("Điều 117 là gì?", retrieval_result)

    assert answer.confidence["source_verification_complete"] is False
    assert answer.confidence["validity_verification_complete"] is False
    assert answer.confidence["human_review_required"] is True
    assert "unverified_source" in answer.confidence["human_review_reasons"]
    assert "unverified_validity" in answer.confidence["human_review_reasons"]
    assert any("tệp nội bộ" in item for item in answer.disclaimers)
    assert not any("local checksum" in item or "parse" in item for item in answer.disclaimers)
    assert any("hiệu lực" in item for item in answer.disclaimers)


def test_rule_based_generator_marks_scenario_answers_for_human_review():
    generator = RuleBasedLegalGenerator()
    chunk = _unverified_chunk()
    chunk.metadata["source_verification_status"] = "official_verified"
    chunk.metadata["source_of_validity"] = "csdl_quoc_gia_vbpl"
    chunk.metadata["validity_status"] = "dang_co_hieu_luc"
    chunk.metadata["validity_confidence"] = "high"
    retrieval_result = RetrievalResult(
        query_intent=QueryIntent(
            raw_query="Tôi đã ký hợp đồng nhưng bên kia vi phạm thì xử lý thế nào?",
            normalized_query="Tôi đã ký hợp đồng nhưng bên kia vi phạm thì xử lý thế nào?",
            loai_yeu_cau="scenario_application",
            source_priority=["bo_luat"],
            scenario_terms=["hợp đồng", "vi phạm"],
        ),
        candidates=[chunk],
        evidence=EvidenceBundle(core_authorities=[chunk]),
        confidence={"level": "medium"},
    )

    answer = generator.generate("scenario", retrieval_result)

    assert answer.confidence["human_review_required"] is True
    assert "fact_sensitive_legal_scenario" in answer.confidence["human_review_reasons"]
