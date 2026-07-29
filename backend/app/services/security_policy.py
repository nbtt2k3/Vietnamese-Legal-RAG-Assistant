import re


INJECTION_PATTERNS = [
    re.compile(r"bo\s*qua\s*cac\s*lenh"),
    re.compile(r"bỏ\s*qua\s*các\s*lệnh"),
    re.compile(r"ignore\s*previous\s*instructions"),
    re.compile(r"hay\s*dong\s*vai"),
    re.compile(r"hãy\s*đóng\s*vai"),
    re.compile(r"act\s*as\s*"),
    re.compile(r"system\s*prompt"),
    re.compile(r"tiet\s*lo\s*huong\s*dan"),
    re.compile(r"tiết\s*lộ\s*hướng\s*dẫn"),
    re.compile(r"quen\s*tat\s*ca"),
    re.compile(r"quên\s*tất\s*cả"),
]


def detect_prompt_injection(query: str) -> re.Pattern | None:
    query_lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if pattern.search(query_lower):
            return pattern
    return None


def sanitize_log_value(value: object, max_length: int = 500) -> str:
    text = str(value or "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length - 3]}..."
