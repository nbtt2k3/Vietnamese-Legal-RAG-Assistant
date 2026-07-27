"""
Text cleaning rules used by ingestion cleaners.
"""
import re
import unicodedata


def normalize_unicode(text: str) -> str:
    if not text:
        return text
    return unicodedata.normalize("NFC", text)


def clean_whitespace(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_punctuation(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+;", ";", text)
    text = re.sub(r"\s+:", ":", text)
    return text


NOISE_PATTERNS = [
    re.compile(r"^\s*Trang\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*Page\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*$"),
    re.compile(r"^\s*\d+\s+Án lệ này do .*$", re.IGNORECASE),
    re.compile(r"THƯ VIỆN PHÁP LUẬT", re.IGNORECASE),
    re.compile(r"VIETLAW", re.IGNORECASE),
    re.compile(r"^[-_=]{3,}$"),
]


def clean_noise(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if not any(pattern.search(line) for pattern in NOISE_PATTERNS):
            cleaned.append(line)
    return "\n".join(cleaned)


def normalize_citation(text: str) -> str:
    if not text:
        return text
    text = re.sub(r"\bĐiều\s+(\d+)\b", r"Điều \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bKhoản\s+(\d+)\b", r"Khoản \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bĐiểm\s+([a-z])\b", r"Điểm \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bChương\s+([IVXLCDM]+)\b", r"Chương \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bMục\s+(\d+)\b", r"Mục \1", text, flags=re.IGNORECASE)
    return text
