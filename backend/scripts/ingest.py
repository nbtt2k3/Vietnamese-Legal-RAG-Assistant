"""
Entry point để chạy pipeline trích xuất.
Cách dùng:
  python -m scripts.ingest
  python -m scripts.ingest --loai bo_luat
"""
import argparse
import time
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.pipeline import run_pipeline, process_file
from ingestion.integrity import directory_inventory, file_sha256, write_manifest
from app.core.config import settings

RAW_DIR = settings.raw_dir
PARSED_DIR = settings.parsed_dir
CLEANED_DIR = settings.cleaned_dir
METADATA_DIR = settings.metadata_dir


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Chạy pipeline trích xuất văn bản")
    parser.add_argument(
        "--loai", 
        type=str, 
        help="Chỉ chạy cho loại văn bản cụ thể (bo_luat, nghi_dinh, an_le...)"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("BAT DAU CHAY PIPELINE TRICH XUAT VAN BAN")
    print(f"Thư mục nguồn: {RAW_DIR}")
    print(f"Thư mục đích (Parsed): {PARSED_DIR}")
    print(f"Thư mục đích (Cleaned): {CLEANED_DIR}")
    print(f"Thư mục đích (Metadata): {METADATA_DIR}")
    if args.loai:
        print(f"Chế độ: Lọc riêng loại [{args.loai}]")
    print("=" * 50)

    start_time = time.time()
    
    if args.loai:
        raw_dir = RAW_DIR / args.loai
        if not raw_dir.exists():
            raise SystemExit(f"Không tìm thấy thư mục: {raw_dir}")

    stats = run_pipeline(RAW_DIR, PARSED_DIR, CLEANED_DIR, loai_filter=args.loai)
    raw_files = sorted(
        path for path in RAW_DIR.rglob("*") if path.is_file() and path.suffix.lower() in {".pdf", ".docx"}
    )
    manifest_path = write_manifest(
        "ingestion",
        inputs={"raw_files": [
            {"path": path.relative_to(RAW_DIR).as_posix(), "sha256": file_sha256(path)}
            for path in raw_files
        ]},
        outputs={
            "parsed": directory_inventory(PARSED_DIR),
            "cleaned": directory_inventory(CLEANED_DIR),
            "metadata": directory_inventory(METADATA_DIR),
        },
        metadata={"loai_filter": args.loai, "success": stats["success"], "failed": stats["failed"]},
    )

    print("\n=== KẾT QUẢ ===")
    print(f"Thành công: {stats['success']}  |  Thất bại: {stats['failed']}")
    
    if stats["errors"]:
        print("\n=== CÁC FILE LỖI ===")
        for err in stats["errors"]:
            print(f"✗ {Path(err['file']).name}")
            print(f"  {err['error']}")
            
    print(f"\n⏱ Thời gian chạy: {time.time() - start_time:.2f}s")


    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
