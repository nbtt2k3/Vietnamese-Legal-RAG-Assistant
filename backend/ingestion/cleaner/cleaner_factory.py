from ingestion.parser.structure import LoaiVanBan
from ingestion.cleaner.legal_cleaner import LegalCleaner
from ingestion.cleaner.case_law_cleaner import CaseLawCleaner

class CleanerFactory:
    @staticmethod
    def get_cleaner(loai_van_ban: str):
        if loai_van_ban == LoaiVanBan.AN_LE.value:
            return CaseLawCleaner()
        return LegalCleaner()