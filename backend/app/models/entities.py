from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="INVESTIGATOR") # ADMIN, LEAD_INVESTIGATOR, INVESTIGATOR, ANALYST, AUDITOR
    badge_number = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)

class Case(Base):
    __tablename__ = "cases"
    
    case_id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default="ACTIVE") # ACTIVE, PENDING_REVIEW, ARCHIVED, CLOSED
    classification = Column(String(32), default="RESTRICTED") # UNCLASSIFIED, CONFIDENTIAL, RESTRICTED, TOP_SECRET
    lead_investigator = Column(String(255), nullable=False)
    assigned_team = Column(JSON, default=list) # List of investigator usernames
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)
    
    documents = relationship("Document", back_populates="case", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    
    document_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False)
    filename = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    file_type = Column(String(64), nullable=False) # PDF_SCAN, CSV_CDR, CSV_BANK, CSV_TOLL, IMAGE
    storage_path = Column(Text, nullable=False)
    sha256_hash = Column(String(64), nullable=False)
    extracted_text = Column(Text, nullable=True)
    parsed_metadata = Column(JSON, default=dict)
    uploaded_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=get_utc_now)
    
    case = relationship("Case", back_populates="documents")
    evidence = relationship("Evidence", back_populates="document", uselist=False)

class Evidence(Base):
    __tablename__ = "evidence"
    
    evidence_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False)
    document_id = Column(String(64), ForeignKey("documents.document_id"), nullable=True)
    title = Column(String(255), nullable=False)
    evidence_type = Column(String(64), nullable=False) # FIR_ORIGINAL, CCTV_TRANSCRIPT, CDR_LOG, BANK_RECORD, TOLL_LOG
    sha256_hash = Column(String(64), nullable=False)
    integrity_status = Column(String(32), default="VERIFIED") # VERIFIED, TAMPER_DETECTED, UNVERIFIED
    blockchain_tx_id = Column(String(128), nullable=True)
    blockchain_block_num = Column(Integer, nullable=True)
    blockchain_timestamp = Column(DateTime, nullable=True)
    metadata_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)
    
    case = relationship("Case", back_populates="evidence_items")
    document = relationship("Document", back_populates="evidence")
    custody_events = relationship("CustodyEvent", back_populates="evidence", cascade="all, delete-orphan")

class CustodyEvent(Base):
    __tablename__ = "custody_events"
    
    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evidence_id = Column(String(64), ForeignKey("evidence.evidence_id"), nullable=False)
    action = Column(String(64), nullable=False) # UPLOAD, INTEGRITY_VERIFY, VIEW, EXPORT_COURT, TRANSFER, ANOMALY_FLAG
    performed_by = Column(String(100), nullable=False)
    ip_address = Column(String(45), default="127.0.0.1")
    sha256_at_event = Column(String(64), nullable=False)
    tamper_detected = Column(Boolean, default=False)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)
    
    evidence = relationship("Evidence", back_populates="custody_events")

class BlockchainRecord(Base):
    __tablename__ = "blockchain_records"
    
    tx_hash = Column(String(128), primary_key=True)
    evidence_id = Column(String(64), nullable=False, index=True)
    case_id = Column(String(64), nullable=False)
    sha256_digest = Column(String(64), nullable=False)
    block_number = Column(Integer, nullable=False)
    sealed_by = Column(String(100), nullable=False)
    contract_address = Column(String(64), default="0x71C2B890a8813C124231EVID_LEDGER_MOCK")
    timestamp = Column(DateTime, default=get_utc_now)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=True)
    case_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), default="127.0.0.1")
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=get_utc_now)
