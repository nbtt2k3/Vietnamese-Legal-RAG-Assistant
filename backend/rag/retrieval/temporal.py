"""Temporal compatibility helpers shared by all retrieval stages."""

from __future__ import annotations

from datetime import date
import re

from rag.retrieval.models import QueryIntent, RetrievedChunk
from rag.retrieval.text_utils import normalize_for_match

ACTIVE_STATUSES = {
    "dang_co_hieu_luc",
    "co_ngay_hieu_luc",
    "co_hieu_luc_va_thay_the_van_ban_khac",
}
EXPIRED_STATUSES = {
    "het_hieu_luc",
    "bi_bai_bo",
    "an_le_bi_bai_bo",
}


def _year(value: object) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    return int(match.group(0)) if match else None


def query_year(query_intent: QueryIntent) -> int | None:
    return _year(query_intent.time_context.get("year_hint")) or _year(query_intent.raw_query)


def allows_historical(query_intent: QueryIntent) -> bool:
    text = normalize_for_match(
        " ".join(
            [
                query_intent.raw_query,
                query_intent.normalized_query,
                *query_intent.key_phrases,
                *query_intent.keywords,
            ]
        )
    )
    return bool(query_year(query_intent)) or any(
        term in text
        for term in (
            "het hieu luc",
            "thay the",
            "van ban cu",
            "truoc khi",
            "tai thoi diem",
            "lich su",
        )
    )


def temporal_state(metadata: dict, query_intent: QueryIntent, today: date | None = None) -> str:
    today = today or date.today()
    status = normalize_for_match(str(metadata.get("validity_status", "")))
    if status in {normalize_for_match(item) for item in EXPIRED_STATUSES}:
        return "expired"

    target_year = query_year(query_intent)
    start_year = _year(metadata.get("effective_from") or metadata.get("ngay_hieu_luc") or metadata.get("effective_date"))
    end_year = _year(metadata.get("effective_to"))
    if target_year:
        if start_year and target_year < start_year:
            return "not_yet_effective"
        if end_year and target_year > end_year:
            return "expired"
    else:
        if start_year and start_year > today.year:
            return "not_yet_effective"
        if end_year and end_year < today.year:
            return "expired"

    if status in {normalize_for_match(item) for item in ACTIVE_STATUSES}:
        return "active"
    if start_year or end_year:
        return "dated_unknown"
    return "unknown"


def temporal_adjustment(metadata: dict, query_intent: QueryIntent) -> tuple[str, float]:
    state = temporal_state(metadata, query_intent)
    historical = allows_historical(query_intent)
    if state == "active":
        return state, 1.0 if not historical else 0.2
    if state == "expired":
        return state, 0.0 if historical else -5.0
    if state == "not_yet_effective":
        return state, -5.0
    if state == "dated_unknown":
        # Án lệ thường không có validity_status/effective_to giống văn bản
        # quy phạm. Không phạt loại nguồn này trong câu hỏi tình huống; nếu
        # không, Điều luật có metadata hiệu lực sẽ luôn đẩy án lệ xuống dưới.
        if metadata.get("document_role") == "case_law":
            return state, 0.0
        return state, -0.4
    if state == "unknown" and metadata.get("document_role") == "case_law":
        return state, 0.0
    return state, -0.8


def _identity(metadata: dict, doc_id: str) -> str:
    return str(metadata.get("so_hieu") or metadata.get("ten") or doc_id).strip().lower()


def _normalized(value: object) -> str:
    return normalize_for_match(str(value or "")).replace("-", " ").strip()


def resolve_temporal_conflicts(
    query_intent: QueryIntent,
    ranked: list[RetrievedChunk],
) -> tuple[list[RetrievedChunk], dict[str, object]]:
    """Prefer applicable current instruments over superseded ones.

    Historical queries retain expired documents, while current queries remove
    expired candidates only when a compatible active replacement is present.
    """
    if not ranked:
        return [], {"conflict_detected": False, "temporal_states": {}}

    states: dict[str, str] = {}
    replacement_targets: set[str] = set()
    for item in ranked:
        state, adjustment = temporal_adjustment(item.metadata, query_intent)
        states[item.chunk_id] = state
        item.metadata["temporal_state"] = state
        item.scores["temporal"] = adjustment
        for target in item.metadata.get("replaced_documents", []) or []:
            replacement_targets.add(_normalized(target))
        for relation in item.metadata.get("related_documents", []) or []:
            if relation.get("relation_type") in {"replaces_or_terminates", "replaces", "sua_doi"}:
                replacement_targets.add(_normalized(relation.get("target_doc")))

    active_identities = {
        _identity(item.metadata, item.doc_id)
        for item in ranked
        if states.get(item.chunk_id) == "active"
    }
    # Only treat an expired source as superseded when the active result
    # explicitly names it. A generic active result must not hide an unrelated
    # historical instrument that happens to be in the same retrieval set.
    explicitly_replaced = {
        target
        for target in replacement_targets
        if target
    }
    conflict_detected = False
    historical = allows_historical(query_intent)
    for item in ranked:
        identity = _identity(item.metadata, item.doc_id)
        if states.get(item.chunk_id) == "expired" and not historical:
            if identity in explicitly_replaced:
                item.metadata["conflict_resolution"] = "superseded_or_expired"
                item.scores["temporal"] = -8.0
                conflict_detected = True
        elif states.get(item.chunk_id) == "active":
            # Active sources already receive the normal temporal score above.
            # Do not add a global bonus merely because another candidate has
            # a replacement relation; that relation may concern a different
            # document and would distort unrelated queries.
            if identity in explicitly_replaced:
                item.metadata["conflict_resolution"] = "preferred_current_source"

    ranked.sort(
        key=lambda item: item.scores.get("final", 0.0) + item.scores.get("temporal", 0.0),
        reverse=True,
    )
    if not historical:
        active_or_unknown = [item for item in ranked if states.get(item.chunk_id) != "expired"]
        if active_or_unknown:
            ranked = active_or_unknown
    return ranked, {
        "conflict_detected": conflict_detected,
        "temporal_states": states,
        "historical_query": historical,
    }
