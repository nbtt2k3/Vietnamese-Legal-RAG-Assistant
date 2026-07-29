import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


OFFICIAL_VERIFICATION_STATUS = "official_verified"
LOCAL_SOURCE_STATUS = "local_checksum_only"
REGISTRY_FILE = "source_registry.json"
OFFICIAL_VALIDITY_SOURCES = {
    "official_registry",
    "csdl_quoc_gia_vbpl",
    "cong_bao_chinh_phu",
    "csdl_an_le_tandtc",
}
SOURCE_FIELDS = (
    "source_name",
    "source_url",
    "source_verified_at",
    "source_verification_status",
)
VALIDITY_FIELDS = (
    "source_of_validity",
    "validity_status",
    "validity_basis",
    "validity_confidence",
    "validity_checked_at",
    "effective_from",
    "effective_to",
    "repeal_reason",
)


def _default_registry_path() -> Path:
    return settings.data_dir / REGISTRY_FILE


@lru_cache(maxsize=4)
def load_source_registry(path: str | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else _default_registry_path()
    if not registry_path.exists():
        return {"documents": []}

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"documents": data}
    if not isinstance(data, dict):
        raise ValueError("source registry must be a JSON object or a list of documents")
    documents = data.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("source registry field 'documents' must be a list")
    return {"documents": documents}


def apply_source_registry(
    source_metadata: dict[str, Any],
    *,
    doc_id: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(source_metadata)
    registry_data = registry if registry is not None else load_source_registry()
    entry = _find_registry_entry(registry_data.get("documents", []), source_metadata, doc_id)
    if not entry:
        enriched["source_registry_status"] = "not_found"
        return enriched

    if not _checksum_matches(entry, source_metadata):
        enriched["source_registry_status"] = "checksum_mismatch"
        return enriched

    if entry.get("source_verification_status") == OFFICIAL_VERIFICATION_STATUS:
        if not _official_source_evidence_complete(entry):
            enriched["source_registry_status"] = "incomplete_official_evidence"
            return enriched

    enriched["source_registry_status"] = "matched"
    for key in SOURCE_FIELDS:
        if entry.get(key) is not None:
            enriched[key] = entry[key]

    if _official_validity_evidence_complete(entry):
        for key in VALIDITY_FIELDS:
            if entry.get(key) is not None:
                enriched[key] = entry[key]

    return enriched


def enrich_metadata_from_source_registry(
    metadata: dict[str, Any],
    *,
    doc_id: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not metadata.get("source_checksum_sha256") and not metadata.get("source_file"):
        return metadata
    return apply_source_registry(metadata, doc_id=doc_id, registry=registry)


def audit_source_registry(registry: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    documents = registry.get("documents", [])
    seen_doc_ids: set[str] = set()

    for index, entry in enumerate(documents):
        if not isinstance(entry, dict):
            issues.append({"index": index, "code": "invalid_entry_type"})
            continue

        doc_id = entry.get("doc_id")
        if not doc_id:
            issues.append({"index": index, "code": "missing_doc_id"})
        elif doc_id in seen_doc_ids:
            issues.append({"index": index, "doc_id": doc_id, "code": "duplicate_doc_id"})
        else:
            seen_doc_ids.add(doc_id)

        if entry.get("source_verification_status") == OFFICIAL_VERIFICATION_STATUS:
            if not _official_source_evidence_complete(entry):
                issues.append({"index": index, "doc_id": doc_id, "code": "incomplete_official_source"})
            if _has_any_validity_field(entry) and not _official_validity_evidence_complete(entry):
                issues.append({"index": index, "doc_id": doc_id, "code": "incomplete_official_validity"})
        if "aliases" in entry and not isinstance(entry.get("aliases"), list):
            issues.append({"index": index, "doc_id": doc_id, "code": "invalid_aliases"})

    return issues


def _find_registry_entry(
    documents: list[dict[str, Any]],
    source_metadata: dict[str, Any],
    doc_id: str,
) -> dict[str, Any] | None:
    source_file = source_metadata.get("source_file")
    checksum = source_metadata.get("source_checksum_sha256")
    for entry in documents:
        if not isinstance(entry, dict):
            continue
        if entry.get("doc_id") and entry.get("doc_id") == doc_id:
            return entry
        if entry.get("source_file") and entry.get("source_file") == source_file:
            return entry
        if entry.get("source_checksum_sha256") and entry.get("source_checksum_sha256") == checksum:
            return entry
    return None


def _checksum_matches(entry: dict[str, Any], source_metadata: dict[str, Any]) -> bool:
    expected = entry.get("source_checksum_sha256")
    actual = source_metadata.get("source_checksum_sha256")
    return not expected or expected == actual


def _official_source_evidence_complete(entry: dict[str, Any]) -> bool:
    return bool(
        entry.get("source_checksum_sha256")
        and entry.get("source_url")
        and entry.get("source_verified_at")
    )


def _official_validity_evidence_complete(entry: dict[str, Any]) -> bool:
    source = str(entry.get("source_of_validity", "")).strip()
    return bool(
        entry.get("source_verification_status") == OFFICIAL_VERIFICATION_STATUS
        and source in OFFICIAL_VALIDITY_SOURCES
        and entry.get("validity_status")
        and entry.get("validity_basis")
        and entry.get("validity_checked_at")
        and str(entry.get("validity_confidence", "")).strip().lower() == "high"
    )


def _has_any_validity_field(entry: dict[str, Any]) -> bool:
    return any(entry.get(key) is not None for key in VALIDITY_FIELDS)
