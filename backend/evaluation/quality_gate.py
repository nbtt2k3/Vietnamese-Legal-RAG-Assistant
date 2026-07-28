from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evaluation.models import EvaluationReport


DEFAULT_QUALITY_THRESHOLDS: dict[str, float] = {
    "pass_rate": 0.85,
    "average_score": 0.78,
    "request_type_match": 0.90,
    "retrieval_citation_recall": 0.75,
    "generation_citation_recall": 0.70,
    "grounded_citation_precision": 0.90,
    "grounding_threshold_met": 0.85,
    "invalid_evidence_free": 1.00,
    "abstention_correctness": 0.90,
    "latency_budget_met": 0.90,
}


@dataclass
class QualityGateResult:
    passed: bool
    thresholds: dict[str, float] = field(default_factory=dict)
    observed: dict[str, float] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "thresholds": self.thresholds,
            "observed": self.observed,
            "failures": self.failures,
        }


def evaluate_quality_gate(
    report: EvaluationReport,
    thresholds: dict[str, float] | None = None,
) -> QualityGateResult:
    active_thresholds = dict(DEFAULT_QUALITY_THRESHOLDS)
    if thresholds:
        active_thresholds.update(thresholds)

    observed = {
        "pass_rate": report.pass_rate,
        "average_score": report.average_score,
        **report.aggregate_metrics,
    }
    failures = []
    for metric, minimum in active_thresholds.items():
        value = float(observed.get(metric, 0.0))
        if value < minimum:
            failures.append(f"{metric}: observed={value:.4f} < required={minimum:.4f}")

    return QualityGateResult(
        passed=not failures,
        thresholds=active_thresholds,
        observed={key: round(float(value), 4) for key, value in observed.items() if key in active_thresholds},
        failures=failures,
    )
