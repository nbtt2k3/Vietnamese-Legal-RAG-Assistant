from ingestion.cleaner.base_cleaner import BaseCleaner
from ingestion.parser.structure import VanBan

class LegalCleaner(BaseCleaner):
    def clean(self, doc: VanBan) -> VanBan:
        if doc.ten:
            doc.ten = self.apply_rules(doc.ten)
        
        for c in doc.chuong:
            if c.title:
                c.title = self.apply_rules(c.title)
            for m in c.muc:
                if m.title:
                    m.title = self.apply_rules(m.title)
                self._clean_dieu_list(m.dieu)
            self._clean_dieu_list(c.dieu)
            
        self._clean_dieu_list(doc.dieu)
        
        for p in doc.phu_luc:
            if p.get("ten_mau"):
                p["ten_mau"] = self.apply_rules(p["ten_mau"])
            if p.get("noi_dung"):
                p["noi_dung"] = self.apply_rules(p["noi_dung"])
                
        return doc

    def _clean_dieu_list(self, dieu_list):
        for d in dieu_list:
            if d.title:
                d.title = self.apply_rules(d.title)
            if d.text:
                d.text = self.apply_rules(d.text)
            for k in d.khoan:
                if k.text:
                    k.text = self.apply_rules(k.text)
                for diem in k.diem:
                    if diem.text:
                        diem.text = self.apply_rules(diem.text)