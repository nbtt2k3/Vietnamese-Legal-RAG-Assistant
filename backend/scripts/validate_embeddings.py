import json
import sys
from pathlib import Path

EMBEDDINGS_DIR = Path("data/embeddings")
EXPECTED_DIMENSIONS = 1024  # bge-m3 dimensions

def check_file(file_path: Path) -> tuple[int, int, int]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Không đọc được file {file_path.name}: {e}")
        return 0, 1, 0
        
    passed = 0
    failed = 0
    wrong_dims = 0
    
    for c in data:
        emb = c.get("embedding")
        if not emb or not isinstance(emb, list) or len(emb) == 0:
            failed += 1
            continue
            
        if len(emb) != EXPECTED_DIMENSIONS:
            print(f"[WARN] Chunk {c.get('chunk_id')} có Vector dài {len(emb)} (mong muốn {EXPECTED_DIMENSIONS})")
            wrong_dims += 1
            
        passed += 1
        
    return passed, failed, wrong_dims

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 50)
    print("🔍 KIỂM ĐỊNH CHẤT LƯỢNG VECTOR (EMBEDDINGS)")
    print("=" * 50)
    
    if not EMBEDDINGS_DIR.exists():
        print(f"Thư mục {EMBEDDINGS_DIR} không tồn tại!")
        return
        
    total_passed = 0
    total_failed = 0
    total_wrong_dims = 0
    
    for loai_dir in EMBEDDINGS_DIR.iterdir():
        if not loai_dir.is_dir(): continue
        
        for f in loai_dir.rglob("*.json"):
            p, fail, w = check_file(f)
            total_passed += p
            total_failed += fail
            total_wrong_dims += w
            
    print(f"Tổng số Vector hợp lệ: {total_passed}")
    print(f"Tổng số Chunk bị trượt : {total_failed} (Không có vector)")
    print(f"Số Vector sai kích thước: {total_wrong_dims}")
    
    if total_failed == 0 and total_wrong_dims == 0:
        print(">> TRẠNG THÁI: XANH MƯỢT! 100% Chunk đã hóa thành Vector 1024-chiều.")
    else:
        print(">> TRẠNG THÁI: CÓ LỖI! Hãy xem lại log.")

if __name__ == "__main__":
    main()
