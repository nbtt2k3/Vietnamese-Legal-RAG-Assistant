"""Fail when chunk and embedding snapshots do not match exactly."""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.integrity import compare_chunk_sets, compare_qdrant_chunks
from app.core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate chunk and embedding snapshot integrity")
    parser.add_argument("--chunks-dir", default="data/chunks")
    parser.add_argument("--embeddings-dir", default="data/embeddings")
    parser.add_argument("--db-path", default="data/qdrant_db")
    parser.add_argument("--collection", default="legal_docs")
    parser.add_argument("--skip-qdrant", action="store_true")
    args = parser.parse_args()
    result = compare_chunk_sets(Path(args.chunks_dir), Path(args.embeddings_dir))

    print(f"Chunks: {result['chunks']['unique_chunk_count']}")
    print(f"Embeddings: {result['embeddings']['unique_chunk_count']}")
    print(f"Missing embeddings: {len(result['missing_embeddings'])}")
    print(f"Orphan embeddings: {len(result['orphan_embeddings'])}")
    for issue in result["chunks"]["invalid_records"] + result["embeddings"]["invalid_records"]:
        print(f"[ERROR] {issue}")
    if result["chunks"]["unique_chunk_count"] == 0 or result["embeddings"]["unique_chunk_count"] == 0:
        print("[UNAVAILABLE] Không tìm thấy snapshot chunks/embeddings để kiểm tra.")
        print("[HƯỚNG DẪN] Chạy lại scripts.run_chunker và scripts.run_embedding trước khi validate.")
        return 2
    if not args.skip_qdrant:
        indexed = compare_qdrant_chunks(Path(args.chunks_dir), Path(args.db_path), args.collection)
        print(f"Qdrant target: {indexed.get('qdrant_target', args.db_path)}")
        print(f"Indexed points: {indexed['indexed_count']}")
        print(f"Missing indexed: {len(indexed['missing_indexed'])}")
        print(f"Orphan indexed: {len(indexed['orphan_indexed'])}")
        if indexed.get("status") == "unavailable":
            print("[UNAVAILABLE] Không thể đọc Qdrant; chưa thể kết luận index bị lệch.")
            print(f"[DETAIL] {indexed.get('error', 'unknown connection error')}")
            if settings.qdrant_url:
                print(
                    "[HƯỚNG DẪN] Qdrant đang là service private. Chạy trong Docker: "
                    "docker compose exec app python -m scripts.validate_data_integrity"
                )
            else:
                print("[HƯỚNG DẪN] Kiểm tra Qdrant local và đường dẫn --db-path.")
            return 2
        result["is_consistent"] = result["is_consistent"] and indexed["is_consistent"]
    if not result["is_consistent"]:
        print("[FAIL] Chunk and embedding snapshots are inconsistent.")
        return 1
    if args.skip_qdrant:
        print("[PASS] Chunk and embedding snapshots match exactly.")
    else:
        print("[PASS] Chunk, embedding, and Qdrant snapshots match exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
