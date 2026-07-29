import argparse
import sys
from pathlib import Path

# Add project root to path so we can import ingestion
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ingestion.indexing.indexer import QdrantIndexer
from ingestion.integrity import compare_chunk_sets, compare_qdrant_chunks, json_inventory, write_manifest
from app.core.config import settings
from app.core.logging import logger

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Chạy quá trình indexing đẩy data vào Qdrant.")
    parser.add_argument("--data-dir", type=str, default=str(settings.embeddings_dir), help="Thư mục chứa file json embeddings")
    parser.add_argument("--db-path", type=str, default=str(settings.qdrant_db_path), help="Thư mục lưu trữ database local")
    parser.add_argument("--sample-only", action="store_true", help="Chạy chế độ sample (dùng collection test và vector_size nhỏ)")
    
    parser.add_argument("--rebuild", action="store_true", help="Recreate collection from the current embedding snapshot")
    parser.add_argument("--migrate-legacy", action="store_true", help="Allow one-time migration from a non-alias live collection after staging verification")
    parser.add_argument("--chunks-dir", type=str, default=str(settings.chunks_dir), help="Chunk snapshot paired with --data-dir")
    args = parser.parse_args()
    
    if args.sample_only:
        collection_name = "legal_docs_sample"
        vector_size = 100 # Theo kích thước vector giả trong sample_doc.json
        logger.info(f"Chạy chế độ SAMPLE_ONLY. Vector size: {vector_size}, Collection: {collection_name}")
    else:
        collection_name = "legal_docs"
        vector_size = 1024 # Kích thước mặc định của bge-m3
        logger.info(f"Chạy chế độ REAL DATA. Vector size: {vector_size}, Collection: {collection_name}")
        
    data_dir = Path(project_root) / args.data_dir
    if not args.sample_only:
        chunks_dir = Path(project_root) / args.chunks_dir
        integrity = compare_chunk_sets(chunks_dir, data_dir)
        if not integrity["is_consistent"]:
            raise SystemExit(
                "[ERROR] Chunk and embedding snapshots differ. Run embedding and validate_data_integrity before indexing."
            )

    with QdrantIndexer(
        db_path=args.db_path,
        collection_name=collection_name,
        vector_size=vector_size,
        recreate=args.rebuild,
    ) as indexer:
        if args.sample_only:
            sample_file = data_dir / "bo_luat" / "sample_doc.json"
            if sample_file.exists():
                logger.info(f"Bắt đầu index sample file: {sample_file}")
                indexer.index_file(sample_file)
            else:
                logger.error(f"Không tìm thấy file sample: {sample_file}")
        else:
            success_count, failed_count = indexer.process_directory(data_dir)
            if failed_count:
                raise SystemExit(f"[ERROR] Indexing failed for {failed_count} file(s).")

            expected_count = json_inventory(data_dir, require_embedding=True)["unique_chunk_count"]
            staged_count = indexer.staging_point_count()
            if staged_count != expected_count:
                raise SystemExit(
                    f"[ERROR] Staging snapshot mismatch: expected {expected_count}, got {staged_count}."
                )
            
            # Phase 4: Swap alias upon success
            indexer.finalize_alias(allow_legacy_migration=args.migrate_legacy)
            
    # Local Qdrant is exclusively locked while the indexer is open. Validate only
    # after its context manager has closed the client.
    if not args.sample_only:
        indexed = compare_qdrant_chunks(chunks_dir, Path(project_root) / args.db_path, collection_name)
        if not indexed["is_consistent"]:
            raise SystemExit(
                f"[ERROR] Qdrant snapshot mismatch after indexing: {indexed['indexed_count']} points."
            )
        manifest_path = write_manifest(
            "indexing",
            inputs={"embeddings": json_inventory(data_dir, require_embedding=True)},
            outputs={"db_path": args.db_path, "collection_name": collection_name},
            metadata={"rebuild": args.rebuild, "vector_size": vector_size},
        )
        logger.info(f"Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
