"""Validate official-source governance metadata before indexing or deployment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.source_registry import audit_source_registry, load_source_registry


def validate_source_registry_file(path: Path, require_documents: bool = True) -> list[dict]:
    try:
        registry = load_source_registry(str(path))
    except (json.JSONDecodeError, ValueError) as exc:
        return [{"code": "invalid_source_registry", "path": str(path), "message": str(exc)}]

    issues = audit_source_registry(registry)
    if require_documents and not registry.get("documents"):
        issues.append({"code": "empty_source_registry", "path": str(path)})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate source registry official evidence and validity metadata.")
    parser.add_argument("--path", default="data/source_registry.json", help="Path to source_registry.json")
    parser.add_argument("--allow-empty", action="store_true", help="Allow an empty registry")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()

    path = Path(args.path)
    issues = validate_source_registry_file(path, require_documents=not args.allow_empty)

    if args.json:
        print(json.dumps({"path": str(path), "issues": issues}, ensure_ascii=False, indent=2))
    elif issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
    else:
        print("Source registry validation passed.")

    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
