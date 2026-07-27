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


def best_match_ratio(observed_items: list[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0
    hits = 0
    for expected in expected_items:
        if any(
            contains_normalized(observed, expected) or contains_normalized(expected, observed)
            for observed in observed_items
        ):
            hits += 1
    return hits / max(1, len(expected_items))


def confidence_at_least(observed: str, minimum: str) -> bool:
    return CONFIDENCE_LEVEL_MAP.get(observed, 0) >= CONFIDENCE_LEVEL_MAP.get(minimum, 0)
