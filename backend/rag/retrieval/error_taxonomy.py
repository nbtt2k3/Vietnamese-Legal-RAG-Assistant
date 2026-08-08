"""Retrieval failure taxonomy used by evaluation and debugging."""

from __future__ import annotations

from typing import Any

from evaluation.utils import citation_matches
from rag.retrieval.text_utils import normalize_for_match


ERROR_TYPES = {
    "wrong_article",
    "wrong_document",
    "missing_related_document",
    "obsolete_document_confusion",
}


def _matches(observed: str, expected: str) -> bool:
    return citation_matches(observed, expected)


def classify_retrieval_errors(case: Any, retrieval: Any) -> list[str]:
    candidates = retrieval.candidates[:8]
    observed_citations = [str(item.metadata.get("citation", item.chunk_id)) for item in candidates]
    observed_sources = {str(item.metadata.get("loai_van_ban", "")) for item in candidates}
    expected_citations = list(getattr(case, "expected_citations", []) or [])
    expected_sources = set(getattr(case, "expected_source_types", []) or [])
    errors: list[str] = []

    matched = [expected for expected in expected_citations if any(_matches(obs, expected) for obs in observed_citations)]
    missing = [expected for expected in expected_citations if expected not in matched]
    if missing:
        if matched:
            errors.append("missing_related_document")
        elif expected_sources and observed_sources & expected_sources:
            errors.append("wrong_article")
        elif expected_citations:
            errors.append("wrong_document")

    query_text = normalize_for_match(str(getattr(case, "query", "")))
    historical = any(term in query_text for term in ("het hieu luc", "thay the", "van ban cu", "truoc khi"))
    if not historical and candidates:
        top_state = str(candidates[0].metadata.get("temporal_state", ""))
        top_status = normalize_for_match(str(candidates[0].metadata.get("validity_status", "")))
        if top_state == "expired" or top_status in {"het hieu luc", "bi bai bo", "an le bi bai bo"}:
            errors.append("obsolete_document_confusion")

    return list(dict.fromkeys(error for error in errors if error in ERROR_TYPES))
