from sqlalchemy import Column, String, Text

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    doc_id = Column(String, primary_key=True, index=True)
    so_hieu = Column(String, index=True)
    ten = Column(Text)
    loai_van_ban = Column(String, index=True)
    ngay_ban_hanh = Column(String, index=True)
    ngay_hieu_luc = Column(String, index=True)
    co_quan_ban_hanh = Column(String)
    validity_status = Column(String, index=True)

    # Phase 3: Temporal Layer & Reliability
    url = Column(String)
    checksum = Column(String)
    verified_at = Column(String)
    effective_from = Column(String)
    effective_to = Column(String)
    repeal_reason = Column(String)
    source_of_validity = Column(String)
    source_file = Column(String)
    source_format = Column(String)
    source_url = Column(String)
    source_checksum_sha256 = Column(String)
    source_verification_status = Column(String, index=True)
    source_verified_at = Column(String)
    validity_basis = Column(Text)
    validity_confidence = Column(String, index=True)
    validity_checked_at = Column(String)
