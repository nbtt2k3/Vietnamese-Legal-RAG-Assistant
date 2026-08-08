from statistics import mean
import time
from collections.abc import Callable

from evaluation.dataset_loader import load_eval_dataset
from evaluation.models import CaseEvaluation, EvalCase, EvaluationReport
from evaluation.utils import best_match_ratio, citation_matches, confidence_at_least
from app.core.config import settings
from rag.generation.pipeline import GenerationPipeline
from rag.retrieval.error_taxonomy import classify_retrieval_errors


from evaluation.llm_judge import LLMJudge

class LegalRAGEvaluator:
    def __init__(
        self,
        dataset_path: str,
        use_llm: bool = False,
        use_llm_judge: bool | None = None,
        pipeline=None,
        llm_judge=None,
        case_pass_threshold: float = 0.7,
    ):
        self.dataset_name, self.cases = load_eval_dataset(dataset_path)
        self.pipeline = pipeline or GenerationPipeline(use_llm=use_llm)
        self.use_llm_judge = settings.llm_judge_enabled if use_llm_judge is None else use_llm_judge
        self.llm_judge = llm_judge or (LLMJudge() if self.use_llm_judge else None)
        self.case_pass_threshold = case_pass_threshold

    def run(self, progress_callback: Callable[[int, int, CaseEvaluation], None] | None = None) -> EvaluationReport:
        case_reports = []
        total = len(self.cases)
        for index, case in enumerate(self.cases, start=1):
            result = self._evaluate_case(case)
            case_reports.append(result)
            if progress_callback:
                progress_callback(index, total, result)
        total_cases = len(case_reports)
        average_score = mean([item.score for item in case_reports]) if case_reports else 0.0
        pass_rate = (sum(1 for item in case_reports if item.passed) / total_cases) if total_cases else 0.0
        aggregate_metrics = self._aggregate_metrics(case_reports)
        return EvaluationReport(
            dataset_name=self.dataset_name,
            total_cases=total_cases,
            pass_rate=round(pass_rate, 4),
            average_score=round(average_score, 4),
            aggregate_metrics=aggregate_metrics,
            cases=case_reports,
        )

    def _evaluate_case(self, case: EvalCase) -> CaseEvaluation:
        t0 = time.time()
        answer, retrieval = self.pipeline.run(case.query)
        latency_seconds = time.time() - t0
        retrieval_citations = [str(item.metadata.get("citation", item.chunk_id)) for item in retrieval.candidates[:8]]
        generation_citations = [item.citation for item in answer.citations]
        observed_sources = [str(item.metadata.get("loai_van_ban", "")) for item in retrieval.candidates[:8]]
        answer_text = " ".join([answer.short_answer] + [section.content for section in answer.sections]).strip()
        disclaimer_text = " ".join(answer.disclaimers)
        observed_confidence = str(answer.confidence.get("level", "low"))
        grounding_coverage = answer.confidence.get("grounding_coverage")
        if grounding_coverage is None:
            grounding_coverage = 1.0 if generation_citations else 0.0
        grounding_coverage = float(grounding_coverage)
        should_abstain = not case.should_answer
        abstained = self._answer_abstained(answer, generation_citations)
        judge_applicable = not (should_abstain and abstained)

        metrics = {
            "request_type_match": 1.0 if retrieval.query_intent.loai_yeu_cau == case.expected_request_type else 0.0,
            "retrieval_citation_recall": best_match_ratio(retrieval_citations, case.expected_citations),
            "generation_citation_recall": best_match_ratio(generation_citations, case.expected_citations),
            "source_type_recall": best_match_ratio(observed_sources, case.expected_source_types),
            "answer_term_coverage": best_match_ratio([answer_text], case.expected_answer_terms),
            "disclaimer_presence": 1.0 if answer.disclaimers else 0.0,
            "disclaimer_term_coverage": best_match_ratio([disclaimer_text], case.expected_disclaimer_terms),
            "confidence_sufficiency": 1.0 if confidence_at_least(observed_confidence, case.min_confidence_level) else 0.0,
            "grounded_citation_precision": self._grounded_citation_precision(generation_citations, retrieval_citations),
            "grounding_coverage": grounding_coverage,
            "grounding_threshold_met": 1.0 if grounding_coverage >= case.min_grounding_coverage else 0.0,
            "invalid_evidence_free": 0.0 if answer.confidence.get("invalid_evidence_used") else 1.0,
            "weak_support_free": 0.0 if answer.confidence.get("weakly_supported_claims") else 1.0,
            "claims_have_evidence": 0.0 if answer.confidence.get("claims_without_evidence") else 1.0,
            "abstention_correctness": 1.0 if abstained == should_abstain else 0.0,
            "missing_facts_term_coverage": best_match_ratio([str(answer.confidence.get("missing_facts", ""))], case.expected_missing_facts_terms),
            "latency_budget_met": 1.0 if case.max_latency_seconds is None or latency_seconds <= case.max_latency_seconds else 0.0,
            "mrr": self._calculate_mrr(retrieval_citations, case.expected_citations),
            "recall_at_5": self._calculate_recall_at_k(retrieval_citations, case.expected_citations, 5),
            "ndcg": self._calculate_ndcg(retrieval_citations, case.expected_citations),
        }
        retrieval_errors = classify_retrieval_errors(case, retrieval)
        metrics["retrieval_error_free"] = 1.0 if not retrieval_errors else 0.0
        
        # Phase 7 TruLens-like Triad (LLM-as-a-judge)
        if self.use_llm_judge:
            if hasattr(self.llm_judge, "last_reasons"):
                self.llm_judge.last_reasons.clear()
            if judge_applicable:
                context_text = "\n".join([item.text for item in retrieval.candidates[:5]])
                if hasattr(self.llm_judge, "evaluate_triad"):
                    metrics.update(self.llm_judge.evaluate_triad(case.query, answer_text, context_text))
                else:
                    metrics["answer_relevance"] = self.llm_judge.evaluate_answer_relevance(case.query, answer_text)
                    metrics["faithfulness"] = self.llm_judge.evaluate_faithfulness(answer_text, context_text)
                    metrics["context_precision"] = self.llm_judge.evaluate_context_precision(case.query, context_text)
            else:
                # A correctly abstained out-of-scope answer has no legal
                # context to judge. Do not send it to the LLM judge and do
                # not penalize it as if an empty context were a bad answer.
                abstention_score = 1.0 if abstained == should_abstain else 0.0
                metrics.update({
                    "answer_relevance": abstention_score,
                    "faithfulness": abstention_score,
                    "context_precision": abstention_score,
                })
            
        score = self._score_case(metrics, case)
        notes = self._build_notes(case, retrieval.query_intent.loai_yeu_cau, retrieval_citations, generation_citations, observed_confidence, metrics)
        observed = {
            "request_type": retrieval.query_intent.loai_yeu_cau,
            "retrieval_top_citations": retrieval_citations,
            "generation_citations": generation_citations,
            "confidence_level": observed_confidence,
            "answer_method": answer.answer_method,
            "latency_seconds": round(latency_seconds, 3),
            "candidate_count": len(retrieval.candidates),
            "grounding_coverage": round(grounding_coverage, 4),
            "disclaimer_count": len(answer.disclaimers),
            "abstained": abstained,
            "retrieval_error_types": retrieval_errors,
        }
        if self.use_llm_judge and self.llm_judge:
            observed["llm_judge_applicable"] = judge_applicable
            observed["llm_judge_reasons"] = dict(getattr(self.llm_judge, "last_reasons", {}))
        return CaseEvaluation(
            case_id=case.case_id,
            query=case.query,
            score=round(score, 4),
            passed=score >= self.case_pass_threshold,
            metrics={key: round(value, 4) for key, value in metrics.items()},
            notes=notes,
            observed=observed,
        )

    def _calculate_mrr(self, retrieval_citations: list[str], expected_citations: list[str]) -> float:
        if not expected_citations:
            return 1.0
        for idx, obs in enumerate(retrieval_citations):
            for exp in expected_citations:
                if citation_matches(obs, exp):
                    return 1.0 / (idx + 1)
        return 0.0

    def _calculate_recall_at_k(self, retrieval_citations: list[str], expected_citations: list[str], k: int) -> float:
        if not expected_citations:
            return 1.0
        hits = set()
        for obs in retrieval_citations[:k]:
            for exp in expected_citations:
                if citation_matches(obs, exp):
                    hits.add(exp)
        return len(hits) / len(expected_citations)

    def _calculate_ndcg(self, retrieval_citations: list[str], expected_citations: list[str]) -> float:
        if not expected_citations:
            return 1.0
        import math

        dcg = 0.0
        matched_expected: set[str] = set()
        for idx, obs in enumerate(retrieval_citations):
            hit = None
            for exp in expected_citations:
                if exp in matched_expected:
                    continue
                if citation_matches(obs, exp):
                    hit = exp
                    break
            if hit:
                matched_expected.add(hit)
                dcg += 1.0 / math.log2(idx + 2)

        ideal_hits = min(len(expected_citations), len(retrieval_citations))
        idcg = sum(1.0 / math.log2(idx + 2) for idx in range(ideal_hits))
        return dcg / idcg if idcg else 0.0

    def _grounded_citation_precision(self, generation_citations: list[str], retrieval_citations: list[str]) -> float:
        if not generation_citations:
            return 0.0
        grounded = 0
        for citation in generation_citations:
            if best_match_ratio(retrieval_citations, [citation]) >= 1.0:
                grounded += 1
        return grounded / max(1, len(generation_citations))

    def _answer_abstained(self, answer, generation_citations: list[str]) -> bool:
        haystack = " ".join([answer.short_answer] + [section.content for section in answer.sections] + answer.disclaimers).lower()
        abstention_markers = [
            "từ chối",
            "không tìm thấy căn cứ",
            "không đủ căn cứ",
            "ngoài phạm vi",
            "chưa cập nhật",
            "không thể trả lời",
        ]
        if any(marker in haystack for marker in abstention_markers):
            return True
        return not generation_citations and str(answer.confidence.get("level", "low")) == "low"

    def _score_case(self, metrics: dict[str, float], case: EvalCase) -> float:
        if not case.should_answer:
            # Abstention cases are evaluated by guardrail correctness and
            # scope messaging, not by answer relevance to an intentionally
            # unsupported question.
            weights = {
                "request_type_match": 0.20,
                "abstention_correctness": 0.35,
                "confidence_sufficiency": 0.15,
                "disclaimer_presence": 0.15,
                "answer_term_coverage": 0.10,
                "latency_budget_met": 0.05,
            }
        elif self.use_llm_judge:
            weights = {
                "request_type_match": 0.05,
                "mrr": 0.15,
                "generation_citation_recall": 0.10,
                "answer_term_coverage": 0.10,
                "grounded_citation_precision": 0.10,
                "answer_relevance": 0.20,
                "faithfulness": 0.15,
                "context_precision": 0.15
            }
        else:
            weights = {
                "request_type_match": 0.10,
                "mrr": 0.20,
                "generation_citation_recall": 0.12,
                "source_type_recall": 0.08,
                "answer_term_coverage": 0.12,
                "disclaimer_presence": 0.04,
                "confidence_sufficiency": 0.05,
                "grounded_citation_precision": 0.10,
                "grounding_threshold_met": 0.09,
                "invalid_evidence_free": 0.05,
                "abstention_correctness": 0.05,
            }
            if "scenario" in case.tags:
                weights["source_type_recall"] = 0.05
                weights["answer_term_coverage"] = 0.17
                weights["generation_citation_recall"] = 0.09
                weights["mrr"] = 0.18
        
        total_weight = sum(weights.values())
        if total_weight <= 0:
            return 0.0
        weighted_score = sum(metrics.get(name, 0) * weight for name, weight in weights.items())
        return weighted_score / total_weight

    def _build_notes(
        self,
        case: EvalCase,
        observed_request_type: str,
        retrieval_citations: list[str],
        generation_citations: list[str],
        observed_confidence: str,
        metrics: dict[str, float],
    ) -> list[str]:
        notes: list[str] = []
        if observed_request_type != case.expected_request_type:
            notes.append(f"Request type lệch: expected={case.expected_request_type}, observed={observed_request_type}.")
        if metrics["retrieval_citation_recall"] < 1.0:
            notes.append("Retrieval chưa kéo đủ căn cứ kỳ vọng vào top candidates.")
        if metrics["generation_citation_recall"] < 1.0:
            notes.append("Generation chưa trích dẫn đủ căn cứ kỳ vọng.")
        if metrics["answer_term_coverage"] < 1.0:
            notes.append("Nội dung trả lời chưa phủ hết thuật ngữ pháp lý hoặc kết luận kỳ vọng.")
        if metrics.get("grounding_threshold_met", 1.0) < 1.0:
            notes.append("Grounding coverage thấp hơn ngưỡng kỳ vọng.")
        if metrics.get("invalid_evidence_free", 1.0) < 1.0:
            notes.append("Answer có dấu hiệu dùng evidence id không hợp lệ.")
        if metrics.get("weak_support_free", 1.0) < 1.0:
            notes.append("Có claim dùng citation nhưng mức support với evidence còn yếu.")
        if metrics.get("claims_have_evidence", 1.0) < 1.0:
            notes.append("Có claim không có evidence hợp lệ.")
        if metrics.get("abstention_correctness", 1.0) < 1.0:
            notes.append("Abstention behavior không khớp kỳ vọng của test case.")
        if metrics.get("latency_budget_met", 1.0) < 1.0:
            notes.append("Latency vượt ngân sách của test case.")
        if not confidence_at_least(observed_confidence, case.min_confidence_level):
            notes.append(f"Confidence thấp hơn ngưỡng mong muốn: {observed_confidence} < {case.min_confidence_level}.")
        if not generation_citations:
            notes.append("Generation không xuất citation.")
        if not retrieval_citations:
            notes.append("Retrieval không có top citations để đánh giá.")
        return notes

    def _aggregate_metrics(self, case_reports: list[CaseEvaluation]) -> dict[str, float]:
        if not case_reports:
            return {}
        keys = sorted({key for item in case_reports for key in item.metrics})
        judge_only_metrics = {"answer_relevance", "faithfulness", "context_precision"}
        aggregate = {}
        for key in keys:
            values = [
                item.metrics[key]
                for item in case_reports
                if key in item.metrics
                and (
                    key not in judge_only_metrics
                    or item.observed.get("llm_judge_applicable", True)
                )
            ]
            if values:
                aggregate[key] = round(mean(values), 4)
        error_cases = sum(
            1 for item in case_reports
            if item.observed.get("retrieval_error_types")
        )
        aggregate["retrieval_error_rate"] = round(error_cases / len(case_reports), 4)
        latencies = sorted(
            item.observed.get("latency_seconds", 0.0)
            for item in case_reports
            if "latency_seconds" in item.observed
        )
        if latencies:
            aggregate["avg_latency_seconds"] = round(mean(latencies), 4)
            aggregate["p50_latency_seconds"] = round(self._percentile(latencies, 50), 4)
            aggregate["p95_latency_seconds"] = round(self._percentile(latencies, 95), 4)
        return aggregate

    def _percentile(self, values: list[float], percentile: int) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]
        index = (len(values) - 1) * percentile / 100
        lower = int(index)
        upper = min(lower + 1, len(values) - 1)
        weight = index - lower
        return values[lower] * (1 - weight) + values[upper] * weight
