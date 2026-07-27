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
from evaluation.reporting import report_to_markdown
from app.config import settings


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Evaluate Legal RAG end-to-end")
    parser.add_argument(
        "--dataset",
        default="evaluation/datasets/legal_rag_eval_v1.json",
        help="Đường dẫn tới file benchmark dataset JSON",
    )
    parser.add_argument("--with-llm", action="store_true", help="Bật nhánh generation bằng LLM nếu có cấu hình")
    parser.add_argument("--with-llm-judge", action="store_true", help="Bật LLM Judge cho evaluation triad")
    parser.add_argument("--no-llm-judge", action="store_true", help="Tắt LLM Judge, dùng deterministic evaluation")
    parser.add_argument("--json", action="store_true", help="In kết quả JSON")
    parser.add_argument("--save-json", type=str, default="", help="Lưu báo cáo JSON ra file")
    parser.add_argument("--save-md", type=str, default="", help="Lưu báo cáo Markdown ra file")
    args = parser.parse_args()
    
    use_judge = settings.llm_judge_enabled
    if args.with_llm_judge:
        use_judge = True
    if args.no_llm_judge:
        use_judge = False
    evaluator = LegalRAGEvaluator(dataset_path=args.dataset, use_llm=args.with_llm, use_llm_judge=use_judge)
    report = evaluator.run()
    
    import subprocess
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode("utf-8").strip()
    except Exception:
        git_commit = "unknown"
        
    report.metadata = {
        "git_commit": git_commit,
        "embedding_model": settings.embedding_model_name,
        "reranker_model": settings.reranker_model_name,
        "use_llm_generation": str(args.with_llm),
        "use_llm_judge": str(use_judge),
        "llm_judge_timeout_seconds": str(settings.llm_judge_timeout_seconds),
    }
    
    payload = report.to_dict()
    markdown = report_to_markdown(report)

    if args.save_json:
        Path(args.save_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.save_md:
        Path(args.save_md).write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(markdown)


if __name__ == "__main__":
    main()
