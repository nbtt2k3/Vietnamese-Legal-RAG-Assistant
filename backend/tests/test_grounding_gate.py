from rag.generation.models import CitationRecord, LegalAnswer
from rag.generation.pipeline import GenerationPipeline


def test_grounding_gate_abstains_when_claim_has_no_evidence():
    answer = LegalAnswer(
        query="Hợp đồng có vô hiệu không?",
        short_answer="Hợp đồng chắc chắn vô hiệu.",
        confidence={"level": "low", "claims_without_evidence": True},
    )

    GenerationPipeline._apply_grounding_gate(answer)

    assert answer.confidence["grounding_gate_triggered"] is True
    assert answer.confidence["level"] == "low"
    assert answer.sections[0].title == "Chưa đủ căn cứ pháp lý"
    assert "Chưa đủ căn cứ pháp lý" in answer.short_answer
    assert answer.confidence["human_review_required"] is True


def test_grounding_gate_preserves_answer_with_grounded_citation():
    answer = LegalAnswer(
        query="Điều kiện có hiệu lực của giao dịch?",
        short_answer="Giao dịch có hiệu lực khi đáp ứng điều kiện luật định.",
        citations=[
            CitationRecord(
                citation="Bộ luật Dân sự 2015, Điều 117",
                snippet="Giao dịch dân sự có hiệu lực khi có đủ các điều kiện...",
                source_type="bo_luat",
            )
        ],
        confidence={"level": "high", "short_answer_grounded": True},
    )

    GenerationPipeline._apply_grounding_gate(answer)

    assert answer.short_answer.startswith("Giao dịch có hiệu lực")
    assert "grounding_gate_triggered" not in answer.confidence
