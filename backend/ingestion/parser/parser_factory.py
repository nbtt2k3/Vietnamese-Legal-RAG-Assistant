"""
Điểm vào duy nhất cho toàn bộ pipeline gọi parser theo loại văn bản.
"""
from .civil_code_parser import CivilCodeParser
from .decree_parser import DecreeParser
from .circular_parser import CircularParser
from .resolution_parser import ResolutionParser
from .case_law_parser import CaseLawParser
from .structure import LoaiVanBan


class ParserFactory:
    _registry = {
        LoaiVanBan.BO_LUAT: CivilCodeParser,
        LoaiVanBan.NGHI_DINH: DecreeParser,
        LoaiVanBan.THONG_TU: CircularParser,
        LoaiVanBan.NGHI_QUYET: ResolutionParser,
        LoaiVanBan.AN_LE: CaseLawParser,
    }

    @classmethod
    def get_parser(cls, loai_van_ban: str | LoaiVanBan):
        if isinstance(loai_van_ban, str):
            loai_van_ban = LoaiVanBan(loai_van_ban)
        parser_cls = cls._registry.get(loai_van_ban)
        if not parser_cls:
            raise ValueError(f"Không có parser cho loại văn bản: {loai_van_ban}")
        return parser_cls()