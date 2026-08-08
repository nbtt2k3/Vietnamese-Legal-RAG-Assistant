import re

from rag.retrieval.document_resolver import resolve_document_ids, source_types_from_text
from rag.retrieval.models import QueryIntent
from rag.retrieval.text_utils import contains_normalized, normalize_for_match


def exact_constraints(query_intent: QueryIntent) -> dict[str, set[str]]:
    haystack = normalize_for_match(
        " ".join([query_intent.raw_query, query_intent.normalized_query, *query_intent.citation_targets])
    )
    references = re.findall(r"(?:khoan\s+(\d+)\s+)?dieu\s+(\d+[a-z]?)\b", haystack)
    article_numbers = {article for _, article in references}
    clause_numbers = {clause for clause, _ in references if clause}

    doc_ids = resolve_document_ids(haystack)
    source_types = source_types_from_text(haystack)
    if article_numbers and any(token in haystack for token in ("dan su", "hinh su")):
        source_types.add("bo_luat")

    return {
        "article_numbers": article_numbers,
        "clause_numbers": clause_numbers,
        "doc_ids": doc_ids,
        "source_types": source_types,
    }


def article_matches(payload: dict, article_numbers: set[str]) -> bool:
    if not article_numbers:
        return True

    payload_article = normalize_for_match(str(payload.get("dieu_number", "")))
    if payload_article in article_numbers:
        return True

    citation = str(payload.get("citation", ""))
    return any(contains_normalized(citation, f"Dieu {number}") for number in article_numbers)


def payload_matches_exact_constraints(payload: dict, constraints: dict[str, set[str]]) -> bool:
    if constraints["doc_ids"] and payload.get("doc_id") not in constraints["doc_ids"]:
        return False
    if constraints["source_types"] and payload.get("loai_van_ban") not in constraints["source_types"]:
        return False
    if not article_matches(payload, constraints["article_numbers"]):
        return False
    clause_numbers = constraints.get("clause_numbers", set())
    if clause_numbers:
        payload_clause = normalize_for_match(str(payload.get("khoan_number", "")))
        if payload_clause in clause_numbers:
            return True
        citation = str(payload.get("citation", ""))
        return any(contains_normalized(citation, f"Khoản {number}") for number in clause_numbers)
    return True
