from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentRelationship(Base):
    __tablename__ = "document_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_doc_id = Column(String, ForeignKey("documents.doc_id"), index=True)
    target_doc_id = Column(String, ForeignKey("documents.doc_id"), index=True)
    target_doc_ref = Column(Text, index=True)
    relationship_type = Column(String, index=True)

    # Phase 3: Article-level relationship
    source_article_id = Column(String, index=True)
    target_article_id = Column(String, index=True)
    note = Column(Text)
    relation_source = Column(String)

    source_doc = relationship("Document", foreign_keys=[source_doc_id], backref="targets")
    target_doc = relationship("Document", foreign_keys=[target_doc_id], backref="sources")
