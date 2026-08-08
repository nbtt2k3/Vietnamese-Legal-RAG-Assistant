import argparse
import sys
from pathlib import Path
from qdrant_client import QdrantClient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.core.config import settings

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Kiểm tra xem dữ liệu đã được index vào Qdrant thành công chưa.")
    parser.add_argument("--db-path", type=str, default=str(settings.qdrant_db_path), help="Thư mục lưu trữ database local")
    parser.add_argument("--qdrant-url", type=str, default=settings.qdrant_url, help="Qdrant URL; Docker thường là http://qdrant:6333")
    parser.add_argument("--sample-only", action="store_true", help="Kiểm tra collection sample")
    
    args = parser.parse_args()
    
    collection_name = "legal_docs_sample" if args.sample_only else "legal_docs"
    vector_size = 100 if args.sample_only else 1024
    
    target = args.qdrant_url or args.db_path
    print(f"[INFO] Đang kết nối Qdrant tại {target}...")
    try:
        if args.qdrant_url:
            client_kwargs = {"url": args.qdrant_url}
            if settings.qdrant_api_key:
                client_kwargs["api_key"] = settings.qdrant_api_key
            client = QdrantClient(**client_kwargs)
        else:
            client = QdrantClient(path=str(Path(project_root) / args.db_path))
    except Exception as e:
        print(f"[ERROR] Không thể kết nối Qdrant: {e}")
        return
        
    try:
        collections = client.get_collections().collections
        collection_names = {c.name for c in collections}
        alias_target = None

        if collection_name not in collection_names:
            aliases = getattr(client, "get_aliases", lambda: None)()
            for alias in getattr(aliases, "aliases", []) or []:
                if alias.alias_name == collection_name:
                    alias_target = alias.collection_name
                    break

        if collection_name not in collection_names and not alias_target:
            print(f"[ERROR] Collection hoặc alias '{collection_name}' không tồn tại. Có vẻ quá trình index thất bại hoặc chưa chạy.")
            return

        if alias_target:
            print(f"[INFO] Alias '{collection_name}' đang trỏ tới collection staging '{alias_target}'.")

        collection_info = client.get_collection(collection_name)
        total_points = collection_info.points_count
        print(f"[SUCCESS] Collection/alias '{collection_name}' tồn tại.")
        print(f"[SUCCESS] Tổng số vector đang lưu trữ (points): {total_points}")

        if total_points == 0:
            print("[WARN] Collection rỗng.")
            return

        print("\n[INFO] Thực hiện dummy search (tìm kiếm bằng vector giả ngẫu nhiên)...")

        # Tạo một vector giả với kích thước tương ứng để search thử
        dummy_query = [0.5] * vector_size

        results = client.query_points(
            collection_name=collection_name,
            query=dummy_query,
            limit=2
        )

        print(f"[INFO] Trả về {len(results.points)} kết quả:")
        for idx, hit in enumerate(results.points):
            print(f"\n--- Kết quả {idx+1} (Score: {hit.score:.4f}) ---")
            print(f"ID: {hit.id}")
            payload = hit.payload or {}
            print(f"Chunk ID: {payload.get('chunk_id')}")
            print(f"Doc ID: {payload.get('doc_id')}")
            text = payload.get('text', '')
            print(f"Text Snippet: {text[:100]}...")

        print("\n[DONE] Quá trình validate hoàn tất.")
    finally:
        client.close()

if __name__ == "__main__":
    main()
