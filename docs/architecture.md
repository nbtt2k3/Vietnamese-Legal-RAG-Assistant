# Architecture

This document explains the system architecture of the Vietnamese Legal RAG Assistant.

## High-Level Flow

```mermaid
flowchart TD
    subgraph Data["Data Pipeline"]
        A[Raw DOCX/PDF Legal Documents]
        B[Loader]
        C[Parser]
        D[Cleaner]
        E[Metadata Builder]
        F[Legal Chunker]
        H[Embedding Builder]
        I[Qdrant Indexer]
    end

    subgraph Runtime["Runtime RAG Pipeline"]
        U[User Query]
        Q[Query Analyzer]
        M[Metadata Retriever]
        L[Lexical Retriever]
        V[Vector Retriever]
        R[Reranker]
        EB[Evidence Builder]
        G[Grounded Generator]
        O[Answer + Citations + Confidence]
    end

    subgraph App["Application Layer"]
        FE[React Frontend]
        API[FastAPI API]
        DB[(SQLite Conversations)]
        OBS[Logs + Metrics]
    end

    A --> B --> C --> D --> E --> F --> H --> I
    FE --> API
    API --> Q
    Q --> M
    Q --> L
    Q --> V
    I --> V
    M --> R
    L --> R
    V --> R
    R --> EB --> G --> O --> API --> FE
    API --> DB
    API --> OBS
```

## Backend Modules

### `app/`

Contains the FastAPI server, API routes, middleware, configuration, database setup, and logging.

Key responsibilities:

- API endpoints for chat, streaming chat, conversations, and feedback.
- Request ID injection.
- Rate limiting.
- API key enforcement in production.
- Security headers.
- Health checks, separate liveness/readiness probes, and Prometheus metrics.

### `ingestion/`

Transforms raw legal documents into structured searchable artifacts.

Main stages:

- Load DOCX/PDF files.
- Parse legal structure.
- Clean text.
- Extract metadata.
- Validate official source and validity evidence through the source registry.
- Chunk by legal document structure.
- Generate embeddings.
- Index into Qdrant.

### `retrieval/`

Handles query understanding and evidence retrieval.

Important components:

- Query analyzer.
- Metadata retriever.
- Lexical retriever.
- Vector retriever.
- Reranker.
- Evidence builder.
- Accent-insensitive Vietnamese matching utilities.

### `generation/`

Creates final answers from retrieved evidence.

Important components:

- Prompt builder.
- Rule-based generator.
- Ollama/Groq generator options.
- Base generator validation.
- Citation and evidence grounding checks.
- Human-review gating for low-confidence, unverified, weakly grounded, or fact-sensitive answers.

### `evaluation/`

Measures RAG quality and regression behavior.

Metrics include:

- Request type match.
- Retrieval citation recall.
- Generation citation recall.
- Source type recall.
- Answer term coverage.
- Grounded citation precision.
- Grounding coverage.
- Abstention correctness.
- Latency budget.
- Optional LLM judge metrics.

## Design Choices

### Why Hybrid Retrieval?

Legal search needs both exact and semantic matching. A user may ask about "Điều 117", "the chap co hieu luc khi nao", or a long scenario. The system combines citation-aware matching, lexical search, vector retrieval, and reranking.

### Why Metadata-Rich Chunks?

Legal answer quality depends on source authority. Chunks carry citation, source type, legal role, validity metadata, and document relationships. This allows better ranking and better source display.

### Why Grounding Checks?

Legal hallucination is high risk. The generator validates citation IDs, weak support, and unsupported claims, then exposes confidence signals.

### Why Evaluation as a First-Class Module?

RAG quality can regress silently. The evaluation module provides repeatable benchmark cases and metrics that map to legal QA behavior.

## Deployment Notes

The project is currently strongest as a portfolio-grade or internal pilot system. Before public production usage, it should add:

- Full deployment gates beyond the current regression CI workflow.
- Monitoring dashboard and alerting.
- E2E tests.
- Operational staffing and escalation process for human-reviewed high-risk legal answers.
