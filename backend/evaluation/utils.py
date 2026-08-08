import re
import unicodedata


CONFIDENCE_LEVEL_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^a-z0-9/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_normalized(haystack: str, needle: str) -> bool:
    return normalize_text(needle) in normalize_text(haystack)


def citation_matches(observed: str, expected: str) -> bool:
    """Match citations even when a display title is inserted in the middle.

    Example: the expected value may be ``Nghị định 21/2021/NĐ-CP, Điều 7``
    while the indexed citation is rendered as ``Nghị định 21/2021/NĐ-CP -
    <long title>, Điều 7, Khoản 3``. Plain substring matching treats this as
    a miss although the document and article are identical.
    """
    observed_normalized = normalize_text(observed)
    expected_normalized = normalize_text(expected)
    if not observed_normalized or not expected_normalized:
        return False
    if expected_normalized in observed_normalized or observed_normalized in expected_normalized:
        return True

    document_pattern = r"\b\d+/\d{4}/[a-z0-9-]+\b"
    article_pattern = r"\bdieu\s+(\d+[a-z]?)\b"
    clause_pattern = r"\bkhoan\s+(\d+)\b"
    expected_documents = set(re.findall(document_pattern, expected_normalized))
    observed_documents = set(re.findall(document_pattern, observed_normalized))
    expected_articles = set(re.findall(article_pattern, expected_normalized))
    observed_articles = set(re.findall(article_pattern, observed_normalized))
    expected_clauses = set(re.findall(clause_pattern, expected_normalized))
    observed_clauses = set(re.findall(clause_pattern, observed_normalized))

    if expected_documents and not expected_documents & observed_documents:
        return False
    if expected_articles and not expected_articles <= observed_articles:
        return False
    if expected_clauses and not expected_clauses <= observed_clauses:
        return False
    return bool(expected_documents or expected_articles or expected_clauses) and (
        not expected_documents or bool(expected_documents & observed_documents)
    )


def best_match_ratio(observed_items: list[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0
    hits = 0
    for expected in expected_items:
        if any(
            citation_matches(observed, expected)
            for observed in observed_items
        ):
            hits += 1
    return hits / max(1, len(expected_items))


def confidence_at_least(observed: str, minimum: str) -> bool:
    return CONFIDENCE_LEVEL_MAP.get(observed, 0) >= CONFIDENCE_LEVEL_MAP.get(minimum, 0)
