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
    if normalized_needle in normalized_haystack:
        return True

    needle_tokens = re.findall(r"[\w]+", normalized_needle, flags=re.UNICODE)
    if not needle_tokens:
        return False
    haystack_tokens = set(re.findall(r"[\w]+", normalized_haystack, flags=re.UNICODE))
    return all(token in haystack_tokens for token in needle_tokens)


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
