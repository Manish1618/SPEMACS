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
    # E.164 (e.g. +919876543210). Used to reach the Crime Branch head by SMS.
    phone_number = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_utc_now)

    # Brute-force controls. locked_until is set once failed_login_count reaches the
    # configured threshold; both reset on a successful login.
    failed_login_count = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=get_utc_now)

    # Bumped on password change, logout-everywhere and deactivation. Access tokens
    # carry the version they were minted under, so raising it revokes every token
    # already in circulation without keeping a blacklist.
    token_version = Column(Integer, default=0, nullable=False)

    sessions = relationship(
        "RefreshSession", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshSession(Base):
    """One browser session, addressed by an opaque refresh token.

    Only the SHA-256 of the token is stored, so a database read does not hand out
    usable sessions. Every refresh rotates the token; presenting a token that has
    already been rotated means it leaked, and revokes the whole chain.
    """

    __tablename__ = "refresh_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    issued_at = Column(DateTime, default=get_utc_now, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String(64), nullable=True)
    rotated_from = Column(String(36), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    user = relationship("User", back_populates="sessions")

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


# ---------------------------------------------------------------------------
# Investigative domain model.
#
# Entities, relationships and events were previously Python literals inside
# ingestion.py / map_timeline.py, which made them unqueryable. They are first
# class rows now so the Copilot's planner has something to actually plan over.
# ---------------------------------------------------------------------------

class Entity(Base):
    __tablename__ = "entities"

    entity_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), index=True, nullable=False)
    label = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # PERSON, PHONE, VEHICLE, ORGANIZATION, LOCATION, ACCOUNT, CASE
    aliases = Column(JSON, default=list)
    properties = Column(JSON, default=dict)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Entity resolution: when a duplicate is merged, canonical_id points at the survivor.
    canonical_id = Column(String(64), nullable=True, index=True)
    merge_confidence = Column(Float, nullable=True)
    merged_by = Column(String(100), nullable=True)
    first_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)


class Relationship(Base):
    __tablename__ = "relationships"

    rel_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), index=True, nullable=False)
    source_id = Column(String(64), ForeignKey("entities.entity_id"), nullable=False, index=True)
    target_id = Column(String(64), ForeignKey("entities.entity_id"), nullable=False, index=True)
    rel_type = Column(String(48), nullable=False, index=True)
    confidence = Column(Float, default=1.0)
    # OBSERVED = directly recorded in a source. INFERRED = derived analytically.
    # Section 29 of the spec: never present an inference as an established fact.
    assertion_kind = Column(String(24), default="OBSERVED")
    evidence_ids = Column(JSON, default=list)
    # valid_from is what makes "relationships that appeared AFTER event X" answerable.
    valid_from = Column(DateTime, nullable=True, index=True)
    valid_to = Column(DateTime, nullable=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)


class Event(Base):
    __tablename__ = "events"

    event_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    event_type = Column(String(48), nullable=False, index=True)  # CALL, TRANSACTION, MEETING, VEHICLE_SIGHTING, OSINT_PUBLICATION, EVIDENCE_REGISTERED
    timestamp = Column(DateTime, nullable=False, index=True)
    location_name = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    related_entities = Column(JSON, default=list)
    evidence_id = Column(String(64), nullable=True, index=True)
    summary = Column(Text, default="")
    confidence = Column(Float, default=1.0)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=get_utc_now)


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    hypothesis_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    statement = Column(Text, nullable=False)
    # OPEN, UNDER_REVIEW, SUPPORTED, DISPUTED, DISMISSED, RESOLVED
    status = Column(String(24), default="OPEN")
    created_by = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)


class OsintRecord(Base):
    __tablename__ = "osint_records"

    record_id = Column(String(64), primary_key=True, index=True)
    case_id = Column(String(64), index=True, nullable=False)
    entity_id = Column(String(64), nullable=True, index=True)
    query_term = Column(String(255), nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    source_type = Column(String(48), default="NEWS")  # NEWS, CORPORATE_REGISTRY, COURT_RECORD, GOVERNMENT, AGGREGATOR
    published_at = Column(DateTime, nullable=True)
    retrieved_at = Column(DateTime, default=get_utc_now)
    reliability = Column(Float, default=0.5)
    confidence = Column(Float, default=0.5)
    claims = Column(JSON, default=list)
    content_hash = Column(String(64), nullable=False)
    # Source-independence analysis (spec section 16): if this report derives from
    # another, origin_record_id names the upstream original.
    origin_record_id = Column(String(64), nullable=True, index=True)
    is_derivative = Column(Boolean, default=False)
    requires_human_verification = Column(Boolean, default=True)
    evidence_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)


class LedgerBlock(Base):
    """Permissioned append-only ledger. Each block hash-chains to its predecessor,
    so altering any historic custody record invalidates every block after it."""

    __tablename__ = "ledger_blocks"

    block_number = Column(Integer, primary_key=True, autoincrement=False)
    previous_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    block_hash = Column(String(64), nullable=False, index=True)
    sealed_by = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=get_utc_now)


class NotificationLog(Base):
    """Every access alert the platform attempted to send.

    Kept separate from AuditLog: the audit log records that an event happened,
    this records that somebody was told about it, and whether that succeeded.
    """

    __tablename__ = "notification_log"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(64), index=True, nullable=False)
    severity = Column(String(16), default="INFO", nullable=False)  # INFO or HIGH
    channel = Column(String(16), nullable=False)                   # EMAIL or SMS
    recipient = Column(String(255), nullable=False)
    recipient_username = Column(String(100), nullable=True)
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)
    # SENT, FAILED, or SKIPPED when no recipient or channel was configured.
    status = Column(String(16), default="SENT", nullable=False)
    error = Column(Text, nullable=True)
    provider = Column(String(32), nullable=True)
    actor_username = Column(String(100), index=True, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=get_utc_now, index=True)
