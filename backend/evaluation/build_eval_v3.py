"""Build a realistic, reproducible Legal RAG evaluation dataset.

The v3 set deliberately reuses citations and expected answer terms from the
reviewed v2 cases. New cases vary the wording and uncertainty conditions; they
do not introduce unverified legal claims.
"""

from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
V2_PATH = ROOT / "datasets" / "legal_rag_eval_v2.json"
V3_PATH = ROOT / "datasets" / "legal_rag_eval_v3.json"


def without_accents(value: str) -> str:
    value = value.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def clone_case(case: dict, case_id: str, query: str, *extra_tags: str) -> dict:
    result = copy.deepcopy(case)
    result["case_id"] = case_id
    result["query"] = query
    result["tags"] = list(dict.fromkeys(result.get("tags", []) + list(extra_tags)))
    result["generated_from"] = case["case_id"]
    return result


def build_cases(seed_cases: list[dict]) -> list[dict]:
    cases: list[dict] = []
    seen_queries: set[str] = set()
    seen_ids: set[str] = set()

    def add(case: dict) -> None:
        if case["case_id"] in seen_ids:
            raise ValueError(f"Duplicate case_id: {case['case_id']}")
        if case["query"] in seen_queries:
            return
        seen_ids.add(case["case_id"])
        seen_queries.add(case["query"])
        cases.append(case)

    # Keep every reviewed v2 case as an anchor, then add three natural wording
    # variants. The unaccented form is especially important for Vietnamese UX.
    for seed in seed_cases:
        add(copy.deepcopy(seed))
        add(clone_case(seed, f"{seed['case_id']}__polite", f"Cho tôi hỏi, {seed['query']}", "paraphrase"))
        add(clone_case(seed, f"{seed['case_id']}__legal_context", f"Theo quy định pháp luật, {seed['query']}", "paraphrase"))
        add(clone_case(seed, f"{seed['case_id']}__unaccented", without_accents(seed["query"]), "unaccented", "paraphrase"))

    answerable = [case for case in seed_cases if case.get("should_answer", True)]
    scenario_or_validity = [
        case for case in answerable
        if "scenario" in case.get("tags", []) or case.get("expected_request_type") == "validity_question"
    ]

    # Missing-facts cases: the user gives a legal topic but explicitly omits
    # facts needed to apply the rule to a real situation.
    for index, seed in enumerate(scenario_or_validity[:15], start=1):
        core = seed["query"].rstrip("?。 ")
        query_a = (
            f"Tôi đang gặp vấn đề liên quan đến việc {core.lower()}. "
            "Tôi chưa rõ thời điểm, chủ thể, giấy tờ và hành vi cụ thể. Có thể kết luận ngay không?"
        )
        query_b = (
            f"Nếu chỉ biết rằng {core.lower()} nhưng thiếu thông tin về thời điểm giao dịch, "
            "người tham gia và nội dung thỏa thuận thì cần bổ sung gì trước khi đánh giá?"
        )
        for suffix, query in (("a", query_a), ("b", query_b)):
            item = clone_case(seed, f"insufficient_facts_{index:02d}_{suffix}", query, "insufficient_facts")
            item["expected_request_type"] = "scenario_application"
            item["min_confidence_level"] = "low"
            item["expected_answer_terms"] = list(dict.fromkeys(item.get("expected_answer_terms", []) + ["chưa đủ", "tình tiết"]))
            item["expected_missing_facts_terms"] = ["thời điểm", "chủ thể", "giấy tờ", "nội dung"]
            add(item)

    # Obsolete/temporal cases focus on replacement and validity status. Their
    # expected authority remains the reviewed current instrument in the seed.
    temporal_seeds = [
        case for case in answerable
        if "temporal" in case.get("tags", []) or "nghi_dinh" in case.get("tags", [])
    ][:8]
    for index, seed in enumerate(temporal_seeds, start=1):
        citation = seed.get("expected_citations", ["văn bản liên quan"])[0]
        queries = [
            f"Văn bản {citation} còn hiệu lực không, hay đã bị văn bản khác thay thế?",
            f"Nếu tra cứu quy định cũ liên quan đến {citation}, cần kiểm tra tình trạng hết hiệu lực và văn bản thay thế nào?",
            f"Tại thời điểm hiện nay, có thể áp dụng {citation} chắc chắn không hay phải đối chiếu văn bản mới hơn?",
        ]
        for suffix, query in zip(("a", "b", "c"), queries):
            item = clone_case(seed, f"obsolete_text_{index:02d}_{suffix}", query, "obsolete_text", "temporal")
            item["expected_request_type"] = "validity_question"
            item["expected_answer_terms"] = list(dict.fromkeys(item.get("expected_answer_terms", []) + ["hết hiệu lực", "thay thế"]))
            item["min_confidence_level"] = "low"
            add(item)

    # Negative cases are paraphrased independently so the evaluator tests
    # abstention rather than memorizing one exact out-of-scope sentence.
    negative_seeds = [case for case in seed_cases if not case.get("should_answer", True)]
    for index, seed in enumerate(negative_seeds, start=1):
        queries = [
            f"Bạn có thể tư vấn giúp tôi: {seed['query']}",
            f"Câu hỏi sau có thuộc phạm vi dữ liệu pháp luật hiện có không: {seed['query']}",
            f"Tôi cần câu trả lời chính xác cho việc này: {seed['query']}",
        ]
        for suffix, query in zip(("a", "b", "c"), queries):
            add(clone_case(seed, f"negative_variant_{index:02d}_{suffix}", query, "paraphrase", "negative"))

    return cases


def main() -> None:
    payload = json.loads(V2_PATH.read_text(encoding="utf-8-sig"))
    cases = build_cases(payload["cases"])
    if not 200 <= len(cases) <= 500:
        raise ValueError(f"Expected 200-500 cases, got {len(cases)}")

    output = {
        "dataset_name": "legal_rag_eval_v3",
        "description": (
            "Vietnamese Legal RAG test set with reviewed anchor questions, "
            "paraphrases, unaccented queries, insufficient facts, temporal/obsolete-text "
            "questions and out-of-scope negatives."
        ),
        "source_dataset": "legal_rag_eval_v2",
        "case_count": len(cases),
        "cases": cases,
    }
    V3_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {V3_PATH}")


if __name__ == "__main__":
    main()
