from pathlib import Path

from scripts.validate_encoding import validate_roots


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_source_files_are_utf8_without_common_mojibake_tokens():
    errors = validate_roots([PROJECT_ROOT / "backend", PROJECT_ROOT / "frontend"])
    assert errors == []


def test_representative_vietnamese_strings_are_stored_correctly():
    checks = {
        PROJECT_ROOT / "backend" / "rag" / "retrieval" / "rule_analyzer.py": [
            "Điều 5",
            "thế chấp",
            "hiệu lực giao dịch",
        ],
        PROJECT_ROOT / "backend" / "rag" / "generation" / "prompt_builder.py": [
            "Trả lời câu hỏi pháp lý Việt Nam",
            "Không bịa thêm căn cứ ngoài context",
        ],
        PROJECT_ROOT / "frontend" / "src" / "ChatPage.jsx": [
            "Xin chào",
        ],
        PROJECT_ROOT / "frontend" / "src" / "components" / "MessageBubble.jsx": [
            "Trợ lý Pháp lý AI",
        ],
    }

    for path, expected_strings in checks.items():
        text = path.read_text(encoding="utf-8")
        for expected in expected_strings:
            assert expected in text
