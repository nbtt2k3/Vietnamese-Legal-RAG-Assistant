import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.evaluator import LegalRAGEvaluator
from evaluation.quality_gate import evaluate_quality_gate
from evaluation.reporting import report_to_markdown
from app.core.config import settings


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Evaluate Legal RAG end-to-end")
    parser.add_argument(
        "--dataset",
        default="evaluation/datasets/legal_rag_eval_civil_v1.json",
        help="Đường dẫn tới file benchmark dataset JSON",
    )
    parser.add_argument("--with-llm", action="store_true", help="Bật nhánh generation bằng LLM nếu có cấu hình")
    parser.add_argument("--with-llm-judge", action="store_true", help="Bật LLM Judge cho evaluation triad")
    parser.add_argument("--no-llm-judge", action="store_true", help="Tắt LLM Judge, dùng deterministic evaluation")
    parser.add_argument("--json", action="store_true", help="In kết quả JSON")
    parser.add_argument("--save-json", type=str, default="", help="Lưu báo cáo JSON ra file")
    parser.add_argument("--save-md", type=str, default="", help="Lưu báo cáo Markdown ra file")
    parser.add_argument("--gate", action="store_true", help="Fail process if evaluation does not meet the quality gate")
    parser.add_argument("--case-threshold", type=float, default=0.7, help="Minimum score required for each case to pass")
    parser.add_argument("--thresholds-json", type=str, default="", help="JSON object overriding quality gate thresholds")
    args = parser.parse_args()
    
    use_judge = settings.llm_judge_enabled
    if args.with_llm_judge:
        use_judge = True
    if args.no_llm_judge:
        use_judge = False
    evaluator = LegalRAGEvaluator(
        dataset_path=args.dataset,
        use_llm=args.with_llm,
        use_llm_judge=use_judge,
        case_pass_threshold=args.case_threshold,
    )
    report = evaluator.run()
    
    import subprocess
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
    except Exception:
        git_commit = "unknown"
        
    gate_result = None
    if args.gate:
        threshold_overrides = json.loads(args.thresholds_json) if args.thresholds_json else None
        gate_result = evaluate_quality_gate(report, thresholds=threshold_overrides)

    report.metadata = {
        "git_commit": git_commit,
        "embedding_model": settings.embedding_model_name,
        "reranker_model": settings.reranker_model_name,
        "use_llm_generation": str(args.with_llm),
        "use_llm_judge": str(use_judge),
        "llm_judge_timeout_seconds": str(settings.llm_judge_timeout_seconds),
        "case_pass_threshold": str(args.case_threshold),
    }
    if gate_result:
        report.metadata["quality_gate_passed"] = str(gate_result.passed)
        if gate_result.failures:
            report.metadata["quality_gate_failures"] = " | ".join(gate_result.failures)
    
    payload = report.to_dict()
    markdown = report_to_markdown(report)

    if args.save_json:
        Path(args.save_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.save_md:
        Path(args.save_md).write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if gate_result and not gate_result.passed:
            raise SystemExit(1)
        return

    print(markdown)
    if gate_result and not gate_result.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
