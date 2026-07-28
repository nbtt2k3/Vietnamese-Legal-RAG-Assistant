"""
Parser cho Bộ luật Dân sự — kế thừa LegalParser gần như nguyên vẹn
vì BLDS có cấu trúc đầy đủ và chuẩn nhất (Phần > Chương > Mục > Điều).
"""
from .legal_parser import LegalParser
from .structure import LoaiVanBan, VanBan


class CivilCodeParser(LegalParser):
    LOAI_VAN_BAN = LoaiVanBan.BO_LUAT

    def _extract_preamble(self, preamble_text: str, van_ban: VanBan):
        # Bộ luật không có "Căn cứ..." như Nghị định, mà có Quốc hội ban hành + số hiệu ở đầu
        super()._extract_preamble(preamble_text, van_ban)
        for line in preamble_text.split('\n'):
            line = line.strip()
            if 'Quốc hội' in line and 'ban hành' in line.lower():
                van_ban.co_quan_ban_hanh = "Quốc hội"

    def _post_process(self, van_ban: VanBan):
        # Validate: Cảnh báo nếu số lượng Điều quá ít (dưới 100 điều đối với một Bộ Luật)
        total_dieu = len(van_ban.all_dieu())
        if total_dieu < 100:
            print(f"[WARNING] CivilCodeParser: chỉ parse được {total_dieu} Điều, "
                  f"có thể lỗi định dạng nặng — kiểm tra lại file input.")