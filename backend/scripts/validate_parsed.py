# scripts/validate_processed.py
"""
Quét toàn bộ data/processed/, tự động flag các file có dấu hiệu bất thường,
để không phải mở từng JSON kiểm tra tay khi có hàng trăm file.
Chạy: python -m scripts.validate_processed
"""
import json
import sys
from pathlib import Path
from app.core.config import settings

PARSED_DIR = settings.parsed_dir

# Các cụm từ đặc trưng của khối hành chính "Nơi nhận / chữ ký" hay bị dính
# nhầm vào nội dung điều luật cuối cùng (bug đã gặp ở nghị quyết HĐTP).
FOOTER_MARKERS = [
    "Nơi nhận:",
    "TM. HỘI ĐỒNG",
    "CHÁNH ÁN",
    "Ủy ban Thường vụ Quốc hội (để giám sát)",
    "Lưu: VT,",
]

# Field nào cũng cần kết thúc bằng dấu câu hợp lệ; nếu không, khả năng cao
# là bị cắt cụt giữa dòng khi nguồn xuống hàng (bug đã gặp ở dieu_luat_lien_quan).
VALID_ENDINGS = (".", ";", ":", ")", "”", '"')


def _is_truncated(text: str) -> bool:
    if not text:
        return False
    return text.strip()[-1] not in VALID_ENDINGS


def validate_van_ban(data: dict, file_path: Path) -> list[str]:
    issues = []

    if data.get("so_hieu") in (None, "unknown"):
        issues.append("so_hieu = unknown")
    if data.get("ngay_ban_hanh") is None:
        issues.append("ngay_ban_hanh = null")
    if not data.get("ten") or data["ten"] in ("BỘ LUẬT", "unknown"):
        issues.append(f"ten khả nghi: '{data.get('ten')}'")

    # co_quan_ban_hanh từng bị bỏ trống toàn bộ ở các file nghị định
    if not data.get("co_quan_ban_hanh"):
        issues.append("co_quan_ban_hanh = null/rỗng")

    dieu = data.get("dieu", [])
    if not dieu:
        issues.append("KHÔNG parse được Điều nào")
        return issues

    nums = []
    for d in dieu:
        try:
            nums.append(int(d["number"]))
        except (ValueError, TypeError):
            issues.append(f"Điều có số không hợp lệ: {d.get('number')}")

    # So khớp so_luong_dieu khai báo với số điều thực tế parse được.
    # Quan trọng hơn suy luận min/max: bắt được cả trường hợp cắt mất
    # nguyên 1 dải điều ở đầu hoặc cuối văn bản mà khoảng min-max không lộ ra.
    declared = data.get("so_luong_dieu")
    if declared is not None and declared != len(dieu):
        issues.append(f"so_luong_dieu={declared} nhưng thực tế có {len(dieu)} điều")

    if nums:
        expected = set(range(min(nums), max(nums) + 1))
        missing = sorted(expected - set(nums))
        if missing:
            issues.append(f"THIẾU {len(missing)} Điều: {missing[:15]}{'...' if len(missing) > 15 else ''}")
        dup = {n for n in nums if nums.count(n) > 1}
        if dup:
            issues.append(f"TRÙNG số Điều: {sorted(dup)}")

    no_title = [d["number"] for d in dieu if not d.get("title")]
    if no_title:
        issues.append(f"{len(no_title)} Điều không có title: {no_title[:10]}")

    no_content = [d["number"] for d in dieu if not d.get("khoan") and not d.get("text")]
    if no_content:
        issues.append(f"{len(no_content)} Điều rỗng nội dung: {no_content[:10]}")

    # Bug đã gặp: khối "Nơi nhận:" / chữ ký bị dính vào khoản cuối cùng của
    # điều cuối cùng (thường là "Hiệu lực thi hành") thay vì bị loại bỏ.
    last_dieu = dieu[-1]
    if last_dieu.get("khoan"):
        tail_text = last_dieu["khoan"][-1].get("text", "")
    else:
        tail_text = last_dieu.get("text", "")
    if any(marker in tail_text for marker in FOOTER_MARKERS):
        issues.append(
            f"Điều {last_dieu.get('number')}: nghi ngờ dính khối 'Nơi nhận'/chữ ký vào nội dung"
        )

    # Bug đã gặp: phụ lục bị lặp nội dung, entry rác từ mục lục, hoặc
    # ma_mau đụng độ giữa nhiều phụ lục con (VD "Phụ lục I" và "Phụ lục II").
    if data.get("co_phu_luc"):
        phu_luc = data.get("phu_luc", [])
        if not phu_luc:
            issues.append("co_phu_luc=true nhưng phu_luc rỗng")
        else:
            total_len = sum(len(e.get("noi_dung", "")) for e in phu_luc)
            declared_len = data.get("do_dai_phu_luc_ky_tu")
            if declared_len is not None and total_len != declared_len:
                issues.append(
                    f"độ dài phụ lục lệch: tổng thực tế={total_len} vs khai báo={declared_len}"
                )
            ma_mau_list = [e.get("ma_mau") for e in phu_luc]
            dup_ma = {m for m in ma_mau_list if ma_mau_list.count(m) > 1}
            if dup_ma:
                issues.append(f"ma_mau trùng trong phu_luc: {sorted(dup_ma)}")
            # entry rác kiểu mục lục còn sót ký tự "|" chưa được strip
            stub_like = [
                e.get("ma_mau")
                for e in phu_luc
                if e.get("ten_mau", "").strip().startswith("|")
                or e.get("noi_dung", "").strip().startswith("|")
            ]
            if stub_like:
                issues.append(f"Nghi ngờ entry rác từ mục lục trong phu_luc: {stub_like[:10]}")

    return issues


