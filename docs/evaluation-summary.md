# Evaluation Summary

## Current Status

The current regression suite passes:

```text
Backend full test suite: 94 passed
Targeted RAG/retrieval/evaluation suite: 50 passed
Encoding validation: passed
Frontend lint: passed
Frontend build: passed
CI quality gate workflow: added
```

The tests cover:

- UTF-8 encoding integrity.
- Parser behavior.
- Query analysis.
- Retrieval quality improvements.
- Generation grounding and hallucination guardrails.
- Evaluation metrics and reporting.
- API hardening.
- LLM judge fallback and evaluator integration.

## Evaluation Dataset

The project includes an expanded dataset:

```text
backend/evaluation/datasets/legal_rag_eval_v2.json
```

It covers representative Legal RAG cases:

- Citation lookup.
- Unaccented Vietnamese legal queries.
- Validity/effectiveness questions.
- Scenario application.
- Case law retrieval.
- Out-of-scope abstention.
- Insufficient-evidence behavior.
- Latency and grounding thresholds.

## Metrics

The evaluator tracks:

- `request_type_match`
- `retrieval_citation_recall`
- `generation_citation_recall`
- `source_type_recall`
- `answer_term_coverage`
- `grounded_citation_precision`
- `grounding_coverage`
- `grounding_threshold_met`
- `invalid_evidence_free`
- `weak_support_free`
- `claims_have_evidence`
- `abstention_correctness`
- `latency_budget_met`
- `mrr`
- `recall_at_5`
- `ndcg`

When LLM judge is enabled, it also tracks:

- `answer_relevance`
- `faithfulness`
- `context_precision`

## How to Run

Deterministic evaluation:

```bash
cd backend
python scripts/evaluate_system.py --dataset evaluation/datasets/legal_rag_eval_v2.json --no-llm-judge --json
```

Production-style quality gate:

```bash
python scripts/evaluate_system.py --dataset evaluation/datasets/legal_rag_eval_v2.json --no-llm-judge --gate
```

The gate fails the process when aggregate Legal RAG metrics fall below the configured thresholds, including pass rate, average score, request type match, citation recall, grounded citation precision, grounding threshold, abstention correctness, invalid evidence checks, and latency budget.

Optional LLM judge:

```bash
python scripts/evaluate_system.py --dataset evaluation/datasets/legal_rag_eval_v2.json --with-llm-judge
```

## Important Limitation

Full end-to-end evaluation with local model/reranker loading can exceed a short command timeout. This is mainly a runtime/model-loading issue, not a unit-level correctness failure.

For CV and portfolio purposes, the current evidence is:

- Unit/regression tests pass.
- CI quality gates run backend/RAG regression, encoding validation, frontend lint, and frontend build.
- Evaluation framework exists.
- Dataset v2 exists.
- Deterministic and LLM-judge metrics are implemented.
- Full benchmark should be rerun with warm model cache or a longer timeout before production claims.

## Recommended Next Benchmark Work

Before using this project as a production system:

1. Run the full v2 benchmark with warm cache.
2. Save JSON and Markdown reports under `backend/evaluation/reports/`.
3. Add full benchmark thresholds to deployment CI once runtime/model caching is available.
4. Track latency percentiles over time.
5. Add a small API smoke benchmark that does not require all models to be cold-loaded.

## Suggested Portfolio Wording

Use conservative wording:

> Implemented an evaluation framework for a Vietnamese Legal RAG system, including citation recall, grounding coverage, abstention correctness, latency metrics, and optional LLM-as-a-judge scoring. Current regression suite passes backend, encoding, frontend lint, and frontend build checks.

Avoid claiming:

> Production-ready legal advice system.

The better claim is:

> Portfolio-grade Legal RAG system with production-readiness hardening and a clear path to deployment.
