from typing import List
from ingestion.chunker.base_chunker import BaseChunker
from ingestion.chunker.models import Chunk
from ingestion.chunker.text_splitter import RecursiveCharacterTextSplitter

class LegalChunker(BaseChunker):
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def _merge_metadata(self, doc_meta: dict, node_meta: dict) -> dict:
        """Merge document metadata (so_hieu, ngay_ban_hanh) with node specific hierarchy."""
        merged = {}
        merged.update(doc_meta)
        
        # Thêm hierarchy
        if "hierarchy" in node_meta:
            merged.update(node_meta["hierarchy"])
        if "statistics" in node_meta:
            merged.update(node_meta["statistics"])
        if "legal" in node_meta:
            merged.update(node_meta["legal"])
        if "source_location" in node_meta:
            merged["source_location"] = dict(node_meta["source_location"])
            
        return merged

    def chunk(self, data: dict) -> List[Chunk]:
        chunks = []
        doc_id = data.get("doc_id", "unknown")
        
        # Document level metadata (so_hieu, loai_van_ban, co_quan_ban_hanh, ...)
        global_meta = dict(data.get("metadata", {}).get("document", {}))
        global_legal_meta = data.get("metadata", {}).get("legal", {})
        # Carry temporal validity and provenance from the document to every chunk.
        # The node-level legal metadata below still supplies article citations.
        global_meta.update(global_legal_meta)
        source_location = data.get("metadata", {}).get("source_location")
        if source_location:
            global_meta["source_location"] = dict(source_location)
        
        # 1. Chunk Điều / Khoản
        for dieu in data.get("dieu", []):
            dieu_number = dieu.get("number", "")
            dieu_meta_raw = dieu.get("metadata", {})
            dieu_merged_meta = self._merge_metadata(global_meta, dieu_meta_raw)
            article_node_id = f"{doc_id}_dieu_{dieu_number}"
            article_parent_id = f"{doc_id}_document"
            article_context = " - ".join(
                part for part in [
                    f"Chuong {dieu.get('chuong_number', '')}: {dieu.get('chuong_title', '')}" if dieu.get("chuong_title") else "",
                    f"Dieu {dieu_number}. {dieu.get('title', '')}".strip(),
                ] if part
            )
            
            # 1a. Intro text của Điều (phần chữ trước khi vào các khoản)
            dieu_text = dieu.get("text", "").strip()
            if dieu_text:
                intro_meta = dict(dieu_merged_meta)
                intro_meta.update({
                    "node_id": article_node_id,
                    "node_type": "dieu",
                    "parent_id": article_parent_id,
                    "ancestor_ids": [article_parent_id],
                    "path": [global_meta.get("ten", doc_id), article_context],
                    "parent_context": article_context,
                    "parent_chunk_id": None,
                    "chunk_part": 1,
                    "chunk_parts": 1,
                })
                full_intro = f"Điều {dieu_number}. {dieu.get('title', '')}\n{dieu_text}".strip()
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_dieu_{dieu_number}_intro",
                    doc_id=doc_id,
                    text=full_intro,
                    metadata=intro_meta
                ))
            
            # 1b. Các Khoản (và Điểm bên trong)
            for khoan in dieu.get("khoan", []):
                khoan_number = khoan.get("number", "")
                khoan_meta_raw = khoan.get("metadata", {})
                khoan_merged_meta = self._merge_metadata(global_meta, khoan_meta_raw)
                
                dieu_title = dieu.get('title', '')
                chuong_title = dieu.get('chuong_title', '')
                chuong_prefix = f"Chương {dieu.get('chuong_number', '')} ({chuong_title}) - " if chuong_title else ""
                dieu_prefix = f"Điều {dieu_number}" + (f" ({dieu_title})" if dieu_title else "") + " - "
                
                parts = [f"{chuong_prefix}{dieu_prefix}Khoản {khoan_number}. {khoan.get('text', '')}"]
                for diem in khoan.get("diem", []):
                    parts.append(f"  Điểm {diem.get('id', '')}) {diem.get('text', '')}")
                
                khoan_full_text = "\n".join(parts).strip()
                khoan_node_id = khoan_merged_meta.get(
                    "node_id",
                    f"{doc_id}_dieu_{dieu_number}_khoan_{khoan_number}",
                )
                khoan_metadata = dict(khoan_merged_meta)
                khoan_metadata.update({
                    "node_id": khoan_node_id,
                    "node_type": "khoan",
                    "parent_id": article_node_id,
                    "ancestor_ids": [article_parent_id, article_node_id],
                    "path": [global_meta.get("ten", doc_id), article_context, f"Khoan {khoan_number}"],
                    "parent_context": article_context,
                    "parent_chunk_id": f"{doc_id}_dieu_{dieu_number}_intro",
                })
                
                # Check nếu Khoản quá dài, cần split. Thường thì Khoản khá ngắn (dưới 1500 char)
                if len(khoan_full_text) > self.splitter.chunk_size:
                    splits = self.splitter.split_text(khoan_full_text)
                    for i, split_txt in enumerate(splits):
                        split_metadata = dict(khoan_metadata)
                        split_metadata.update({"chunk_part": i + 1, "chunk_parts": len(splits)})
                        chunks.append(Chunk(
                            chunk_id=f"{doc_id}_dieu_{dieu_number}_khoan_{khoan_number}_p{i+1}",
                            doc_id=doc_id,
                            text=split_txt,
                            metadata=split_metadata
                        ))
                else:
                    khoan_metadata.update({"chunk_part": 1, "chunk_parts": 1})
                    chunks.append(Chunk(
                        chunk_id=f"{doc_id}_dieu_{dieu_number}_khoan_{khoan_number}",
                        doc_id=doc_id,
                        text=khoan_full_text,
                        metadata=khoan_metadata
                    ))

        # 2. Chunk Phụ lục
        for i, phu_luc in enumerate(data.get("phu_luc", [])):
            pl_text = f"{phu_luc.get('ten_mau', '')}\n{phu_luc.get('noi_dung', '')}".strip()
            if not pl_text:
                continue
                
            pl_meta = dict(global_meta)
            pl_meta["phan_loai"] = "phu_luc"
            pl_meta["ma_mau"] = phu_luc.get("ma_mau", "")
            legal_meta = data.get("metadata", {}).get("legal", {})
            if legal_meta:
                pl_meta.update(legal_meta)
            pl_meta["legal_unit_type"] = "phu_luc"
            pl_meta["legal_role"] = "appendix_form"
            appendix_id = f"{doc_id}_phuluc_{i+1}"
            pl_meta.update({
                "node_id": appendix_id,
                "node_type": "phu_luc",
                "parent_id": f"{doc_id}_document",
                "ancestor_ids": [f"{doc_id}_document"],
                "path": [global_meta.get("ten", doc_id), phu_luc.get("ma_mau", "Phụ lục")],
            })
            
            splits = self.splitter.split_text(pl_text)
            for j, split_txt in enumerate(splits):
                chunks.append(Chunk(
                    chunk_id=f"{doc_id}_phuluc_{i+1}_p{j+1}",
                    doc_id=doc_id,
                    text=split_txt,
                    metadata=pl_meta
                ))

        seen_ids = set()
        duplicate_ids = []
        for chunk in chunks:
            if chunk.chunk_id in seen_ids:
                duplicate_ids.append(chunk.chunk_id)
            seen_ids.add(chunk.chunk_id)
        if duplicate_ids:
            sample = ", ".join(sorted(set(duplicate_ids))[:10])
            raise ValueError(f"Duplicate chunk_id(s) generated for {doc_id}: {sample}")

        return chunks
