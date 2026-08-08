from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvalCase:
    case_id: str
    query: str
    generated_from: str | None = None
    tags: list[str] = field(default_factory=list)
    expected_request_type: str = ""
    expected_citations: list[str] = field(default_factory=list)
    expected_source_types: list[str] = field(default_factory=list)
    expected_answer_terms: list[str] = field(default_factory=list)
    min_confidence_level: str = "medium"
    should_answer: bool = True
    max_latency_seconds: float | None = None
    min_grounding_coverage: float = 0.0
    expected_missing_facts_terms: list[str] = field(default_factory=list)
    expected_disclaimer_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseEvaluation:
    case_id: str
    query: str
    score: float
    passed: bool
    metrics: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    observed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    dataset_name: str
    total_cases: int
    pass_rate: float
    average_score: float
    aggregate_metrics: dict[str, float] = field(default_factory=dict)
    cases: list[CaseEvaluation] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_cases": self.total_cases,
            "pass_rate": self.pass_rate,
            "average_score": self.average_score,
            "metadata": self.metadata,
            "aggregate_metrics": self.aggregate_metrics,
            "cases": [item.to_dict() for item in self.cases],
        }
