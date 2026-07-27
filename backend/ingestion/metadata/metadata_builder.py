"""
Metadata Builder Orchestrator.
"""
from ingestion.parser.structure import VanBan, AnLe

class MetadataBuilder:
    def __init__(self, extractors):
        self.extractors = extractors
        
    def build(self, document):
        """
        Duyệt qua document và chạy tất cả extractors lên từng node.
        """
        # Áp dụng cho cấp cao nhất
        for extractor in self.extractors:
            extractor.extract(document)
            
        # Nếu là VanBan, duyệt các cấp con
        if isinstance(document, VanBan):
            for dieu in document.all_dieu():
                for extractor in self.extractors:
                    extractor.extract(dieu, document=document)
                for khoan in dieu.khoan:
                    for extractor in self.extractors:
                        extractor.extract(khoan, document=document, dieu=dieu)
                    for diem in khoan.diem:
                        for extractor in self.extractors:
                            extractor.extract(diem, document=document, dieu=dieu, khoan=khoan)
        elif isinstance(document, AnLe):
            for extractor in self.extractors:
                extractor.extract(document, document=document)
                            
        return document
