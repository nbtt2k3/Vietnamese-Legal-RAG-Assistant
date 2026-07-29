"""
Script to validate the output of Metadata Builder.
Checks if metadata is properly attached to documents, chapters, articles, clauses, and points.
"""
import json
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings

METADATA_DIR = settings.metadata_dir

def _check_node_metadata(node: dict, node_name: str, has_hierarchy: bool) -> tuple[int, int]:
    passed = 0
    failed = 0
    
    if "metadata" not in node or not node["metadata"]:
        print(f"  [!] Lỗi: {node_name} không có trường metadata.")
        failed += 1
        return passed, failed
        
    meta = node["metadata"]
    if "legal" not in meta or not meta["legal"].get("citation"):
        print(f"  [!] Lỗi: {node_name} thiếu metadata.legal.citation.")
        failed += 1
    else:
        passed += 1
    if "legal" not in meta or not meta["legal"].get("legal_role"):
        print(f"  [!] Lỗi: {node_name} thiếu metadata.legal.legal_role.")
        failed += 1
    else:
        passed += 1
    
    if has_hierarchy:
        if "hierarchy" not in meta:
            print(f"  [!] Lỗi: {node_name} thiếu metadata.hierarchy.")
            failed += 1
        else:
            passed += 1
            
    # Check statistics for Dieu, Khoan, Diem
    if node_name.startswith("Dieu") or node_name.startswith("Khoan") or node_name.startswith("Diem"):
        if "statistics" not in meta:
            print(f"  [!] Lỗi: {node_name} thiếu metadata.statistics.")
            failed += 1
        else:
            passed += 1
            
    return passed, failed

def validate_file(file_path: Path) -> tuple[int, int]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[ERROR] Không thể đọc JSON file {file_path.name}")
        return 0, 1
        
    passed = 0
    failed = 0
    
    loai_van_ban = data.get("loai_van_ban")
    
    # 1. Document Metadata check
    if "metadata" not in data or "document" not in data.get("metadata", {}):
        print(f"  [!] Lỗi: Văn bản {file_path.name} thiếu metadata.document.")
        failed += 1
    else:
        doc_meta = data["metadata"]["document"]
        if not doc_meta.get("so_hieu"):
            print(f"  [!] Lỗi: metadata.document thiếu so_hieu.")
            failed += 1
        else:
            passed += 1
    if "legal" not in data.get("metadata", {}) or not data["metadata"]["legal"].get("citation"):
        print(f"  [!] Lỗi: Văn bản {file_path.name} thiếu metadata.legal.citation.")
        failed += 1
    else:
        passed += 1
    legal_meta = data.get("metadata", {}).get("legal", {})
    if not legal_meta.get("validity_status"):
        print(f"  [!] Lỗi: Văn bản {file_path.name} thiếu metadata.legal.validity_status.")
        failed += 1
    else:
        passed += 1
    if "related_documents" not in legal_meta:
        print(f"  [!] Lỗi: Văn bản {file_path.name} thiếu metadata.legal.related_documents.")
        failed += 1
    else:
        passed += 1
    for field in (
        "source_verification_status",
        "source_checksum_sha256",
        "source_of_validity",
        "validity_basis",
        "validity_confidence",
    ):
        if field not in legal_meta:
            print(f"  [~] Cảnh báo: Văn bản {file_path.name} chưa có metadata Phase 1: metadata.legal.{field}.")
        else:
            passed += 1
            
    if loai_van_ban == "an_le":
        # Check an le specific
        if "search" not in data.get("metadata", {}):
            print(f"  [!] Lỗi: Án lệ {file_path.name} thiếu metadata.search (keywords).")
            failed += 1
        else:
            passed += 1
    else:
        # Check hierarchy recursion
        for dieu in data.get("dieu", []):
            d_name = f"Dieu {dieu.get('number')}"
            p, f = _check_node_metadata(dieu, d_name, True)
            passed += p; failed += f
            
            for khoan in dieu.get("khoan", []):
                k_name = f"{d_name}, Khoan {khoan.get('number')}"
                p, f = _check_node_metadata(khoan, k_name, True)
                passed += p; failed += f
                
                for diem in khoan.get("diem", []):
                    di_name = f"{k_name}, Diem {diem.get('id')}"
                    p, f = _check_node_metadata(diem, di_name, True)
                    passed += p; failed += f
                    
    return passed, failed

def main():
    parser = argparse.ArgumentParser(description="Validate Metadata JSON files")
    parser.add_argument("--loai", type=str, help="Loại văn bản (bo_luat, nghi_dinh...)")
    args = parser.parse_args()
    
    total_passed = 0
    total_failed = 0
    files_checked = 0
    
    print("=" * 50)
    print("🔍 BẮT ĐẦU KIỂM TRA CHẤT LƯỢNG METADATA")
    print(f"Thư mục nguồn: {METADATA_DIR}")
    print("=" * 50)
    
    if not METADATA_DIR.exists():
        print(f"Thư mục {METADATA_DIR} không tồn tại. Vui lòng chạy ingest.py trước.")
        return
        
    for loai_dir in METADATA_DIR.iterdir():
        if not loai_dir.is_dir():
            continue
            
        loai_van_ban = loai_dir.name
        if args.loai and args.loai != loai_van_ban:
            continue
            
        files = list(loai_dir.glob("*.json"))
        if not files:
            continue
            
        print(f"\n[{loai_van_ban}] Đang kiểm tra {len(files)} files...")
        
        for f in files:
            p, failed = validate_file(f)
            total_passed += p
            total_failed += failed
            files_checked += 1
            if failed == 0:
                print(f"  ✓ {f.name}: OK (Passed {p} checks)")
                
    print("=" * 50)
    print(" KẾT QUẢ VALIDATE")
    print("=" * 50)
    print(f"Tổng số file đã kiểm tra : {files_checked}")
    print(f"Tổng số Node Pass       : {total_passed}")
    print(f"Tổng số Node Lỗi        : {total_failed}")
    if total_failed == 0:
        print(">> TRẠNG THÁI: XANH MƯỢT! Mọi Metadata đều đã được gán chính xác.")
    else:
        print(">> TRẠNG THÁI: CÓ LỖI! Cần kiểm tra lại log bên trên.")
        
if __name__ == "__main__":
    main()
