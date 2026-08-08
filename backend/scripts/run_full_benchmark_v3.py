"""Run the full v3 benchmark against the local corpus.

This harness is for the checked-in local Qdrant snapshot. It keeps vector
retrieval, BM25, cross-encoder reranking, cross-document expansion and the
LLM judge enabled. Only query classification is forced deterministic so the
benchmark measures retrieval/generation/judging rather than an extra LLM call.
"""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from evaluation.evaluator import LegalRAGEvaluator
from evaluation.reporting import report_to_markdown
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models
from rag.retrieval.query_analyzer import QueryAnalyzer
from rag.retrieval.repository import QdrantRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark v3 against the configured Qdrant service.")
    parser.add_argument(
        "--qdrant-url",
        default=None,
        help="Qdrant URL override. In Docker use http://qdrant:6333; otherwise settings.QDRANT_URL is used.",
    )
    parser.add_argument("--collection", default="legal_docs", help="Qdrant collection to benchmark.")
    parser.add_argument("--subset-size", type=int, default=0, help="Run a representative subset instead of all cases.")
    parser.add_argument(
        "--baseline-report",
        default=None,
        help="Previous JSON report used to prioritize wrong_article/missing_related_document/wrong_document cases.",
    )
    args = parser.parse_args()

    # The local snapshot was written by a newer Qdrant client that adds a
    # nullable collection metadata field. Ignore that forward-compatible field
    # when loading it with the installed client.
    rest_models.CreateCollection.model_config["extra"] = "ignore"
    rest_models.CreateCollection.model_rebuild(force=True)

    # Keep the configured connection. Docker Compose injects
    # QDRANT_URL=http://qdrant:6333 and QDRANT_API_KEY into the app container.
    # The previous version forced qdrant_url=None and silently benchmarked a
    # local snapshot that is not the Docker Qdrant volume.
    if args.qdrant_url:
        settings.qdrant_url = args.qdrant_url
    settings.llm_judge_enabled = True
    settings.llm_judge_timeout_seconds = 60.0
    settings.llm_judge_max_attempts = 2

    client_kwargs = {"url": settings.qdrant_url} if settings.qdrant_url else {"path": str(settings.qdrant_db_path)}
    if settings.qdrant_url and settings.qdrant_api_key:
        client_kwargs["api_key"] = settings.qdrant_api_key
    shared = QdrantClient(**client_kwargs)
    try:
        collection_info = shared.get_collection(collection_name=args.collection)
        collection_count = shared.count(collection_name=args.collection, exact=True).count
        points, _ = shared.scroll(
            collection_name=args.collection,
            limit=10000,
            with_payload=True,
            with_vectors=False,
        )
        payloads = [point.payload or {} for point in points]

        # Keep one service client and one payload snapshot for the whole run.
        # This uses the same Docker Qdrant endpoint as normal application
        # traffic while avoiding a full payload scroll for every case.
        shared.count = lambda *args, **kwargs: SimpleNamespace(count=len(payloads))
        QdrantRepository.__enter__ = lambda self: (setattr(self, "client", shared) or self)
        QdrantRepository.__exit__ = lambda self, exc_type, exc, tb: None
        QdrantRepository.all_payloads = lambda self: payloads
        def benchmark_repository_init(self, db_path=str(settings.qdrant_db_path), collection_name=args.collection):
            self.db_path = db_path
            self.collection_name = collection_name
            self.client = None
            self._payloads = None

        QdrantRepository.__init__ = benchmark_repository_init

        # Avoid an additional LLM call for ambiguous query classification. The
        # requested LLM judge remains enabled for every benchmark case.
        original_analyze = QueryAnalyzer.analyze
        QueryAnalyzer.analyze = lambda self, query, force_deterministic=False, history=None: original_analyze(
            self, query, True, history
        )

        evaluator = LegalRAGEvaluator(
            dataset_path=str(ROOT / "evaluation" / "datasets" / "legal_rag_eval_v3.json"),
            use_llm=False,
            use_llm_judge=True,
        )

        if args.subset_size and args.subset_size < len(evaluator.cases):
            baseline_types: dict[str, list[str]] = {}
            if args.baseline_report:
                baseline_path = Path(args.baseline_report)
                if baseline_path.exists():
                    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
                    for case in baseline.get("cases", []):
                        errors = case.get("observed", {}).get("retrieval_error_types", [])
                        for error_type in errors:
                            baseline_types.setdefault(error_type, []).append(case.get("case_id"))

            priority_ids = []
            for error_type in ("wrong_article", "missing_related_document", "wrong_document"):
                priority_ids.extend(baseline_types.get(error_type, []))
            by_id = {case.case_id: case for case in evaluator.cases}
            selected = []
            for case_id in priority_ids:
                case = by_id.get(case_id)
                if case and case not in selected:
                    selected.append(case)
                if len(selected) >= args.subset_size:
                    break
            for case in evaluator.cases:
                if len(selected) >= args.subset_size:
                    break
                if case not in selected:
                    selected.append(case)
            evaluator.cases = selected
            print(
                f"Running representative subset {len(selected)} cases "
                f"(priority retrieval errors first)",
                flush=True,
            )

        def show_progress(index, total, result):
            print(
                f"[{index}/{total}] {result.case_id} "
                f"score={result.score:.3f} "
                f"status={'PASS' if result.passed else 'FAIL'}",
                flush=True,
            )

        report = evaluator.run(progress_callback=show_progress)
        report.metadata = {
            "benchmark_mode": "full_local",
            "dataset": "legal_rag_eval_v3",
            "case_count": str(report.total_cases),
            "vector_retrieval": "enabled",
            "bm25_retrieval": "enabled",
            "cross_encoder_reranking": "enabled",
            "cross_document_expansion": "enabled",
            "llm_judge": "enabled_triad_one_call_per_case",
            "query_analyzer": "deterministic_for_benchmark_control",
            "embedding_model": settings.embedding_model_name,
            "reranker_model": settings.reranker_model_name,
            "judge_model": settings.llm_model_name,
            "qdrant_target": settings.qdrant_url or str(settings.qdrant_db_path),
            "qdrant_collection": args.collection,
            "qdrant_collection_count": str(collection_count),
            "qdrant_collection_status": str(collection_info.status),
            "qdrant_snapshot_payload_count": str(len(payloads)),
            "subset_size": str(args.subset_size or report.total_cases),
            "subset_baseline_report": str(args.baseline_report or ""),
        }

        # ``evaluation/reports`` is intentionally excluded from the Docker
        # image and is not a mounted volume. Persist benchmark artifacts under
        # data/, which is mounted by docker-compose to the host workspace.
        reports_dir = settings.data_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"_subset_{report.total_cases}" if args.subset_size else "_full_docker"
        json_path = reports_dir / f"legal_rag_eval_v3{suffix}.json"
        md_path = reports_dir / f"legal_rag_eval_v3{suffix}.md"
        json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(report_to_markdown(report), encoding="utf-8")
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        print(f"Saved: {json_path}")
        print(f"Saved: {md_path}")
    finally:
        shared.close()


if __name__ == "__main__":
    main()