def validate_an_le(data: dict, file_path: Path) -> list[str]:
    issues = []

    if not data.get("tinh_huong_phap_ly"):
        issues.append("thiếu tình huống pháp lý")
    if not data.get("giai_phap_phap_ly"):
        issues.append("thiếu giải pháp pháp lý")
    if not data.get("noi_dung_vu_an"):
        issues.append("thiếu nội dung vụ án")
    if not data.get("dieu_luat_lien_quan"):
        issues.append("chưa trích được điều luật liên quan")
    if not data.get("ngay_cong_bo"):
        issues.append("ngay_cong_bo = null")

    # noi_dung_an_le_trich_dan là field quan trọng nhất của 1 án lệ — từng
    # bị rỗng hoàn toàn ở 1 file dù nguồn có đầy đủ nội dung. Bắt buộc phải có.
    if not data.get("noi_dung_an_le_trich_dan"):
        issues.append("THIẾU noi_dung_an_le_trich_dan — bug nghiêm trọng, đây là nội dung cốt lõi")

    # tu_khoa từng bị rỗng ở nhiều file dù nguồn có từ khóa rõ ràng.
    if not data.get("tu_khoa"):
        issues.append("tu_khoa rỗng")

    # Giá trị rác kiểu "của án lệ:" (mảnh vụn của header bị bắt nhầm)
    khai_quat = data.get("khai_quat_noi_dung")
    if khai_quat is not None and len(khai_quat.strip()) < 15:
        issues.append(f"khai_quat_noi_dung khả nghi (quá ngắn/có thể là mảnh header): '{khai_quat}'")

    # Phát hiện câu bị cắt cụt giữa dòng khi nguồn xuống hàng dài
    # (bug đã gặp: mất đuôi câu "...về giao dịch bảo đảm." hay "...năm 2010").
    # CHỈ kiểm tra item CUỐI CÙNG của mảng: trong văn bản gốc, dấu ";" ngăn
    # cách giữa các gạch đầu dòng bị strip đi khi tách mảng (đúng, không phải
    # bug), nên các item không phải cuối tự nhiên không có dấu câu — chỉ item
    # cuối mới thực sự phải kết thúc bằng dấu "." của toàn bộ danh sách.
    dllq = data.get("dieu_luat_lien_quan") or []
    if dllq and _is_truncated(dllq[-1]):
        issues.append(f"dieu_luat_lien_quan (item cuối) có thể bị cắt cụt: '...{dllq[-1][-40:]}'")

    for item in data.get("tu_khoa", []) or []:
        if len(item.strip()) < 3:
            issues.append(f"tu_khoa có mục quá ngắn/khả nghi: '{item}'")

    return issues


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    total, ok, warn = 0, 0, 0
    for json_file in PARSED_DIR.rglob("*.json"):
        total += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"✗ {json_file}: LỖI ĐỌC FILE — {e}")
            warn += 1
            continue

        # án lệ có schema khác, kiểm tra riêng
        if "so_an_le" in data:
            issues = validate_an_le(data, json_file)
        else:
            issues = validate_van_ban(data, json_file)

        if issues:
            warn += 1
            print(f"⚠ {json_file.relative_to(PARSED_DIR)}")
            for i in issues:
                print(f"    - {i}")
        else:
            ok += 1

    print(f"\n=== TỔNG KẾT: {total} file | {ok} ổn | {warn} cần xem lại ===")


if __name__ == "__main__":
    main()
