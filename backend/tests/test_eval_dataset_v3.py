import json
from collections import Counter
from pathlib import Path

import pytest


DATASET_PATH = Path(__file__).parents[1] / "evaluation" / "datasets" / "legal_rag_eval_v3.json"


def _load_dataset() -> dict:
    if not DATASET_PATH.exists():
        pytest.skip("Local v3 dataset artifact is generated on demand and is not tracked")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def test_v3_dataset_is_large_and_schema_valid():
    payload = _load_dataset()
    cases = payload["cases"]

    assert 200 <= len(cases) <= 500
    assert payload["case_count"] == len(cases)
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({case["query"] for case in cases}) == len(cases)

    required = {
        "case_id",
        "query",
        "tags",
        "expected_request_type",
        "expected_citations",
        "expected_source_types",
        "expected_answer_terms",
        "min_confidence_level",
    }
    assert all(required <= set(case) for case in cases)


def test_v3_contains_required_real_world_slices():
    payload = _load_dataset()
    cases = payload["cases"]
    tag_counts = Counter(tag for case in cases for tag in case["tags"])

    assert tag_counts["paraphrase"] >= 100
    assert tag_counts["unaccented"] >= 20
    assert tag_counts["insufficient_facts"] >= 20
    assert tag_counts["obsolete_text"] >= 20
    assert tag_counts["negative"] >= 20
