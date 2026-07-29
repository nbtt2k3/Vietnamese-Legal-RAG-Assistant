from __future__ import annotations

from ingestion.source_registry import load_source_registry
from rag.retrieval.text_utils import normalize_for_match


SOURCE_TYPE_PHRASES = {
    "bo_luat": ("bo luat", "luat"),
    "nghi_dinh": ("nghi dinh",),
    "nghi_quyet": ("nghi quyet",),
    "thong_tu": ("thong tu",),
    "an_le": ("an le",),
}


def infer_source_type(entry: dict) -> str:
    explicit = str(entry.get("loai_van_ban") or entry.get("source_type") or "").strip()
    if explicit:
        return explicit
    source_file = str(entry.get("source_file", "")).replace("\\", "/")
    if "/" in source_file:
        return source_file.split("/", 1)[0]
    return ""


def source_types_from_text(text: str) -> set[str]:
    normalized = normalize_for_match(text)
    return {
        source_type
        for source_type, phrases in SOURCE_TYPE_PHRASES.items()
        if any(phrase in normalized for phrase in phrases)
    }


def resolve_document_ids(text: str, registry: dict | None = None) -> set[str]:
    normalized = normalize_for_match(text)
    registry_data = registry if registry is not None else load_source_registry()
    matched: set[str] = set()

    for entry in registry_data.get("documents", []):
        if not isinstance(entry, dict):
            continue
        doc_id = str(entry.get("doc_id", "")).strip()
        if not doc_id:
            continue

        candidates = _document_match_terms(entry)
        if any(term and term in normalized for term in candidates):
            matched.add(doc_id)

    return matched


def _document_match_terms(entry: dict) -> set[str]:
    terms: set[str] = set()
    for key in ("official_number", "so_hieu", "document_title", "ten"):
        value = str(entry.get(key, "")).strip()
        if value:
            terms.add(normalize_for_match(value))

    for alias in entry.get("aliases", []) or []:
        value = str(alias).strip()
        if value:
            terms.add(normalize_for_match(value))

    return {term for term in terms if term}
