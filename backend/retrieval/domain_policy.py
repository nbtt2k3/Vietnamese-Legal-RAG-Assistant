from retrieval.models import QueryIntent, RetrievedChunk
from retrieval.text_utils import normalize_for_match


CRIMINAL_TERMS = {
    "hinh su",
    "pham toi",
    "toi pham",
    "trom cap",
    "an trom",
    "hinh phat",
    "tu",
    "mien trach nhiem hinh su",
}

CIVIL_SECURITY_TERMS = {
    "the chap",
    "bao dam",
    "hop dong",
    "giao dich",
    "quyen dinh doat",
    "ngan hang",
    "ben mua",
    "ben ban",
    "thanh toan",
    "so do",
    "dat",
    "nha",
}


def is_scenario_domain_compatible(item: RetrievedChunk, query_intent: QueryIntent) -> bool:
    if query_intent.loai_yeu_cau != "scenario_application":
        return True

    query_text = normalize_for_match(
        " ".join(
            [
                query_intent.normalized_query,
                *query_intent.key_phrases,
                *query_intent.scenario_terms,
                *query_intent.keywords,
            ]
        )
    )
    tags = {normalize_for_match(str(tag)) for tag in item.metadata.get("legal_domain_tags", []) or []}
    title = normalize_for_match(str(item.metadata.get("ten", "")))
    doc_id = normalize_for_match(item.doc_id)
    candidate_text = " ".join([*tags, title, doc_id])

    if _has_any(query_text, CRIMINAL_TERMS):
        return "hinh su" in candidate_text
    if not _has_any(query_text, CIVIL_SECURITY_TERMS):
        return True

    if "hinh su" not in candidate_text:
        return True

    civil_tags = {"dan su", "hop dong", "bao dam", "tai san", "dat dai"}
    return bool(tags & civil_tags) and "bo luat hinh su" not in title


def _has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)
