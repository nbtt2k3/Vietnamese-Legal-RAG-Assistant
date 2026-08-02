import pytest
from rag.generation.base_generator import BaseLLMGenerator
from rag.retrieval.models import RetrievalResult, EvidenceBundle, RetrievedChunk

def test_base_llm_generator_parsing():
    generator = BaseLLMGenerator()
    
    # Mock data from LLM
    mock_data = {
        "short_answer": "Giao dịch dân sự có hiệu lực khi đáp ứng điều kiện luật định.",
        "quy_dinh_phap_luat": [
            {
                "claim": "Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
                "reasoning": "Evidence E1 nêu trực tiếp điều kiện về chủ thể và năng lực pháp luật dân sự.",
                "evidence_ids": ["E1"]
            }
        ],
        "conflict_detected": False,
        "uncertainty": ""
    }
    
    # Mock retrieval result
    evidence = EvidenceBundle(
        core_authorities=[
            RetrievedChunk(
                chunk_id="1",
                doc_id="d1",
                text="Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            )
        ]
    )
    retrieval_result = RetrievalResult(
        query_intent=None, # mock
        evidence=evidence,
        confidence={"level": "high"}
    )
    
    answer = generator._parse_llm_response(
        data=mock_data,
        query="Test query",
        retrieval_result=retrieval_result,
        method_name="test"
    )
    
    assert answer.short_answer == "Giao dịch dân sự có hiệu lực khi đáp ứng điều kiện luật định."
    assert len(answer.sections) == 1
    assert answer.sections[0].title == "Quy định pháp luật"
    assert answer.sections[0].claims[0].evidence_ids == ["E1"]
    assert answer.confidence["level"] == "high"
    assert answer.confidence["grounded_claim_count"] == 1
    assert answer.confidence["grounding_coverage"] == 1.0

def test_hallucination_penalty():
    generator = BaseLLMGenerator()
    
    # AI generates evidence_id E2, but we only have 1 chunk (E1)
    mock_data = {
        "short_answer": "Test",
        "quy_dinh_phap_luat": [
            {
                "claim": "Test claim",
                "reasoning": "Test reasoning",
                "evidence_ids": ["E2"] # Hallucination!
            }
        ],
        "conflict_detected": False,
    }
    
    evidence = EvidenceBundle(
        core_authorities=[RetrievedChunk(chunk_id="1", doc_id="d1", text="Test")]
    )
    retrieval_result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})
    
    answer = generator._parse_llm_response(mock_data, "Test", retrieval_result, "test")
    
    # Because E2 was hallucinative, the confidence should drop to low
    assert answer.confidence["invalid_evidence_used"] is True
    assert answer.confidence["level"] == "low"
    assert answer.confidence["human_review_required"] is True
    assert "invalid_evidence_used" in answer.confidence["human_review_reasons"]
    assert any("căn cứ không tồn tại" in d for d in answer.disclaimers)
    assert not any("Hallucination" in d for d in answer.disclaimers)


def test_claim_without_evidence_is_penalized():
    generator = BaseLLMGenerator()

    mock_data = {
        "short_answer": "Test",
        "quy_dinh_phap_luat": [
            {
                "claim": "Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
                "reasoning": "Không nêu căn cứ.",
                "evidence_ids": [],
            }
        ],
        "conflict_detected": False,
    }

    evidence = EvidenceBundle(
        core_authorities=[
            RetrievedChunk(
                chunk_id="1",
                doc_id="d1",
                text="Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            )
        ]
    )
    retrieval_result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})

    answer = generator._parse_llm_response(mock_data, "Test", retrieval_result, "test")

    assert answer.confidence["claims_without_evidence"] is True
    assert answer.confidence["level"] == "low"
    assert answer.confidence["human_review_required"] is True
    assert "claims_without_evidence" in answer.confidence["human_review_reasons"]
    assert any("không có căn cứ hợp lệ" in d for d in answer.disclaimers)
    assert not any(" evidence " in f" {d} " for d in answer.disclaimers)


def test_short_answer_grounding_is_recorded_when_supported():
    generator = BaseLLMGenerator()
    evidence = EvidenceBundle(
        core_authorities=[
            RetrievedChunk(
                chunk_id="1",
                doc_id="d1",
                text="Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            )
        ]
    )
    result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})

    answer = generator._parse_llm_response(
        {
            "short_answer": "Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            "conflict_detected": False,
        },
        "Test",
        result,
        "test",
    )

    assert answer.confidence["short_answer_grounded"] is True
    assert answer.confidence["short_answer_not_grounded"] is False
    assert "short_answer_not_grounded" not in answer.confidence["human_review_reasons"]


def test_ungrounded_short_answer_is_penalized():
    generator = BaseLLMGenerator()
    evidence = EvidenceBundle(
        core_authorities=[
            RetrievedChunk(
                chunk_id="1",
                doc_id="d1",
                text="Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            )
        ]
    )
    result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})

    answer = generator._parse_llm_response(
        {
            "short_answer": "Người mua chắc chắn được hủy hợp đồng và yêu cầu bồi thường.",
            "conflict_detected": False,
        },
        "Test",
        result,
        "test",
    )

    assert answer.confidence["short_answer_grounded"] is False
    assert answer.confidence["short_answer_not_grounded"] is True
    assert answer.confidence["level"] == "low"
    assert answer.confidence["human_review_required"] is True
    assert "short_answer_not_grounded" in answer.confidence["human_review_reasons"]
    assert any("tóm tắt" in disclaimer for disclaimer in answer.disclaimers)


def test_weakly_supported_claim_is_penalized_even_with_valid_evidence_id():
    generator = BaseLLMGenerator()

    mock_data = {
        "short_answer": "Test",
        "quy_dinh_phap_luat": [
            {
                "claim": "Bên vay phải trả lãi suất vượt trần trong mọi trường hợp.",
                "reasoning": "Kết luận này dựa trên thỏa thuận lãi suất giữa các bên.",
                "evidence_ids": ["E1"],
            }
        ],
        "conflict_detected": False,
    }

    evidence = EvidenceBundle(
        core_authorities=[
            RetrievedChunk(
                chunk_id="1",
                doc_id="d1",
                text="Giao dịch dân sự có hiệu lực khi chủ thể có năng lực pháp luật dân sự.",
            )
        ]
    )
    retrieval_result = RetrievalResult(query_intent=None, evidence=evidence, confidence={"level": "high"})

    answer = generator._parse_llm_response(mock_data, "Test", retrieval_result, "test")

    assert answer.confidence["weakly_supported_claims"] is True
    assert answer.confidence["level"] == "low"
    assert answer.confidence["human_review_required"] is True
    assert "weakly_supported_claims" in answer.confidence["human_review_reasons"]
    assert any("mức khớp nội dung" in d for d in answer.disclaimers)
    assert not any(" evidence " in f" {d} " for d in answer.disclaimers)
