import re

from rag.generation.models import CitationRecord
from rag.retrieval.models import RetrievedChunk

UNVERIFIED_SOURCE_STATUSES = {"", "unverified", "local_checksum_only"}
UNVERIFIED_VALIDITY_SOURCES = {"", "unverified", "unverified_parsed_text"}
UNCERTAIN_VALIDITY_STATUSES = {"", "chua_xac_dinh"}


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def snippet_from_text(text: str, max_chars: int = 240) -> str:
    snippet = clean_whitespace(text)
    if len(snippet) <= max_chars:
        return snippet
    return snippet[: max_chars - 3].rstrip() + "..."


def _page_number(value) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page > 0 else None


def chunk_to_citation(item: RetrievedChunk) -> CitationRecord:
    metadata = item.metadata
    source_location = metadata.get("source_location") or {}
    if not isinstance(source_location, dict):
        source_location = {}
    return CitationRecord(
        citation=str(metadata.get("citation", item.chunk_id)),
        snippet=snippet_from_text(item.text),
        source_type=str(metadata.get("loai_van_ban", "")),
        legal_role=str(metadata.get("legal_role", "")),
        validity_status=str(metadata.get("validity_status", "")),
        source_verification_status=str(metadata.get("source_verification_status", "")),
        source_url=str(metadata.get("source_url") or metadata.get("url") or ""),
        source_file=str(metadata.get("source_file", "")),
        source_of_validity=str(metadata.get("source_of_validity", "")),
        validity_basis=str(metadata.get("validity_basis", "")),
        validity_confidence=str(metadata.get("validity_confidence", "")),
        page_start=_page_number(
            metadata.get("page_start", source_location.get("page_start"))
        ),
        page_end=_page_number(
            metadata.get("page_end", source_location.get("page_end"))
        ),
        relevance_score=round(float(item.scores.get("final", 0.0)), 3),
        relevance_label=item.relevance_label,
        relevance_rank=item.relevance_rank,
    )


def dedupe_citations(items: list[CitationRecord], limit: int | None = None) -> list[CitationRecord]:
    deduped: list[CitationRecord] = []
    seen: set[str] = set()
    for item in items:
        key = item.citation.strip().lower()
        if not key or key in seen:
            continue
        deduped.append(item)
        seen.add(key)
        if limit is not None and len(deduped) >= limit:
            break
    return deduped


def build_source_validity_confidence(items: list[RetrievedChunk]) -> dict[str, object]:
    source_statuses = {
        str(item.metadata.get("source_verification_status", "")).strip()
        for item in items
    }
    validity_statuses = {
        str(item.metadata.get("validity_status", "")).strip()
        for item in items
    }
    validity_sources = {
        str(item.metadata.get("source_of_validity", "")).strip()
        for item in items
    }
    validity_confidences = {
        str(item.metadata.get("validity_confidence", "")).strip().lower()
        for item in items
    }

    has_unverified_source = any(status in UNVERIFIED_SOURCE_STATUSES for status in source_statuses)
    has_uncertain_validity = (
        any(status in UNCERTAIN_VALIDITY_STATUSES for status in validity_statuses)
        or any(source in UNVERIFIED_VALIDITY_SOURCES for source in validity_sources)
        or "low" in validity_confidences
    )

    return {
        "source_verification_complete": bool(items) and not has_unverified_source,
        "source_verification_statuses": sorted(source_statuses),
        "validity_verification_complete": bool(items) and not has_uncertain_validity,
        "validity_statuses": sorted(validity_statuses),
        "validity_sources": sorted(validity_sources),
        "validity_confidences": sorted(validity_confidences),
    }


def build_source_validity_disclaimers(items: list[RetrievedChunk]) -> list[str]:
    if not items:
        return []

    confidence = build_source_validity_confidence(items)
    notes = []
    if not confidence["source_verification_complete"]:
        notes.append(
            "Nguồn: Một số căn cứ hiện mới được ghi nhận từ tệp nội bộ và mã kiểm tra toàn vẹn, chưa được xác minh trực tiếp từ nguồn có thẩm quyền."
        )
    if not confidence["validity_verification_complete"]:
        notes.append(
            "Hiệu lực: Tình trạng hiệu lực của một số căn cứ được suy ra từ nội dung hệ thống đã đọc tự động hoặc chưa xác định đầy đủ; không nên coi đây là xác nhận hiệu lực chính thức."
        )
    return notes


def build_human_review_signal(
    request_type: str,
    confidence: dict[str, object],
    items: list[RetrievedChunk],
) -> dict[str, object]:
    reasons: list[str] = []

    if not items:
        reasons.append("no_retrieved_evidence")
    if confidence.get("level") == "low":
        reasons.append("low_confidence")
    if confidence.get("conflict_detected"):
        reasons.append("legal_conflict_detected")
    if confidence.get("invalid_evidence_used"):
        reasons.append("invalid_evidence_used")
    if confidence.get("claims_without_evidence"):
        reasons.append("claims_without_evidence")
    if confidence.get("weakly_supported_claims"):
        reasons.append("weakly_supported_claims")
    if confidence.get("short_answer_not_grounded"):
        reasons.append("short_answer_not_grounded")
    if confidence.get("source_verification_complete") is False:
        reasons.append("unverified_source")
    if confidence.get("validity_verification_complete") is False:
        reasons.append("unverified_validity")
    if request_type in {"scenario_application", "case_law_question"}:
        reasons.append("fact_sensitive_legal_scenario")

    deduped_reasons = list(dict.fromkeys(reasons))
    return {
        "human_review_required": bool(deduped_reasons),
        "human_review_reasons": deduped_reasons,
    }
