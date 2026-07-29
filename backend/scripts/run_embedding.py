import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.embedding.embedding_builder import EmbeddingBuilder
from ingestion.integrity import json_inventory, write_manifest
from app.core.config import settings
from tqdm import tqdm
import time

CHUNKS_DIR = settings.chunks_dir
EMBEDDINGS_DIR = settings.embeddings_dir

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Chạy Pipeline Sinh Vector (Embedding)")
    parser.add_argument("--loai", type=str, help="Loại văn bản cụ thể (VD: an_le, bo_luat)")
    args = parser.parse_args()

    print("=" * 50)
    print("BAT DAU CHAY PIPELINE EMBEDDING (BGE-M3)")
    print(f"Thư mục nguồn (Chunks)     : {CHUNKS_DIR}")
    print(f"Thư mục đích  (Embeddings) : {EMBEDDINGS_DIR}")
    if args.loai:
        print(f"Chỉ chạy cho loại văn bản: {args.loai}")
    print("=" * 50)
    
    if not CHUNKS_DIR.exists():
        print(f"[!] Thư mục {CHUNKS_DIR} không tồn tại!")
        return
        
    builder = EmbeddingBuilder(model_name="bge-m3:latest")
    
    total_files = 0
    total_chunks_embedded = 0
    start_time = time.time()
    
    # Gom tất cả các file cần xử lý
    files_to_process = []
    for loai_dir in CHUNKS_DIR.iterdir():
        if not loai_dir.is_dir(): continue
        loai_van_ban = loai_dir.name
        if args.loai and args.loai != loai_van_ban: continue
        
        for f in loai_dir.rglob("*.json"):
            rel_path = f.relative_to(loai_dir)
            out_file = EMBEDDINGS_DIR / loai_van_ban / rel_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            files_to_process.append((f, out_file))
            
    print(f"\nTìm thấy {len(files_to_process)} file JSON cần xử lý.")
    
    # Duyệt qua các file
    for in_f, out_f in tqdm(files_to_process, desc="Tổng tiến trình Files"):
        num_embedded = builder.process_file(in_f, out_f)
        if num_embedded > 0:
            total_files += 1
            total_chunks_embedded += num_embedded
            
    duration = time.time() - start_time
    manifest_path = write_manifest(
        "embedding",
        inputs={"chunks": json_inventory(CHUNKS_DIR)},
        outputs={"embeddings": json_inventory(EMBEDDINGS_DIR, require_embedding=True)},
        metadata={"model_name": "bge-m3:latest", "loai_filter": args.loai},
    )
    print("\n" + "=" * 50)
    print(" KẾT QUẢ EMBEDDING")
    print("=" * 50)
    print(f"Tổng số file đã lưu  : {total_files}")
    print(f"Tổng số Vector tạo ra: {total_chunks_embedded}")
    print(f"Thời gian chạy       : {duration:.2f} giây")
    print(f"Manifest: {manifest_path}")
    print("GIAI DOAN SINH VECTOR DA HOAN TAT!")

if __name__ == "__main__":
    main()
