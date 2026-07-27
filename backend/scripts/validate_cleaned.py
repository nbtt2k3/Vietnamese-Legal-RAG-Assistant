import json
from pathlib import Path
import re

CLEANED_DIR = Path("data/cleaned")

def check_text(text: str) -> list:
    if not text: return []
    issues = []
    
    if re.search(r"(?i)Trang\s+\d+", text):
        issues.append("Còn sót 'Trang X'")
    if re.search(r"(?i)Page\s+\d+", text):
        issues.append("Còn sót 'Page X'")
    if re.search(r"(?i)THƯ VIỆN PHÁP LUẬT", text):
        issues.append("Còn sót watermark")
        
    if "  " in text:
        issues.append("Còn sót khoảng trắng kép")
        
    if re.search(r"\s+[\.,;:]", text):
        issues.append("Dấu câu sai định dạng (có khoảng trắng trước dấu câu)")
        
    if re.search(r"\bđiều\s+\d+", text) or re.search(r"\bkhoản\s+\d+", text):
        issues.append("Từ 'Điều/Khoản' chưa được viết hoa")
        
    return issues

def validate_doc(data: dict) -> list:
    issues = []
    
    def _check(text, context):
        res = check_text(text)
        for r in res:
            issues.append(f"{context}: {r}")
            
    _check(data.get('ten'), 'Tên văn bản')
    
    if data.get('loai_van_ban') == 'an_le':
        _check(data.get('khai_quat_noi_dung'), 'Khái quát nội dung')
        _check(data.get('tinh_huong_phap_ly'), 'Tình huống pháp lý')
        _check(data.get('giai_phap_phap_ly'), 'Giải pháp pháp lý')
        _check(data.get('noi_dung_vu_an'), 'Nội dung vụ án')
        _check(data.get('noi_dung_an_le_trich_dan'), 'Nội dung án lệ')
        for item in data.get('dieu_luat_lien_quan', []): _check(item, 'Điều luật liên quan')
        for item in data.get('tu_khoa', []): _check(item, 'Từ khóa')
    else:
        for d in data.get('dieu', []):
            _check(d.get('title'), f"Điều {d.get('number')}")
            _check(d.get('text'), f"Điều {d.get('number')} text")
            for k in d.get('khoan', []):
                _check(k.get('text'), f"Điều {d.get('number')} Khoản {k.get('number')}")
                for diem in k.get('diem', []):
                    _check(diem.get('text'), f"Điều {d.get('number')} Khoản {k.get('number')} Điểm {diem.get('id')}")
                    
        for p in data.get('phu_luc', []):
            _check(p.get('ten_mau'), 'Phụ lục tên mẫu')
            _check(p.get('noi_dung'), 'Phụ lục nội dung')
            
    return issues

def main():
    total, ok, warn = 0, 0, 0
    if not CLEANED_DIR.exists():
        print(f"Thư mục {CLEANED_DIR} không tồn tại.")
        return
        
    for json_file in CLEANED_DIR.rglob("*.json"):
        total += 1
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            issues = validate_doc(data)
            if issues:
                warn += 1
                print(f"⚠ {json_file.relative_to(CLEANED_DIR)}")
                # Chỉ in tối đa 5 lỗi để tránh trôi màn hình
                for i in issues[:5]:
                    print(f"    - {i}")
                if len(issues) > 5:
                    print(f"    ... và {len(issues)-5} lỗi khác")
            else:
                ok += 1
        except Exception as e:
            print(f"❌ Lỗi đọc file {json_file.name}: {e}")
            warn += 1
            
    print(f"\n=== TỔNG KẾT CLEANER: {total} file | {ok} sạch | {warn} dơ ===")

if __name__ == '__main__':
    main()
