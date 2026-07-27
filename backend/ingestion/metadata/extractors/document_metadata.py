import re

from ingestion.metadata.base_builder import BaseMetadataExtractor
from ingestion.metadata.models import DocumentMetadata, LegalMetadata
from ingestion.parser.structure import VanBan, AnLe

class DocumentMetadataExtractor(BaseMetadataExtractor):
    def extract(self, node, **kwargs):
        # Chỉ xử lý cấp độ cao nhất: VanBan hoặc AnLe
        if isinstance(node, VanBan):
            loai_vb_val = node.loai_van_ban.value if hasattr(node.loai_van_ban, "value") else node.loai_van_ban
            doc_meta = DocumentMetadata(
                doc_id=node.doc_id,
                loai_van_ban=loai_vb_val,
                so_hieu=node.so_hieu,
                ten=node.ten,
                ngay_ban_hanh=node.ngay_ban_hanh,
                ngay_hieu_luc=node.ngay_hieu_luc,
                co_quan_ban_hanh=node.co_quan_ban_hanh
            )
            self._ensure_legal_metadata(node)
            node.metadata["document"] = doc_meta.to_dict()
            
        elif isinstance(node, AnLe):
            doc_meta = DocumentMetadata(
                doc_id=node.doc_id,
                loai_van_ban="an_le",
                so_hieu=node.so_an_le,
                ten=node.ten,
                ngay_ban_hanh=node.ngay_cong_bo,
                co_quan_ban_hanh=self._extract_case_law_issuer(node)
            )
            self._ensure_legal_metadata(node)
            node.metadata["document"] = doc_meta.to_dict()
            
    def _ensure_legal_metadata(self, node):
        if not hasattr(node, "metadata") or node.metadata is None:
            node.metadata = {}

    def _extract_case_law_issuer(self, node: AnLe) -> str | None:
        texts = [
            getattr(node, "toa_an_ra_quyet_dinh", None),
            getattr(node, "nguon_an_le", None),
        ]

        patterns = [
            r"Tòa án nhân dân tối cao",
            r"Tòa án nhân dân cấp cao(?: tại [^.;,\n]+)?",
            r"Tòa án nhân dân [^.;,\n]+",
            r"Hội đồng Thẩm phán Tòa án nhân dân tối cao",
        ]

        for text in texts:
            if not text:
                continue
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    value = match.group(0).strip()
                    if "Hội đồng Thẩm phán Tòa án nhân dân tối cao" in value:
                        return "Tòa án nhân dân tối cao"
                    return value

        return getattr(node, "toa_an_ra_quyet_dinh", None)
