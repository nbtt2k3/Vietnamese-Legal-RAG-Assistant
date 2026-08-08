from __future__ import annotations

import re
import unicodedata


def strip_vietnamese_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").casefold()
    text = strip_vietnamese_accents(text)
    return re.sub(r"\s+", " ", text).strip()


def contains_normalized(haystack: str, needle: str) -> bool:
    normalized_needle = normalize_for_match(needle)
    if not normalized_needle:
        return False
    normalized_haystack = normalize_for_match(haystack)
    if re.search(
        rf"(?<!\w){re.escape(normalized_needle)}(?!\w)",
        normalized_haystack,
        flags=re.UNICODE,
    ):
        return True

    needle_tokens = re.findall(r"[\w]+", normalized_needle, flags=re.UNICODE)
    if not needle_tokens:
        return False
    haystack_tokens = set(re.findall(r"[\w]+", normalized_haystack, flags=re.UNICODE))
    return all(token in haystack_tokens for token in needle_tokens)


def citation_matches(observed: str, expected: str) -> bool:
    """Match citations when a long document title is inserted in the middle."""
    observed_normalized = normalize_for_match(observed)
    expected_normalized = normalize_for_match(expected)
    if not observed_normalized or not expected_normalized:
        return False
    if _bounded_contains(observed_normalized, expected_normalized) or _bounded_contains(
        expected_normalized, observed_normalized
    ):
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
    return bool(expected_documents or expected_articles or expected_clauses)


def _bounded_contains(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack, flags=re.UNICODE))


def tokenize_for_bm25(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text or "").casefold()
    tokens = re.findall(r"[\wÀ-ỹĐđ]+", normalized, flags=re.UNICODE)
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        variants = [token, strip_vietnamese_accents(token)]
        for variant in variants:
            if len(variant) < 2 or variant in seen:
                continue
            expanded.append(variant)
            seen.add(variant)
    return expanded
