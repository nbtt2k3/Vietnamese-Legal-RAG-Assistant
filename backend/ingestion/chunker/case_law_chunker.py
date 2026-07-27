from typing import List
from ingestion.chunker.base_chunker import BaseChunker
from ingestion.chunker.models import Chunk
from ingestion.chunker.text_splitter import RecursiveCharacterTextSplitter

class CaseLawChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _merge_metadata(self, global_meta: dict, keyword_meta: dict, phan_loai: str) -> dict:
        merged = {}
        merged.update(global_meta)
        merged["phan_loai"] = phan_loai
        
        # Án lệ có search keywords
        if "keywords" in keyword_meta:
            merged["keywords"] = keyword_meta["keywords"]

        legal_meta = keyword_meta.get("__legal__", {})
        if legal_meta:
            merged.update(legal_meta)
            
        return merged

    def chunk(self, data: dict) -> List[Chunk]:
        chunks = []
        doc_id = data.get("doc_id", "unknown")
        
        global_meta = data.get("metadata", {}).get("document", {})
        keyword_meta = data.get("metadata", {}).get("search", {})
        legal_meta = data.get("metadata", {}).get("legal", {})
        keyword_meta = dict(keyword_meta)
        keyword_meta["__legal__"] = legal_meta
        
        # 1. Tình huống pháp lý
        tinh_huong = data.get("tinh_huong_phap_ly")
        if tinh_huong:
            meta = self._merge_metadata(global_meta, keyword_meta, "tinh_huong_phap_ly")
            meta["legal_unit_type"] = "an_le_tinh_huong"
            meta["legal_role"] = "case_issue"
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_tinh_huong",
                doc_id=doc_id,
                text=tinh_huong.strip(),
                metadata=meta
            ))
            
        # 2. Giải pháp pháp lý
        giai_phap = data.get("giai_phap_phap_ly")
        if giai_phap:
            meta = self._merge_metadata(global_meta, keyword_meta, "giai_phap_phap_ly")
            meta["legal_unit_type"] = "an_le_giai_phap"
            meta["legal_role"] = "case_holding"
            chunks.append(Chunk(
                chunk_id=f"{doc_id}_giai_phap",
                doc_id=doc_id,
                text=giai_phap.strip(),
                metadata=meta
            ))
            
        # 3. Nội dung án lệ trích dẫn
        trich_dan = data.get("noi_dung_an_le_trich_dan")
        if trich_dan:
            meta = self._merge_metadata(global_meta, keyword_meta, "an_le_trich_dan")
            meta["legal_unit_type"] = "an_le_trich_dan"
            meta["legal_role"] = "case_reasoning"
            splits = self.splitter.split_text(trich_dan.strip())
            for i, split_txt in enumerate(splits):
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_trich_dan_p{i+1}",
                    doc_id=doc_id,
                    text=split_txt,
                    metadata=meta
                ))

        # 4. Nội dung vụ án (Rất dài, bắt buộc cắt)
        vu_an = data.get("noi_dung_vu_an")
        if vu_an:
            meta = self._merge_metadata(global_meta, keyword_meta, "noi_dung_vu_an")
            meta["legal_unit_type"] = "an_le_vu_an"
            meta["legal_role"] = "case_facts"
            splits = self.splitter.split_text(vu_an.strip())
            for i, split_txt in enumerate(splits):
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_vu_an_p{i+1}",
                    doc_id=doc_id,
                    text=split_txt,
                    metadata=meta
                ))
                
        return chunks
