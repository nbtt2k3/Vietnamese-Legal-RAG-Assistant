import json

from evaluation.dataset_loader import load_eval_dataset
from evaluation.evaluator import LegalRAGEvaluator
from evaluation.models import EvalCase
from evaluation.quality_gate import evaluate_quality_gate
from evaluation.reporting import report_to_markdown
from rag.generation.models import CitationRecord, LegalAnswer
from rag.retrieval.models import EvidenceBundle, QueryIntent, RetrievalResult, RetrievedChunk


def test_eval_dataset_v2_loads_extended_case_fields():
    dataset_name, cases = load_eval_dataset("evaluation/datasets/legal_rag_eval_v2.json")

    assert dataset_name == "legal_rag_eval_v2"
    assert len(cases) >= 20
    assert any(case.should_answer is False for case in cases)
    assert any(case.max_latency_seconds is not None for case in cases)
    assert any(case.min_grounding_coverage > 0 for case in cases)
    assert any("source_governance" in case.tags for case in cases)
    assert any(case.expected_disclaimer_terms for case in cases)


class FakePipeline:
    def __init__(self, answer: LegalAnswer, retrieval: RetrievalResult):
        self.answer = answer
        self.retrieval = retrieval

    def run(self, query: str):
        return self.answer, self.retrieval


def _retrieval_result(request_type: str = "citation_lookup") -> RetrievalResult:
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        doc_id="doc-1",
        text="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
        metadata={"citation": "Bộ luật Dân sự, Điều 117", "loai_van_ban": "bo_luat"},
        scores={"final": 10.0},
        sources=["metadata"],
    )
    return RetrievalResult(
        query_intent=QueryIntent(
            raw_query="Điều 117 là gì?",
            normalized_query="Điều 117 là gì?",
            loai_yeu_cau=request_type,
            source_priority=["bo_luat"],
        ),
        candidates=[chunk],
        evidence=EvidenceBundle(core_authorities=[chunk]),
        confidence={"level": "high"},
    )


def test_evaluator_reports_grounding_latency_and_guardrail_metrics(tmp_path):
    dataset = {
        "dataset_name": "unit_eval",
        "cases": [
            {
                "case_id": "grounded_case",
                "query": "Điều 117 là gì?",
                "expected_request_type": "citation_lookup",
                "expected_citations": ["Bộ luật Dân sự, Điều 117"],
                "expected_source_types": ["bo_luat"],
                "expected_answer_terms": ["điều kiện", "giao dịch"],
                "min_confidence_level": "medium",
                "min_grounding_coverage": 0.8,
                "max_latency_seconds": 5.0,
            }
        ],
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    answer = LegalAnswer(
        query="Điều 117 là gì?",
        short_answer="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
        citations=[
            CitationRecord(
                citation="Bộ luật Dân sự, Điều 117",
                snippet="Điều kiện có hiệu lực của giao dịch dân sự.",
                source_type="bo_luat",
                evidence_id="E1",
            )
        ],
        confidence={
            "level": "high",
            "grounding_coverage": 1.0,
            "invalid_evidence_used": False,
            "weakly_supported_claims": False,
            "claims_without_evidence": False,
        },
        disclaimers=["Cần đối chiếu hồ sơ thực tế."],
        answer_method="unit",
    )
    evaluator = LegalRAGEvaluator(
        dataset_path=str(dataset_path),
        use_llm=False,
        use_llm_judge=False,
        pipeline=FakePipeline(answer, _retrieval_result()),
    )

    report = evaluator.run()
    case = report.cases[0]

    assert case.metrics["grounding_threshold_met"] == 1.0
    assert case.metrics["invalid_evidence_free"] == 1.0
    assert case.metrics["weak_support_free"] == 1.0
    assert case.metrics["claims_have_evidence"] == 1.0
    assert case.metrics["latency_budget_met"] == 1.0
    assert case.observed["candidate_count"] == 1
    assert "avg_latency_seconds" in report.aggregate_metrics

    markdown = report_to_markdown(report)
    assert "Observed" in markdown
    assert "grounding_coverage" in markdown
    assert "retrieval_top_citations" in markdown


def test_evaluator_scores_expected_abstention(tmp_path):
    dataset = {
        "dataset_name": "unit_abstention",
        "cases": [
            {
                "case_id": "out_of_scope",
                "query": "Thời tiết hôm nay thế nào?",
                "expected_request_type": "out_of_scope",
                "expected_answer_terms": ["ngoài phạm vi"],
                "min_confidence_level": "low",
                "should_answer": False,
                "max_latency_seconds": 5.0,
            }
        ],
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    answer = LegalAnswer(
        query="Thời tiết hôm nay thế nào?",
        short_answer="Câu hỏi nằm ngoài phạm vi pháp luật Việt Nam.",
        citations=[],
        confidence={"level": "low", "grounding_coverage": 0.0},
        disclaimers=["Ngoài phạm vi hệ thống."],
        answer_method="guardrail",
    )
    evaluator = LegalRAGEvaluator(
        dataset_path=str(dataset_path),
        use_llm=False,
        use_llm_judge=False,
        pipeline=FakePipeline(answer, _retrieval_result(request_type="out_of_scope")),
    )

    report = evaluator.run()
    case = report.cases[0]

    assert case.metrics["abstention_correctness"] == 1.0
    assert case.observed["abstained"] is True
    assert case.passed is True


def test_quality_gate_reports_failures_for_low_metrics(tmp_path):
    dataset = {
        "dataset_name": "unit_gate",
        "cases": [
            {
                "case_id": "weak_case",
                "query": "Điều 117 là gì?",
                "expected_request_type": "citation_lookup",
                "expected_citations": ["Bộ luật Dân sự, Điều 117"],
                "expected_source_types": ["bo_luat"],
                "expected_answer_terms": ["điều kiện"],
                "min_confidence_level": "medium",
            }
        ],
    }
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")

    answer = LegalAnswer(
        query="Điều 117 là gì?",
        short_answer="Không rõ.",
        citations=[],
        confidence={"level": "low", "grounding_coverage": 0.0},
        disclaimers=[],
        answer_method="unit",
    )
    evaluator = LegalRAGEvaluator(
        dataset_path=str(dataset_path),
        use_llm=False,
        use_llm_judge=False,
        pipeline=FakePipeline(answer, _retrieval_result()),
    )

    report = evaluator.run()
    gate = evaluate_quality_gate(report, thresholds={"pass_rate": 1.0, "generation_citation_recall": 1.0})

    assert gate.passed is False
    assert any("generation_citation_recall" in failure for failure in gate.failures)
