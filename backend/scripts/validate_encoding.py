from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".css",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".py",
    ".yaml",
    ".yml",
}

DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "dist",
    "logs",
    "models",
    "node_modules",
}

MOJIBAKE_TOKEN_CODEPOINTS = (
    (0x00C4, 0x0090),
    (0x00C4, 0x2018),
    (0x00E1, 0x00BB),
    (0x00E1, 0x00BA),
    (0x00C6, 0x00A1),
    (0x00C6, 0x00B0),
    (0x00F0, 0x0178),
    (0x0043, 0x00C3, 0x00A2),
    (0x006B, 0x0068, 0x00C3, 0x00B4),
    (0x0070, 0x0068, 0x00C3, 0x00A1),
    (0x006C, 0x0075, 0x00E1, 0x00BA),
    (0x006E, 0x0067, 0x00C6, 0x00B0),
)

MOJIBAKE_TOKENS = tuple("".join(chr(codepoint) for codepoint in item) for item in MOJIBAKE_TOKEN_CODEPOINTS)


def iter_text_files(root: Path, include_data: bool = False):
    excluded = set(DEFAULT_EXCLUDED_PARTS)
    if not include_data:
        excluded.add("data")

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in DEFAULT_EXTENSIONS:
            continue
        if any(part in excluded for part in path.parts):
            continue
        yield path


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{path}: invalid UTF-8 ({exc})"]

    for token in MOJIBAKE_TOKENS:
        if token in text:
            errors.append(f"{path}: possible mojibake token {token!r}")
    return errors


def validate_roots(roots: list[Path], include_data: bool = False) -> list[str]:
    errors: list[str] = []
    seen: set[Path] = set()
    for root in roots:
        for path in iter_text_files(root, include_data=include_data):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            errors.extend(validate_file(path))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate UTF-8 source files and common mojibake tokens.")
    parser.add_argument(
        "roots",
        nargs="*",
        default=["."],
        help="Root directories to scan. Defaults to the current directory.",
    )
    parser.add_argument(
        "--include-data",
        action="store_true",
        help="Also scan generated data files. This can be slow and noisy for large corpora.",
    )
    args = parser.parse_args()

    errors = validate_roots([Path(item) for item in args.roots], include_data=args.include_data)
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Encoding validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
