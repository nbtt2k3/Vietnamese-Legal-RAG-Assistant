import argparse
import json
from pathlib import Path

CHUNKS_DIR = Path("data/chunks")

def check_chunks(file_path: Path) -> tuple[int, int, int]:
    """Returns (passed, failed, length_warnings)"""
    try:
        chunks = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Lỗi đọc file {file_path.name}: {e}")
        return 0, 1, 0
        
    passed = 0
    failed = 0
    warnings = 0
    
    for c in chunks:
        # 1. Kiểm tra trường bắt buộc
        if not c.get("chunk_id") or not c.get("doc_id") or not c.get("text"):
            print(f"  [!] Lỗi: Chunk bị thiếu trường bắt buộc trong {file_path.name}")
            failed += 1
            continue
            
        # 2. Kiểm tra metadata
        meta = c.get("metadata", {})
        if not meta:
            print(f"  [!] Lỗi: Chunk {c.get('chunk_id')} không có metadata.")
            failed += 1
            continue
            
        if not meta.get("so_hieu") and not meta.get("loai_van_ban"):
            print(f"  [!] Lỗi: Chunk {c.get('chunk_id')} thiếu document metadata.")
            failed += 1
            continue
        if not meta.get("citation"):
            print(f"  [!] Lỗi: Chunk {c.get('chunk_id')} thiếu citation chuẩn.")
            failed += 1
            continue
        if not meta.get("legal_role"):
            print(f"  [!] Lỗi: Chunk {c.get('chunk_id')} thiếu legal_role.")
            failed += 1
            continue
            
        # 3. Kiểm tra độ dài (cảnh báo nếu > 2000 ký tự - khoảng 400 từ)
        text_len = len(c.get("text", ""))
        if text_len > 2500:
            print(f"  [?] Cảnh báo: Chunk {c.get('chunk_id')} có độ dài {text_len} ký tự, hơi lớn so với mức lý tưởng.")
            warnings += 1
            
        passed += 1
        
    return passed, failed, warnings

def main():
    print("=" * 50)
    print("🔍 BẮT ĐẦU KIỂM TRA CHẤT LƯỢNG CHUNKS")
    print(f"Thư mục nguồn: {CHUNKS_DIR}")
    print("=" * 50)
    
    if not CHUNKS_DIR.exists():
        print(f"Thư mục {CHUNKS_DIR} không tồn tại!")
        return
        
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    
    for loai_dir in CHUNKS_DIR.iterdir():
        if not loai_dir.is_dir():
            continue
            
        loai_van_ban = loai_dir.name
        files = list(loai_dir.rglob("*.json"))
        
        for f in files:
            p, failed, w = check_chunks(f)
            total_passed += p
            total_failed += failed
            total_warnings += w
            
    print("=" * 50)
    print(" KẾT QUẢ VALIDATE CHUNKS")
    print("=" * 50)
    print(f"Tổng số Chunk OK     : {total_passed}")
    print(f"Tổng số Chunk Lỗi    : {total_failed}")
    print(f"Tổng số Cảnh báo dài : {total_warnings}")
    
    if total_failed == 0:
        print(">> TRẠNG THÁI: XANH MƯỢT! 100% Chunks có cấu trúc và Metadata hợp lệ.")
    else:
        print(">> TRẠNG THÁI: CÓ LỖI! Vui lòng kiểm tra log phía trên.")

if __name__ == "__main__":
    main()
