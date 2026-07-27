import argparse
import json
import sys

from generation.pipeline import GenerationPipeline
from retrieval.pipeline import RetrievalPipeline
from app.api.router import api_router
from app.api.auth_router import auth_router


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Legal RAG CLI")
    parser.add_argument("query", type=str, nargs="?", help="Câu hỏi pháp lý cần truy xuất hoặc trả lời")
    parser.add_argument("--json", action="store_true", help="In kết quả JSON")
    parser.add_argument("--retrieval-only", action="store_true", help="Chỉ chạy retrieval")
    args = parser.parse_args()

    if not args.query:
        print("Vui lòng truyền câu hỏi. Ví dụ:")
        print('python -m app.main "Nếu bên mua nhà chưa thanh toán đủ tiền nhưng đã được cấp sổ rồi đem thế chấp ngân hàng thì hợp đồng thế chấp có bị vô hiệu không?"')
        return

    if args.retrieval_only:
        result = RetrievalPipeline().run(args.query)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return
        print("=== QUERY INTENT ===")
        print(json.dumps(result.query_intent.to_dict(), ensure_ascii=False, indent=2))
        print("\n=== CONFIDENCE ===")
        print(json.dumps(result.confidence, ensure_ascii=False, indent=2))
        print("\n=== RETRIEVAL DEBUG ===")
        print(json.dumps(result.retrieval_debug, ensure_ascii=False, indent=2))
        print("\n=== TOP CANDIDATES ===")
        for idx, item in enumerate(result.candidates[:8], start=1):
            citation = item.metadata.get("citation", item.chunk_id)
            print(f"{idx}. {citation}")
            print(f"   role={item.metadata.get('legal_role')} | source={item.metadata.get('loai_van_ban')} | score={item.scores.get('final', 0):.3f}")
            print(f"   text={item.text[:220]}...")
        return

    answer, retrieval_result = GenerationPipeline().run(args.query)
    if args.json:
        payload = {
            "answer": answer.to_dict(),
            "retrieval": retrieval_result.to_dict(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print("=== SHORT ANSWER ===")
    print(answer.short_answer)

    for section in answer.sections:
        print(f"\n=== {section.title.upper()} ===")
        print(section.content)
        if section.citations:
            print("Citations:")
            for citation in section.citations:
                print(f"- {citation.citation}")

    print("\n=== CONFIDENCE ===")
    print(json.dumps(answer.confidence, ensure_ascii=False, indent=2))

    if answer.disclaimers:
        print("\n=== DISCLAIMERS ===")
        for item in answer.disclaimers:
            print(f"- {item}")

    print("\n=== TOP SOURCES ===")
    for citation in answer.citations[:8]:
        print(f"- {citation.citation}")


if __name__ == "__main__":
    main()
