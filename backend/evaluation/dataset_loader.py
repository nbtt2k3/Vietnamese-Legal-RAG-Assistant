import json
from pathlib import Path

from evaluation.models import EvalCase


def load_eval_dataset(path: str | Path) -> tuple[str, list[EvalCase]]:
    dataset_path = Path(path)
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    dataset_name = str(payload.get("dataset_name", dataset_path.stem))
    cases = [EvalCase(**item) for item in payload.get("cases", [])]
    return dataset_name, cases
