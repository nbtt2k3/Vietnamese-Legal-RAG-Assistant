"""Snapshot and integrity helpers for ingestion artifacts."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.core.config import settings

MANIFEST_DIR = settings.data_dir / "manifests"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return _digest(path.read_bytes())


def directory_inventory(root: Path) -> dict[str, Any]:
    """Fingerprint arbitrary files without assuming a chunk JSON schema."""
    files = [path for path in sorted(root.rglob("*")) if path.is_file()]
    return {
        "root": root.as_posix(),
        "file_count": len(files),
        "files": [
            {"path": path.relative_to(root).as_posix(), "sha256": file_sha256(path)}
            for path in files
        ],
    }


def _read_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("expected a JSON list")
    return payload


def json_inventory(root: Path, require_embedding: bool = False) -> dict[str, Any]:
    """Return a deterministic, auditable inventory for JSON artifacts."""
    records: list[dict[str, Any]] = []
    chunk_ids: list[str] = []
    invalid: list[str] = []

    for path in sorted(root.rglob("*.json")):
        try:
            rows = _read_rows(path)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            invalid.append(f"{path}: {exc}")
            continue
        file_ids: list[str] = []
        for row in rows:
            chunk_id = row.get("chunk_id") if isinstance(row, dict) else None
            if not chunk_id:
                invalid.append(f"{path}: missing chunk_id")
                continue
            if require_embedding and not row.get("embedding"):
                invalid.append(f"{path}: {chunk_id} has no embedding")
                continue
            file_ids.append(str(chunk_id))
            chunk_ids.append(str(chunk_id))
        records.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": file_sha256(path),
            "rows": len(rows),
            "chunk_id_digest": _digest("\n".join(sorted(file_ids)).encode("utf-8")),
        })

    unique_ids = sorted(set(chunk_ids))
    duplicates = sorted(item for item, count in Counter(chunk_ids).items() if count > 1)
    return {
        "root": root.as_posix(),
        "files": records,
        "row_count": len(chunk_ids),
        "unique_chunk_count": len(unique_ids),
        "chunk_id_digest": _digest("\n".join(unique_ids).encode("utf-8")),
        "duplicate_chunk_ids": duplicates,
        "invalid_records": invalid,
    }


def _chunk_ids(root: Path, require_embedding: bool = False) -> set[str]:
    result: set[str] = set()
    for path in root.rglob("*.json"):
        try:
            rows = _read_rows(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        for row in rows:
            if not isinstance(row, dict) or (require_embedding and not row.get("embedding")):
                continue
            if row.get("chunk_id"):
                result.add(str(row["chunk_id"]))
    return result


def compare_qdrant_chunks(chunks_dir: Path, db_path: Path, collection_name: str) -> dict[str, Any]:
    """Compare indexed payload chunk IDs with the current chunk snapshot.

    Use the configured remote Qdrant service when QDRANT_URL is set. This is
    important in Docker: the mounted ``data/qdrant_db`` directory is only a
    local artifact and is not the Qdrant server's active storage backend.
    """
    from qdrant_client import QdrantClient

    expected_ids = _chunk_ids(chunks_dir)
    qdrant_target = settings.qdrant_url or str(db_path)
    client = None
    try:
        if settings.qdrant_url:
            client_kwargs = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                client_kwargs["api_key"] = settings.qdrant_api_key
            client = QdrantClient(**client_kwargs)
        else:
            client = QdrantClient(path=str(db_path))
    except Exception as exc:
        return {
            "collection_exists": False,
            "indexed_count": 0,
            "missing_indexed": sorted(expected_ids),
            "orphan_indexed": [],
            "is_consistent": False,
            "status": "unavailable",
            "qdrant_target": qdrant_target,
            "error": str(exc),
        }
    try:
        indexed_ids: set[str] = set()
        offset = None
        try:
            while True:
                points, offset = client.scroll(
                    collection_name=collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=["chunk_id"],
                    with_vectors=False,
                )
                indexed_ids.update(
                    str(point.payload.get("chunk_id"))
                    for point in points
                    if point.payload and point.payload.get("chunk_id")
                )
                if offset is None:
                    break
        except Exception as exc:
            return {
                "collection_exists": False,
                "indexed_count": 0,
                "missing_indexed": sorted(expected_ids),
                "orphan_indexed": [],
                "is_consistent": False,
                "status": "unavailable",
                "qdrant_target": qdrant_target,
                "error": str(exc),
            }
    finally:
        if client is not None:
            client.close()

    missing = sorted(expected_ids - indexed_ids)
    orphan = sorted(indexed_ids - expected_ids)
    return {
        "collection_exists": True,
        "indexed_count": len(indexed_ids),
        "missing_indexed": missing,
        "orphan_indexed": orphan,
        "is_consistent": not missing and not orphan and len(indexed_ids) == len(expected_ids),
        "status": "ok",
        "qdrant_target": qdrant_target,
    }


def compare_chunk_sets(chunks_dir: Path, embeddings_dir: Path) -> dict[str, Any]:
    chunks = json_inventory(chunks_dir)
    embeddings = json_inventory(embeddings_dir, require_embedding=True)
    chunk_ids = _chunk_ids(chunks_dir)
    embedding_ids = _chunk_ids(embeddings_dir, require_embedding=True)
    missing = sorted(chunk_ids - embedding_ids)
    orphan = sorted(embedding_ids - chunk_ids)
    return {
        "chunks": chunks,
        "embeddings": embeddings,
        "missing_embeddings": missing,
        "orphan_embeddings": orphan,
        "is_consistent": not (
            chunks["invalid_records"] or embeddings["invalid_records"]
            or chunks["duplicate_chunk_ids"] or embeddings["duplicate_chunk_ids"]
            or missing or orphan
        ),
    }


def write_manifest(stage: str, inputs: dict[str, Any], outputs: dict[str, Any], metadata: dict[str, Any] | None = None) -> Path:
    """Persist the exact artifact snapshot produced by a stage."""
    payload = {
        "schema_version": 1,
        "stage": stage,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "outputs": outputs,
        "metadata": metadata or {},
    }
    manifest_json = json.dumps(payload, ensure_ascii=False, indent=2)

    try:
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        path = MANIFEST_DIR / f"{stage}_latest.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(manifest_json, encoding="utf-8")
        temp_path.replace(path)
        return path
    except PermissionError:
        fallback_dir = settings.data_dir / "manifest_fallbacks"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        fallback_path = fallback_dir / f"{stage}_latest.json"
        fallback_path.write_text(manifest_json, encoding="utf-8")
        return fallback_path
