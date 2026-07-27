# Vietnamese Legal RAG Assistant

Vietnamese Legal RAG Assistant is an end-to-end Retrieval-Augmented Generation system for Vietnamese legal question answering. The first version focuses on the 2015 Civil Code and related legal documents, with a design that can expand to other legal domains without rewriting the core retrieval and generation pipeline.

The project demonstrates a practical Legal RAG stack: document ingestion, legal-aware chunking, metadata extraction, embedding, hybrid retrieval, reranking, grounded answer generation, citation control, evaluation, API hardening, and a React chat interface.

## Highlights

- Vietnamese legal question understanding with deterministic query analysis and retrieval-aware intent signals.
- Legal document processing for civil code, decrees, resolutions, and case law.
- Metadata-aware chunking with citations, source type, legal role, validity fields, and document relationships.
- Hybrid retrieval using metadata, lexical matching, vector retrieval, reranking, and fallback logic.
- Grounded generation with evidence IDs, citation validation, confidence signals, and hallucination controls.
- Evaluation suite covering citation recall, answer terms, source type recall, grounding coverage, abstention, latency, and LLM-as-a-judge metrics.
- FastAPI backend with request IDs, rate limiting, request size limit, security headers, CORS config, Prometheus instrumentation, and API key support.
- React/Vite frontend with streaming chat UI, citations, feedback, and configurable API base URL.

## Architecture

```mermaid
flowchart LR
    A[Raw Legal Documents<br/>DOCX/PDF] --> B[Ingestion]
    B --> C[Parser + Cleaner]
    C --> D[Metadata Builder]
    D --> E[Legal Chunker]
    E --> F[Embedding Builder]
    F --> G[Qdrant Vector Store]

    U[User Question] --> FE[React Frontend]
    FE --> API[FastAPI Backend]
    API --> QA[Query Analyzer]
    QA --> R[Hybrid Retrieval]
    R --> G
    R --> LX[Lexical + Metadata Retrieval]
    R --> RR[Reranker]
    RR --> EB[Evidence Builder]
    EB --> GEN[Grounded Generator]
    GEN --> OUT[Answer + Citations + Confidence]
    OUT --> FE

    API --> OBS[Logs + Metrics]
    GEN --> EV[Evaluation Suite]
    R --> EV
```

For a fuller architecture explanation, see [docs/architecture.md](docs/architecture.md).

## Repository Structure

```text
backend/
  app/                 FastAPI app, API routes, middleware, database config
  ingestion/           loaders, parsers, cleaners, chunkers, metadata, embeddings, indexing
  retrieval/           query analyzer, retrievers, reranker, evidence builder
  generation/          prompt builder, rule-based/LLM generators, grounding checks
  evaluation/          datasets, evaluator, reporting, LLM judge
  scripts/             ingestion, validation, evaluation, indexing entrypoints
  tests/               regression tests for encoding, retrieval, generation, evaluation, API hardening
frontend/
  src/                 React chat app
  dist/                production build artifact
docs/
  architecture.md
  evaluation-summary.md
  cv-bullets.md
PROJECT_REPORT.md
```

## RAG Pipeline

1. **Data processing**
   - Reads raw legal documents from `backend/data/raw`.
   - Parses DOCX/PDF into structured JSON.
   - Cleans text and builds legal metadata.

2. **Chunking**
   - Uses document-type-aware chunkers.
   - Preserves article/citation metadata and legal role.

3. **Embedding and indexing**
   - Generates embeddings from chunk files.
   - Indexes embeddings into Qdrant with snapshot integrity checks.

4. **Retrieval**
   - Combines metadata retrieval, lexical retrieval, vector retrieval, reranking, and fallback.
   - Supports accent-insensitive Vietnamese matching.

5. **Generation**
   - Produces grounded legal answers with citations and evidence IDs.
   - Adds confidence signals, disclaimers, and hallucination guardrails.

6. **Evaluation**
   - Measures retrieval, generation, grounding, abstention, latency, and judge metrics.

## Backend Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Run the API:

```bash
uvicorn app.server:app --host 0.0.0.0 --port 8000
```

Run the CLI:

```bash
python -m app.main "Điều 117 Bộ luật Dân sự quy định gì?"
python -m app.main "Điều 117 Bộ luật Dân sự quy định gì?" --retrieval-only
```

## Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Default frontend API URL:

```text
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Data Pipeline Commands

From `backend/`:

```bash
python -m scripts.ingest
python -m scripts.run_chunker
python -m scripts.run_embedding
python -m scripts.run_indexing --rebuild
```

Validation commands:

```bash
python scripts/validate_encoding.py . ../frontend --include-data
python scripts/validate_chunks.py
python scripts/validate_embeddings.py
python scripts/validate_index.py
```

## Quality Checks

Backend:

```bash
cd backend
python -m pytest -q
python scripts/validate_encoding.py . ../frontend --include-data
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Current regression status:

- Backend/RAG tests: `35 passed`
- Encoding validation: passed
- Frontend lint: passed
- Frontend build: passed

## Evaluation

Run deterministic evaluation:

```bash
cd backend
python scripts/evaluate_system.py --dataset evaluation/datasets/legal_rag_eval_v2.json --no-llm-judge --json
```

Enable LLM-as-a-judge:

```bash
python scripts/evaluate_system.py --dataset evaluation/datasets/legal_rag_eval_v2.json --with-llm-judge
```

LLM judge is disabled by default through:

```text
LLM_JUDGE_ENABLED=false
```

See [docs/evaluation-summary.md](docs/evaluation-summary.md) for the current evaluation summary and limitations.

## Security and Production Hardening

The backend includes:

- API key enforcement in production.
- Configurable CORS.
- Request body size limit.
- Redis token bucket rate limiting with in-memory fallback.
- Request IDs.
- Security headers.
- Redacted structured logging.
- Prometheus metrics endpoint.
- Health check endpoint.

## Limitations

- Full end-to-end benchmark can be slow because it loads local reranker/model resources.
- The project is suitable for portfolio, demo, staging, or internal pilot usage, not direct legal advice in public production.
- Legal corpus update, legal review workflow, monitoring dashboards, and CI/CD deployment gates still need to be added for production-grade use.

## Portfolio Value

This project showcases:

- Legal-domain RAG system design.
- Vietnamese NLP handling.
- Hybrid retrieval and metadata-aware search.
- Grounded generation and hallucination control.
- Evaluation-driven AI engineering.
- Backend/frontend integration and production hardening.

Suggested CV bullets are available in [docs/cv-bullets.md](docs/cv-bullets.md).
