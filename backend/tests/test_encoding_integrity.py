from pathlib import Path

from scripts.validate_encoding import validate_roots


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if (PROJECT_ROOT / "backend").is_dir():
    BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


def test_source_files_are_utf8_without_common_mojibake_tokens():
    roots = [BACKEND_ROOT]
    if FRONTEND_ROOT.is_dir():
        roots.append(FRONTEND_ROOT)
    errors = validate_roots(roots)
    assert errors == []


def test_representative_vietnamese_strings_are_stored_correctly():
    checks = {
        BACKEND_ROOT / "rag" / "retrieval" / "rule_analyzer.py": [
            "Điều 5",
            "thế chấp",
            "hiệu lực giao dịch",
        ],
        BACKEND_ROOT / "rag" / "generation" / "prompt_builder.py": [
            "Trả lời câu hỏi pháp lý Việt Nam",
            "Không bịa thêm căn cứ ngoài context",
        ],
    }
    if FRONTEND_ROOT.is_dir():
        checks.update({
            FRONTEND_ROOT / "src" / "ChatPage.jsx": ["Xin chào"],
            FRONTEND_ROOT / "src" / "components" / "MessageBubble.jsx": [
                "Trợ lý Pháp lý AI",
            ],
        })

    for path, expected_strings in checks.items():
        text = path.read_text(encoding="utf-8")
        for expected in expected_strings:
            assert expected in text
