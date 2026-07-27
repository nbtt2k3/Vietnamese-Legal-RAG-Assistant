"""
Metadata models for Legal RAG.
These models define the schema for metadata attached to VanBan, Dieu, Khoan, etc.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional

@dataclass
class DocumentMetadata:
    doc_id: str = ""
    loai_van_ban: str = ""
    so_hieu: str = ""
    ten: str = ""
    ngay_ban_hanh: Optional[str] = None
    ngay_hieu_luc: Optional[str] = None
    co_quan_ban_hanh: Optional[str] = None

    def to_dict(self):
        return asdict(self)

@dataclass
class HierarchyMetadata:
    phan_number: Optional[str] = None
    phan_title: Optional[str] = None
    chuong_number: Optional[str] = None
    chuong_title: Optional[str] = None
    muc_number: Optional[str] = None
    muc_title: Optional[str] = None
    dieu_number: Optional[str] = None
    dieu_title: Optional[str] = None
    khoan_number: Optional[str] = None
    diem_id: Optional[str] = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

@dataclass
class StatisticsMetadata:
    word_count: int = 0
    char_count: int = 0

    def to_dict(self):
        return asdict(self)

@dataclass
class KeywordMetadata:
    keywords: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

@dataclass
class LegalMetadata:
    document: Optional[DocumentMetadata] = None
    hierarchy: Optional[HierarchyMetadata] = None
    statistics: Optional[StatisticsMetadata] = None
    search: Optional[KeywordMetadata] = None
    
    def to_dict(self):
        res = {}
        if self.document:
            res["document"] = self.document.to_dict()
        if self.hierarchy:
            res["hierarchy"] = self.hierarchy.to_dict()
        if self.statistics:
            res["statistics"] = self.statistics.to_dict()
        if self.search:
            res["search"] = self.search.to_dict()
        return res
