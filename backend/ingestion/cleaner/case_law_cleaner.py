from ingestion.cleaner.base_cleaner import BaseCleaner
from ingestion.parser.structure import AnLe


class CaseLawCleaner(BaseCleaner):
    def clean(self, doc: AnLe) -> AnLe:
        if doc.ten:
            doc.ten = self.apply_rules(doc.ten)
        if doc.nguon_an_le:
            doc.nguon_an_le = self.apply_rules(doc.nguon_an_le)
        if doc.toa_an_ra_quyet_dinh:
            doc.toa_an_ra_quyet_dinh = self.apply_rules(doc.toa_an_ra_quyet_dinh)
        if doc.vi_tri_noi_dung:
            doc.vi_tri_noi_dung = self.apply_rules(doc.vi_tri_noi_dung)
        if doc.khai_quat_noi_dung:
            doc.khai_quat_noi_dung = self.apply_rules(doc.khai_quat_noi_dung)
        if doc.tinh_huong_phap_ly:
            doc.tinh_huong_phap_ly = self.apply_rules(doc.tinh_huong_phap_ly)
        if doc.giai_phap_phap_ly:
            doc.giai_phap_phap_ly = self.apply_rules(doc.giai_phap_phap_ly)
        if doc.noi_dung_vu_an:
            doc.noi_dung_vu_an = self.apply_rules(doc.noi_dung_vu_an)
        if doc.noi_dung_an_le_trich_dan:
            doc.noi_dung_an_le_trich_dan = self.apply_rules(doc.noi_dung_an_le_trich_dan)

        doc.dieu_luat_lien_quan = [self.apply_rules(item) for item in doc.dieu_luat_lien_quan]
        doc.tu_khoa = [self.apply_rules(item) for item in doc.tu_khoa]
        return doc
