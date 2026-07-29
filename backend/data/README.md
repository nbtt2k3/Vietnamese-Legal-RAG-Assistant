# Backend Data Policy

This directory is mostly local/generated data for the Legal RAG pipeline.

Tracked in git:

- `source_registry.json`: source governance metadata used to verify documents.
- `README.md`: this data policy.

Not tracked in git:

- `raw/`: local DOCX/PDF legal corpus files.
- `parsed/`, `cleaned/`, `metadata/`, `chunks/`: generated ingestion artifacts.
- `embeddings/`: generated vector payloads.
- `manifests/`, `manifest_fallbacks/`: generated pipeline run manifests.
- `models/`: downloaded local model/cache files.
- `qdrant_db/`: local Qdrant storage.
- `*.db`, `*.sqlite`, `*.sqlite3`: local application databases.

Regenerate ignored artifacts from the scripts in `backend/scripts/`.
