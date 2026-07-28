# Corpus Governance

This project treats legal corpus updates as a controlled data change, not a code feature.

## Required Evidence

Every document promoted beyond local experimentation must have an entry in:

```text
backend/data/source_registry.json
```

Required fields for an officially verified source:

- `doc_id`
- `loai_van_ban`
- `official_number`
- `document_title`
- `aliases`
- `source_file`
- `source_checksum_sha256`
- `source_name`
- `source_url`
- `source_verified_at`
- `source_verification_status=official_verified`

Validity metadata can override parsed validity only when the registry also includes:

- `validity_status`
- `source_of_validity`
- `validity_basis`
- `validity_confidence=high`
- `validity_checked_at`

Accepted official validity sources are enforced in `backend/ingestion/source_registry.py`.

`aliases` must be a list of natural names users may type, such as `Bộ luật Dân sự`, `BLDS 2015`, or `Nghị định 21/2021/NĐ-CP`. Exact retrieval constraints resolve document IDs from this registry metadata. Do not add document-ID constants directly inside retrieval code.

## Update Workflow

1. Add the raw legal document under the correct `backend/data/raw` domain/type path.
2. Record the official source, checksum, document type, official number, and aliases in `backend/data/source_registry.json`.
3. Run source registry validation:

```bash
cd backend
python scripts/validate_source_registry.py --path data/source_registry.json
```

4. Run the ingestion pipeline:

```bash
python -m scripts.ingest
python -m scripts.run_chunker
python -m scripts.run_embedding
python -m scripts.run_indexing --rebuild
```

5. Run integrity and regression checks:

```bash
python scripts/validate_data_integrity.py
python -m pytest -q
```

6. Add or update evaluation cases for the changed legal area.
7. Do not claim official validity for documents that only have parsed text evidence.

## Expansion Rule

Adding Criminal, Land, Labor, Enterprise, Tax, or other legal domains should be done by adding corpus files, source registry entries, metadata/rules when needed, and evaluation cases. The retrieval and generation core should not require code changes unless the new document structure is genuinely unsupported by existing parsers/chunkers.
