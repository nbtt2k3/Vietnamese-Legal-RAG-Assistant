"""
Parser cho Nghị quyết (thường là Nghị quyết của HĐTP TANDTC hướng dẫn áp dụng
một Điều cụ thể của Bộ luật). Điểm khác biệt: cần link chặt với Điều luật gốc.
"""
import re
from .legal_parser import LegalParser
from .structure import LoaiVanBan, VanBan


class ResolutionParser(LegalParser):
    LOAI_VAN_BAN = LoaiVanBan.NGHI_QUYET

    RE_HUONG_DAN = re.compile(
        r'[Hh]ướng dẫn\s+(?:áp dụng\s+)?'
        r'(?:khoản\s+(\d+)\s+)?[Đđ]iều\s+(\d+)\s+'
        r'(?:của\s+)?(Bộ luật Dân sự|Bộ luật [^\d\n,]+)',
    )

    def _extract_preamble(self, preamble_text: str, van_ban: VanBan):
        super()._extract_preamble(preamble_text, van_ban)
        full_text = preamble_text + "\n" + (van_ban.ten or "")
        for m in self.RE_HUONG_DAN.finditer(full_text):
            van_ban.sua_doi_bo_sung.append({
                "type": "huong_dan_ap_dung",
                "target_khoan": m.group(1),
                "target_dieu": m.group(2),
                "target_van_ban": m.group(3).strip(),
            })