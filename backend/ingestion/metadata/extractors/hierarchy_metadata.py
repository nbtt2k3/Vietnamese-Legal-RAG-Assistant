from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.metadata.models import HierarchyMetadata
from ingestion.parser.structure import VanBan, Chuong, Muc, Dieu, Khoan, Diem
import re


def _safe_part(value: object) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE)
    return value.strip("_") or "unknown"


def _node_id(doc_id: str, node_type: str, *parts: object) -> str:
    suffix = "_".join(_safe_part(part) for part in parts if part not in (None, ""))
    return f"{_safe_part(doc_id)}_{node_type}" + (f"_{suffix}" if suffix else "")

class HierarchyMetadataExtractor(BaseMetadataExtractor):
    def extract(self, node, **kwargs):
        if isinstance(node, VanBan):
            self._ensure_metadata(node)
            node.metadata["hierarchy"] = {
                "node_id": _node_id(node.doc_id, "document"),
                "node_type": "document",
                "parent_id": None,
                "ancestor_ids": [],
                "path": [node.ten],
            }
            for chuong in node.chuong:
                self._process_chuong(chuong, node)
            for dieu in node.dieu:
                self._process_dieu(dieu, HierarchyMetadata(
                    node_id=_node_id(node.doc_id, "document"),
                    node_type="document",
                    path=[node.ten],
                ), node.doc_id)
                
    def _process_chuong(self, chuong: Chuong, document: VanBan):
        doc_id = _node_id(document.doc_id, "document")
        chapter_id = _node_id(document.doc_id, "chuong", chuong.number)
        meta = HierarchyMetadata(
            node_id=chapter_id,
            node_type="chuong",
            parent_id=doc_id,
            ancestor_ids=[doc_id],
            path=[document.ten, f"Chương {chuong.number}: {chuong.title}"],
            phan_number=chuong.phan_number,
            phan_title=chuong.phan_title,
            chuong_number=chuong.number,
            chuong_title=chuong.title
        )
        self._ensure_metadata(chuong)
        chuong.metadata["hierarchy"] = meta.to_dict()
        for muc in chuong.muc:
            self._process_muc(muc, meta, document.doc_id)
        for dieu in chuong.dieu:
            self._process_dieu(dieu, meta, document.doc_id)
            
    def _process_muc(self, muc: Muc, parent_meta: HierarchyMetadata, doc_id: str):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.node_id = _node_id(doc_id, "muc", parent_meta.chuong_number, muc.number)
        meta.node_type = "muc"
        meta.parent_id = parent_meta.node_id
        meta.ancestor_ids = [*parent_meta.ancestor_ids, parent_meta.node_id]
        meta.path = [*parent_meta.path, f"Mục {muc.number}: {muc.title}"]
        meta.muc_number = muc.number
        meta.muc_title = muc.title
        self._ensure_metadata(muc)
        muc.metadata["hierarchy"] = meta.to_dict()
        for dieu in muc.dieu:
            self._process_dieu(dieu, meta, doc_id)
            
    def _process_dieu(self, dieu: Dieu, parent_meta: HierarchyMetadata, doc_id: str):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.node_id = _node_id(doc_id, "dieu", dieu.number)
        meta.node_type = "dieu"
        meta.parent_id = parent_meta.node_id
        meta.ancestor_ids = [*parent_meta.ancestor_ids, parent_meta.node_id]
        meta.path = [*parent_meta.path, f"Điều {dieu.number}: {dieu.title or ''}".strip()]
        meta.dieu_number = dieu.number
        meta.dieu_title = dieu.title
        
        self._ensure_metadata(dieu)
        dieu.metadata["hierarchy"] = meta.to_dict()
        
        for khoan in dieu.khoan:
            self._process_khoan(khoan, meta, doc_id)
            
    def _process_khoan(self, khoan: Khoan, parent_meta: HierarchyMetadata, doc_id: str):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.node_id = _node_id(doc_id, "khoan", parent_meta.dieu_number, khoan.number)
        meta.node_type = "khoan"
        meta.parent_id = parent_meta.node_id
        meta.ancestor_ids = [*parent_meta.ancestor_ids, parent_meta.node_id]
        meta.path = [*parent_meta.path, f"Khoản {khoan.number}"]
        meta.khoan_number = khoan.number
        
        self._ensure_metadata(khoan)
        khoan.metadata["hierarchy"] = meta.to_dict()
        
        for diem in khoan.diem:
            self._process_diem(diem, meta, doc_id)
            
    def _process_diem(self, diem: Diem, parent_meta: HierarchyMetadata, doc_id: str):
        import copy
        meta = copy.deepcopy(parent_meta)
        meta.node_id = _node_id(doc_id, "diem", parent_meta.dieu_number, parent_meta.khoan_number, diem.id)
        meta.node_type = "diem"
        meta.parent_id = parent_meta.node_id
        meta.ancestor_ids = [*parent_meta.ancestor_ids, parent_meta.node_id]
        meta.path = [*parent_meta.path, f"Điểm {diem.id}"]
        meta.diem_id = diem.id
        
        self._ensure_metadata(diem)
        diem.metadata["hierarchy"] = meta.to_dict()

    def _ensure_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}
