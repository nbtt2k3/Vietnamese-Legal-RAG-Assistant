from evaluation.models import EvaluationReport


def report_to_markdown(report: EvaluationReport) -> str:
    lines = [
        f"# Evaluation Report: {report.dataset_name}",
        "",
        f"- Total cases: {report.total_cases}",
        f"- Pass rate: {report.pass_rate:.2%}",
        f"- Average score: {report.average_score:.3f}",
        ""
    ]
    if report.metadata:
        lines.append("## Metadata")
        for key, value in report.metadata.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        
    lines.append("## Aggregate Metrics")
    for key, value in report.aggregate_metrics.items():
        lines.append(f"- {key}: {value:.3f}")

    lines.append("")
    lines.append("## Case Results")
    for item in report.cases:
        status = "PASS" if item.passed else "FAIL"
        lines.append("")
        lines.append(f"### {item.case_id} [{status}]")
        lines.append(f"- Query: {item.query}")
        lines.append(f"- Score: {item.score:.3f}")
        if item.observed:
            lines.append("- Observed:")
            for key in [
                "request_type",
                "confidence_level",
                "answer_method",
                "latency_seconds",
                "candidate_count",
                "grounding_coverage",
                "disclaimer_count",
                "abstained",
            ]:
                if key in item.observed:
                    lines.append(f"  - {key}: {item.observed[key]}")
            if item.observed.get("retrieval_top_citations"):
                lines.append("  - retrieval_top_citations:")
                for citation in item.observed["retrieval_top_citations"][:5]:
                    lines.append(f"    - {citation}")
            if item.observed.get("generation_citations"):
                lines.append("  - generation_citations:")
                for citation in item.observed["generation_citations"][:5]:
                    lines.append(f"    - {citation}")
            if item.observed.get("llm_judge_reasons"):
                lines.append("  - llm_judge_reasons:")
                for metric, reason in item.observed["llm_judge_reasons"].items():
                    lines.append(f"    - {metric}: {reason}")
        for key, value in item.metrics.items():
            lines.append(f"- {key}: {value:.3f}")
        if item.notes:
            lines.append("- Notes:")
            for note in item.notes:
                lines.append(f"  - {note}")
    return "\n".join(lines)
