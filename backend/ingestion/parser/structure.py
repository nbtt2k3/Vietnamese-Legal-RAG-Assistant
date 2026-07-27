"""
Data model cho toàn bộ cấu trúc văn bản pháp luật VN.
Dùng dataclass để nhẹ, dễ serialize sang dict/JSON cho bước chunking/embedding sau.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class LoaiVanBan(str, Enum):
    BO_LUAT = "bo_luat"
    NGHI_DINH = "nghi_dinh"
    THONG_TU = "thong_tu"
    NGHI_QUYET = "nghi_quyet"
    AN_LE = "an_le"


# ---------- Nhóm văn bản quy phạm (Điều/Khoản/Điểm) ----------

@dataclass
class Diem:
    id: str                     # "a", "b", "c"...
    text: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class Khoan:
    number: str                 # "1", "2"...
    text: str
    diem: list[Diem] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "number": self.number,
            "text": self.text,
            "diem": [d.to_dict() for d in self.diem],
            "metadata": self.metadata,
        }


@dataclass
class Dieu:
    number: str                          # "463"
    title: Optional[str] = None          # "Hợp đồng vay tài sản"
    text: str = ""                       # phần mở đầu trước khi vào khoản (nếu có)
    khoan: list[Khoan] = field(default_factory=list)

    # metadata phục vụ citation & hiệu lực pháp luật
    phan_number: Optional[str] = None
    phan_title: Optional[str] = None
    chuong_number: Optional[str] = None   # điều này thuộc chương nào
    chuong_title: Optional[str] = None
    muc_number: Optional[str] = None
    muc_title: Optional[str] = None
    amended_by: list[str] = field(default_factory=list)   # ["NĐ 91/2015 - Điều 3"]
    repealed: bool = False
    repealed_by: Optional[str] = None
    effective_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def full_text(self) -> str:
        """Ghép toàn bộ nội dung điều luật thành 1 chuỗi — dùng cho chunker."""
        parts = [f"Điều {self.number}. {self.title or ''}".strip()]
        if self.text:
            parts.append(self.text)
        for k in self.khoan:
            parts.append(f"{k.number}. {k.text}")
            for d in k.diem:
                parts.append(f"  {d.id}) {d.text}")
        return "\n".join(parts)

    def to_dict(self):
        return {
            "number": self.number,
            "title": self.title,
            "text": self.text,
            "khoan": [k.to_dict() for k in self.khoan],
            "phan_number": self.phan_number,
            "phan_title": self.phan_title,
            "chuong_number": self.chuong_number,
            "chuong_title": self.chuong_title,
            "muc_number": self.muc_number,
            "muc_title": self.muc_title,
            "amended_by": self.amended_by,
            "repealed": self.repealed,
            "repealed_by": self.repealed_by,
            "effective_date": self.effective_date,
            "metadata": self.metadata,
        }


@dataclass
class Muc:
    number: str
    title: str
    dieu: list[Dieu] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class Chuong:
    number: str
    title: str
    phan_number: Optional[str] = None
    phan_title: Optional[str] = None
    muc: list[Muc] = field(default_factory=list)
    dieu: list[Dieu] = field(default_factory=list)   # nếu chương không chia mục
    metadata: dict = field(default_factory=dict)


@dataclass
class VanBan:
    doc_id: str
    loai_van_ban: LoaiVanBan
    so_hieu: str
    ten: str
    ngay_ban_hanh: Optional[str] = None
    ngay_hieu_luc: Optional[str] = None
    co_quan_ban_hanh: Optional[str] = None
    can_cu: list[str] = field(default_factory=list)     # danh sách "Căn cứ..." ở preamble
    chuong: list[Chuong] = field(default_factory=list)
    dieu: list[Dieu] = field(default_factory=list)      # dùng khi văn bản không chia chương

    # quan hệ với văn bản khác — quan trọng cho retrieval/citation
    sua_doi_bo_sung: list[dict] = field(default_factory=list)
    # vd: [{"target_doc": "NĐ 43/2014", "target_dieu": "12", "type": "sua_doi"}]

    phu_luc: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def all_dieu(self) -> list[Dieu]:
        """Trả về flat list toàn bộ Điều, được sắp xếp đúng thứ tự (tránh lỗi các Điều ở Phần không có Chương bị đẩy lên đầu)."""
        result = list(self.dieu)
        for c in self.chuong:
            result.extend(c.dieu)
            for m in c.muc:
                result.extend(m.dieu)
                
        # Sắp xếp lại dựa trên số hiệu Điều (ví dụ: "1", "2", "688")
        def get_dieu_num(d: Dieu):
            import re
            m = re.match(r'^(\d+)', str(d.number))
            return int(m.group(1)) if m else 999999
            
        result.sort(key=get_dieu_num)
        return result


# ---------- Án lệ — cấu trúc hoàn toàn khác ----------

@dataclass
class AnLe:
    doc_id: str
    so_an_le: str                     # "42/2021/AL"
    ten: str
    nguon_an_le: Optional[str] = None
    ngay_cong_bo: Optional[str] = None
    toa_an_ra_quyet_dinh: Optional[str] = None
    vi_tri_noi_dung: Optional[str] = None      # "Đoạn 2 phần Nhận định của Tòa án"

    khai_quat_noi_dung: Optional[str] = None    # tóm tắt ngắn (nếu văn bản có)
    tinh_huong_phap_ly: str = ""
    giai_phap_phap_ly: str = ""
    noi_dung_vu_an: str = ""                    # phần dài, có thể chunk riêng
    noi_dung_an_le_trich_dan: str = ""

    dieu_luat_lien_quan: list[str] = field(default_factory=list)
    tu_khoa: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)