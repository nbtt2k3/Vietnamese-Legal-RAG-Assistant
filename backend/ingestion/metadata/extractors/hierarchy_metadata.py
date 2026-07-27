from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.metadata.models import HierarchyMetadata
from ingestion.parser.structure import VanBan, Chuong, Muc, Dieu, Khoan, Diem

class HierarchyMetadataExtractor(BaseMetadataExtractor):
    def extract(self, node, **kwargs):
        if isinstance(node, VanBan):
            for chuong in node.chuong:
                self._process_chuong(chuong)
            for dieu in node.dieu:
                self._process_dieu(dieu, HierarchyMetadata())
                
    def _process_chuong(self, chuong: Chuong):
        meta = HierarchyMetadata(
            phan_number=chuong.phan_number,
            phan_title=chuong.phan_title,
            chuong_number=chuong.number,
            chuong_title=chuong.title
        )
        for muc in chuong.muc:
            self._process_muc(muc, meta)
        for dieu in chuong.dieu:
            self._process_dieu(dieu, meta)
            
    def _process_muc(self, muc: Muc, parent_meta: HierarchyMetadata):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.muc_number = muc.number
        meta.muc_title = muc.title
        for dieu in muc.dieu:
            self._process_dieu(dieu, meta)
            
    def _process_dieu(self, dieu: Dieu, parent_meta: HierarchyMetadata):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.dieu_number = dieu.number
        meta.dieu_title = dieu.title
        
        self._ensure_metadata(dieu)
        dieu.metadata["hierarchy"] = meta.to_dict()
        
        for khoan in dieu.khoan:
            self._process_khoan(khoan, meta)
            
    def _process_khoan(self, khoan: Khoan, parent_meta: HierarchyMetadata):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.khoan_number = khoan.number
        
        self._ensure_metadata(khoan)
        khoan.metadata["hierarchy"] = meta.to_dict()
        
        for diem in khoan.diem:
            self._process_diem(diem, meta)
            
    def _process_diem(self, diem: Diem, parent_meta: HierarchyMetadata):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.diem_id = diem.id
        
        self._ensure_metadata(diem)
        diem.metadata["hierarchy"] = meta.to_dict()

    def _ensure_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
