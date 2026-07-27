import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.chunker.chunker_factory import ChunkerFactory
from ingestion.integrity import directory_inventory, json_inventory, write_manifest
from app.config import settings

METADATA_DIR = settings.metadata_dir
CHUNKS_DIR = settings.chunks_dir

def process_file(file_path: Path, out_path: Path, loai_van_ban: str) -> int:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Lỗi đọc file {file_path.name}: {e}")
        return 0
        
    chunker = ChunkerFactory.get_chunker(loai_van_ban)
    chunks = chunker.chunk(data)
    
    with open(out_path, "w", encoding="utf-8") as f:
        # Lưu thành list of dicts
        json.dump([c.to_dict() for c in chunks], f, ensure_ascii=False, indent=2)
        
    return len(chunks)

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Chạy pipeline cắt văn bản (Chunker)")
    parser.add_argument("--loai", type=str, help="Chỉ chạy cho loại văn bản cụ thể (bo_luat, an_le...)")
    args = parser.parse_args()
    
    print("=" * 50)
    print("BAT DAU CHAY PIPELINE CHUNKING")
    print(f"Thư mục nguồn (Metadata): {METADATA_DIR}")
    print(f"Thư mục đích (Chunks)   : {CHUNKS_DIR}")
    if args.loai:
        print(f"Chế độ: Lọc riêng loại [{args.loai}]")
    print("=" * 50)
    
    if not METADATA_DIR.exists():
        print(f"Thư mục {METADATA_DIR} không tồn tại!")
        return
        
    total_files = 0
    total_chunks = 0
    
    for loai_dir in METADATA_DIR.iterdir():
        if not loai_dir.is_dir():
            continue
            
        loai_van_ban = loai_dir.name
        if args.loai and args.loai != loai_van_ban:
            continue
            
        files = list(loai_dir.rglob("*.json"))
        if not files:
            continue
            
        print(f"\n[{loai_van_ban}] tìm thấy {len(files)} file")
        for f in files:
            rel_path = f.relative_to(loai_dir)
            out_path = CHUNKS_DIR / loai_van_ban / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            
            num_chunks = process_file(f, out_path, loai_van_ban)
            if num_chunks > 0:
                print(f"  ✓ {f.name} -> Tạo được {num_chunks} chunks")
                total_files += 1
                total_chunks += num_chunks
                
    manifest_path = write_manifest(
        "chunking",
        inputs={"metadata": directory_inventory(METADATA_DIR)},
        outputs={"chunks": json_inventory(CHUNKS_DIR)},
        metadata={"loai_filter": args.loai},
    )
    print("\n" + "=" * 50)
    print(" KẾT QUẢ CHUNKING")
    print("=" * 50)
    print(f"Tổng số file xử lý : {total_files}")
    print(f"Tổng số chunks tạo : {total_chunks}")
    print(f"Manifest: {manifest_path}")
    print("SAN SANG DE DUA VAO VECTOR DB!")

if __name__ == "__main__":
    main()
