import json

from evaluation.evaluator import LegalRAGEvaluator
from evaluation.llm_judge import LLMJudge
from generation.models import CitationRecord, LegalAnswer
from retrieval.models import EvidenceBundle, QueryIntent, RetrievalResult, RetrievedChunk


class FakeJudgeClient:
    def __init__(self, payload):
        self.payload = payload

    def chat(self, **kwargs):
        return {"message": {"content": json.dumps(self.payload)}}


class FailingJudgeClient:
    def chat(self, **kwargs):
        raise RuntimeError("judge unavailable")


class FakeJudge:
    def __init__(self):
        self.last_reasons = {
            "answer_relevance": "direct",
            "faithfulness": "grounded",
            "context_precision": "useful",
        }

    def evaluate_answer_relevance(self, query: str, answer: str) -> float:
        return 0.9

    def evaluate_faithfulness(self, answer: str, context: str) -> float:
        return 0.8

    def evaluate_context_precision(self, query: str, context: str) -> float:
        return 0.7


class FakePipeline:
    def run(self, query: str):
        chunk = RetrievedChunk(
            chunk_id="chunk-1",
            doc_id="doc-1",
            text="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
            metadata={"citation": "Bộ luật Dân sự, Điều 117", "loai_van_ban": "bo_luat"},
            scores={"final": 10.0},
            sources=["metadata"],
        )
        retrieval = RetrievalResult(
            query_intent=QueryIntent(
                raw_query=query,
                normalized_query=query,
                loai_yeu_cau="citation_lookup",
                source_priority=["bo_luat"],
            ),
            candidates=[chunk],
            evidence=EvidenceBundle(core_authorities=[chunk]),
            confidence={"level": "high"},
        )
        answer = LegalAnswer(
            query=query,
            short_answer="Điều 117 quy định điều kiện có hiệu lực của giao dịch dân sự.",
            citations=[
                CitationRecord(
                    citation="Bộ luật Dân sự, Điều 117",
                    snippet="Điều kiện có hiệu lực của giao dịch dân sự.",
                    source_type="bo_luat",
                    evidence_id="E1",
                )
            ],
            confidence={"level": "high", "grounding_coverage": 1.0},
            answer_method="unit",
        )
        return answer, retrieval


def _dataset(tmp_path):
    payload = {
        "dataset_name": "phase7_eval",
        "cases": [
            {
                "case_id": "judge_case",
                "query": "Điều 117 là gì?",
                "expected_request_type": "citation_lookup",
                "expected_citations": ["Bộ luật Dân sự, Điều 117"],
                "expected_source_types": ["bo_luat"],
                "expected_answer_terms": ["điều kiện", "giao dịch"],
                "min_confidence_level": "medium",
            }
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_llm_judge_clamps_score_and_stores_reason():
    judge = LLMJudge(client=FakeJudgeClient({"score": 1.4, "reason": "too high"}), timeout_seconds=1)

    score = judge.evaluate_answer_relevance("q", "a")

    assert score == 1.0
    assert judge.last_reasons["answer_relevance"] == "too high"


def test_llm_judge_returns_safe_zero_when_unavailable():
    judge = LLMJudge(client=FailingJudgeClient(), timeout_seconds=1, max_attempts=1)

    score = judge.evaluate_faithfulness("answer", "context")

    assert score == 0.0
    assert "unavailable" in judge.last_reasons["faithfulness"]


def test_evaluator_records_llm_judge_metrics_and_reasons(tmp_path):
    evaluator = LegalRAGEvaluator(
        dataset_path=_dataset(tmp_path),
        use_llm=False,
        use_llm_judge=True,
        pipeline=FakePipeline(),
        llm_judge=FakeJudge(),
    )

    report = evaluator.run()
    case = report.cases[0]

    assert case.metrics["answer_relevance"] == 0.9
    assert case.metrics["faithfulness"] == 0.8
    assert case.metrics["context_precision"] == 0.7
    assert case.observed["llm_judge_reasons"]["faithfulness"] == "grounded"


def test_evaluator_uses_deterministic_mode_by_default(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "llm_judge_enabled", False)
    evaluator = LegalRAGEvaluator(
        dataset_path=_dataset(tmp_path),
        use_llm=False,
        pipeline=FakePipeline(),
    )

    report = evaluator.run()
    case = report.cases[0]

    assert "answer_relevance" not in case.metrics
    assert "llm_judge_reasons" not in case.observed
