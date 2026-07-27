# CV Bullets

Use these bullets in your CV, portfolio, or LinkedIn. Pick 2-4 depending on space.

## English Version

- Built an end-to-end Vietnamese Legal RAG assistant for the 2015 Civil Code, covering document ingestion, legal-aware chunking, metadata extraction, embedding, hybrid retrieval, grounded generation, and citation display.

- Designed a hybrid retrieval pipeline combining metadata search, lexical matching, vector retrieval, reranking, and accent-insensitive Vietnamese query handling to improve legal citation recall.

- Implemented hallucination-control mechanisms for legal QA, including evidence ID validation, grounded citation checks, weak-support detection, confidence signals, and abstention behavior.

- Developed an evaluation framework for Legal RAG with metrics for citation recall, source type recall, answer term coverage, grounding coverage, abstention correctness, latency, MRR, NDCG, and optional LLM-as-a-judge scoring.

- Built a FastAPI + React demo application with streaming chat responses, citation cards, conversation storage, API hardening, request IDs, rate limiting, security headers, and configurable production settings.

- Improved system reliability through regression tests, UTF-8 encoding validation, frontend lint/build quality gates, and benchmark datasets for Vietnamese legal questions.

## Short English Version

- Built a Vietnamese Legal RAG system with hybrid retrieval, legal metadata, grounded generation, citation validation, and evaluation benchmarks.

- Implemented hallucination controls and evidence-grounding checks for legal answers with citation-level confidence signals.

- Delivered a FastAPI/React RAG demo with production-readiness hardening, streaming responses, and automated regression checks.

## Vietnamese Version

- Xây dựng hệ thống Vietnamese Legal RAG cho Bộ luật Dân sự 2015, bao gồm ingestion, chunking theo cấu trúc pháp luật, metadata extraction, embedding, hybrid retrieval, grounded generation và citation display.

- Thiết kế pipeline truy xuất kết hợp metadata search, lexical matching, vector retrieval, reranking và xử lý truy vấn tiếng Việt không dấu nhằm cải thiện khả năng truy xuất căn cứ pháp lý.

- Triển khai cơ chế kiểm soát hallucination cho câu trả lời pháp lý, bao gồm kiểm tra evidence ID, grounded citation, weak support, confidence signals và abstention behavior.

- Xây dựng evaluation framework cho Legal RAG với các metric như citation recall, source type recall, grounding coverage, abstention correctness, latency, MRR, NDCG và LLM-as-a-judge.

- Phát triển demo FastAPI + React với streaming chat, citation cards, lưu hội thoại, API hardening, request ID, rate limiting, security headers và cấu hình production qua environment variables.

## Project Summary for Portfolio

Vietnamese Legal RAG Assistant is a portfolio-grade AI engineering project demonstrating how to build a domain-specific RAG system for Vietnamese law. It includes document processing, legal metadata, hybrid retrieval, grounded generation, hallucination control, evaluation metrics, and a full-stack demo application.

## Interview Talking Points

- Why vector-only retrieval is not enough for legal QA.
- How legal metadata improves retrieval and citation quality.
- How accent-insensitive Vietnamese matching helps user queries.
- How grounded generation reduces hallucination risk.
- Why evaluation needs both deterministic metrics and optional LLM-as-a-judge.
- What remains before public legal-production deployment.
