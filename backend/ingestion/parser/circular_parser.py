"""
Parser cho Thông tư — kế thừa toàn bộ logic từ LegalParser.
Việc tách Phụ lục (mẫu biểu, bảng số liệu) giờ đã được xử lý chung
ở base class (LegalParser.parse() -> _split_phu_luc), áp dụng cho
mọi loại văn bản (Bộ luật, Nghị định, Thông tư, Nghị quyết), nên
không cần override riêng ở đây nữa.
"""
from .legal_parser import LegalParser
from .structure import LoaiVanBan, VanBan


class CircularParser(LegalParser):
    LOAI_VAN_BAN = LoaiVanBan.THONG_TU

    def _extract_preamble(self, preamble_text: str, van_ban: VanBan):
        super()._extract_preamble(preamble_text, van_ban)
        
        # Thông tư thường hướng dẫn thi hành Nghị định/Luật và có phần "Theo đề nghị của..."
        grounds = []
        for line in preamble_text.split("\n"):
            line = line.strip()
            if line.lower().startswith("căn cứ") or line.lower().startswith("theo đề nghị"):
                grounds.append(line)
        if grounds:
            van_ban.metadata["legal_grounds"] = grounds