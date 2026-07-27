"""
Parser cho Nghị định — khác Bộ luật ở chỗ:
- Luôn có phần "Căn cứ..." dài ở đầu
- Cần track quan hệ sửa đổi/bổ sung/hướng dẫn văn bản khác
"""
import re
from .legal_parser import LegalParser
from .structure import LoaiVanBan, VanBan


class DecreeParser(LegalParser):
    LOAI_VAN_BAN = LoaiVanBan.NGHI_DINH

    RE_RELATION = re.compile(
        r'(Sửa đổi|Bổ sung|Bãi bỏ|Hướng dẫn thi hành)\s+'
        r'(?:một số điều của\s+)?'
        r'(Nghị định|Luật|Bộ luật)\s+'
        r'(?:(.*?)\s+)?'
        r'(?:số\s+)?([\d]+/[\d]+/[A-ZĐ\-\d]+)',
        re.IGNORECASE
    )

    def _extract_preamble(self, preamble_text: str, van_ban: VanBan):
        super()._extract_preamble(preamble_text, van_ban)
        # Tên nghị định thường chứa luôn quan hệ, vd:
        # "Nghị định sửa đổi, bổ sung một số điều của Nghị định số 43/2014/NĐ-CP"
        full_text = preamble_text + "\n" + (van_ban.ten or "")
        for m in self.RE_RELATION.finditer(full_text):
            van_ban.sua_doi_bo_sung.append({
                "type": m.group(1).lower(),
                "target_type": m.group(2),
                "target_so_hieu": m.group(4),
            })
            
        # Parse "Căn cứ..." (Legal grounds)
        grounds = []
        for line in preamble_text.split("\n"):
            line = line.strip()
            if line.lower().startswith("căn cứ"):
                grounds.append(line)
        if grounds:
            van_ban.metadata["legal_grounds"] = grounds

    def _post_process(self, van_ban: VanBan):
        # Nghị định thường không có Chương -> đảm bảo không lỗi khi all_dieu() rỗng
        if not van_ban.all_dieu():
            print(f"[WARNING] DecreeParser: văn bản {van_ban.so_hieu} không parse được Điều nào.")