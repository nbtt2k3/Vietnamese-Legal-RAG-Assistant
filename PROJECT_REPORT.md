# Project Report: Vietnamese Legal RAG Assistant

## 1. Problem

Vietnamese legal question answering requires more than general semantic search. A useful system must understand legal intent, retrieve authoritative legal grounds, produce grounded answers, cite sources, handle uncertainty, and avoid unsupported legal claims.

The initial goal of this project was to build a specialized Legal RAG system for Vietnamese law, starting with the 2015 Civil Code and related documents, while keeping the architecture extensible to other domains.

## 2. Solution Overview

The project implements an end-to-end Legal RAG application with:

- Legal document ingestion and metadata extraction.
- Legal-aware chunking.
- Embedding and Qdrant indexing.
- Hybrid retrieval combining metadata, lexical, vector, and reranking signals.
- Grounded generation with citation and evidence validation.
- Evaluation benchmarks for retrieval and generation quality.
- FastAPI backend and React frontend.
- Production-readiness improvements such as API hardening, request IDs, rate limiting, security headers, and configuration via environment variables.

## 3. Technical Architecture

The system is split into five main layers:

1. **Ingestion layer**
   - Loads DOCX/PDF legal documents.
   - Parses document structures.
   - Cleans text and builds metadata.
   - Produces structured JSON artifacts and manifests.

2. **Indexing layer**
   - Converts chunks into embeddings.
   - Stores vectors in Qdrant.
   - Validates chunk and embedding consistency before indexing.

3. **Retrieval layer**
   - Analyzes user query intent.
   - Uses metadata retrieval for citations and legal source constraints.
   - Uses lexical retrieval with accent-insensitive Vietnamese matching.
   - Uses vector retrieval and reranking for semantic relevance.
   - Builds evidence bundles for generation.

4. **Generation layer**
   - Builds grounded prompts.
   - Generates answers through rule-based or LLM-backed paths.
   - Validates evidence IDs and citation support.
   - Produces confidence and hallucination-control signals.

5. **Application and evaluation layer**
   - Exposes FastAPI endpoints and a React chat UI.
   - Tracks evaluation metrics, benchmark cases, and LLM judge results.

## 4. Key Engineering Decisions

### Hybrid retrieval instead of vector-only search

Legal queries often refer to exact citations, article numbers, document types, and legal roles. Pure vector search can miss exact legal anchors, so the system combines metadata, lexical, vector, and reranking strategies.

### Metadata-first legal grounding

Each chunk carries legal metadata such as citation, source type, legal role, validity fields, and document references. This supports better retrieval, source filtering, answer grounding, and citation rendering.

### Evidence-aware generation

The generation layer does not only produce text. It also checks whether generated citations map to retrieved evidence and whether claims appear sufficiently supported.

### Evaluation-driven improvement

The project includes deterministic metrics and optional LLM-as-a-judge evaluation. The benchmark covers citation recall, source recall, answer term coverage, grounding coverage, abstention, latency, and judge scores.

## 5. Roadmap Improvements Completed

The project was improved through multiple phases:

- Encoding integrity and UTF-8 validation.
- Grounded generation and hallucination control.
- Accent-insensitive retrieval and vector fallback.
- Expanded evaluation benchmark and reporting.
- API hardening and production configuration.
- Frontend lint/build quality gate.
- LLM judge hardening with timeout, safe fallback, and judge reasons.

## 6. Current Quality Status

Regression checks currently pass:

- Backend/RAG tests: `35 passed`
- Encoding validation: passed
- Frontend lint: passed
- Frontend build: passed

The system is suitable for portfolio demonstration, technical interview discussion, and internal pilot usage.

## 7. Remaining Limitations

The project is not yet ready for public legal-production usage because:

- Full benchmark execution can be slow due to local model/reranker loading.
- CI/CD quality gates are not yet implemented.
- Monitoring dashboards and alerting are not yet configured.
- Legal corpus update and legal review workflows are not yet formalized.
- Frontend component/e2e tests are not yet implemented.

## 8. What This Project Demonstrates

This project demonstrates practical ability in:

- RAG system architecture.
- Vietnamese legal NLP.
- Hybrid retrieval and reranking.
- Metadata-aware chunking.
- Citation-grounded generation.
- Hallucination control.
- Evaluation framework design.
- FastAPI/React integration.
- Production hardening basics.

## 9. Production Decision

As a Technical Lead, I would approve this system for:

- Portfolio demo.
- Technical interview showcase.
- Staging environment.
- Internal pilot with clear disclaimers.

I would not approve it for public legal-production use until benchmark automation, monitoring, legal corpus governance, and human review workflows are added.
