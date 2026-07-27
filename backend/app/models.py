from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

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

class DocumentRelationship(Base):
    __tablename__ = "document_relationships"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_doc_id = Column(String, ForeignKey("documents.doc_id"), index=True)
    target_doc_id = Column(String, ForeignKey("documents.doc_id"), index=True)
    target_doc_ref = Column(Text, index=True)
    relationship_type = Column(String, index=True) # e.g., 'sua_doi', 'thay_the', 'huong_dan'
    
    # Phase 3: Article-level relationship
    source_article_id = Column(String, index=True)
    target_article_id = Column(String, index=True)
    note = Column(Text)
    relation_source = Column(String)
    
    # Optional relationships for ORM convenience
    source_doc = relationship("Document", foreign_keys=[source_doc_id], backref="targets")
    target_doc = relationship("Document", foreign_keys=[target_doc_id], backref="sources")

from sqlalchemy import DateTime, ForeignKey
import datetime
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True)
    role = Column(String)  # 'user' or 'ai'
    content = Column(Text)
    msg_metadata = Column(Text, nullable=True) # store JSON data for AI messages
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    conversation = relationship("Conversation", back_populates="messages")
