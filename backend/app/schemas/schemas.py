from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    # Lets the browser schedule a silent refresh instead of waiting for a 401.
    expires_in_minutes: int
    user: Dict[str, Any]

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)

class AuthConfig(BaseModel):
    """Public bootstrap for the login screen."""
    demo_mode: bool
    # Populated only while DEMO_MODE is on, so a production build never shows them.
    demo_credentials: List[Dict[str, str]] = []
    min_password_length: int
    access_token_expire_minutes: int

class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=1, max_length=200)

# --- User administration (ADMIN only) ---
# A light shape check rather than pydantic's EmailStr, which would pull in the
# email-validator package for no benefit here.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

# CRIME_BRANCH_HEAD receives the access alerts. Whoever holds it is the
# notification recipient, so changing who gets alerted is an admin action.
VALID_ROLES = [
    "ADMIN",
    "CRIME_BRANCH_HEAD",
    "LEAD_INVESTIGATOR",
    "INVESTIGATOR",
    "ANALYST",
    "AUDITOR",
]

# E.164, e.g. +919876543210.
_PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"

class UserOut(BaseModel):
    id: str
    username: str
    email: str
    full_name: str
    role: str
    badge_number: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    is_locked: bool = False
    accessible_cases: List[str] = []

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str = Field(..., max_length=255, pattern=_EMAIL_PATTERN)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = "INVESTIGATOR"
    badge_number: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, pattern=_PHONE_PATTERN)
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(VALID_ROLES)}")
        return value

class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=255, pattern=_EMAIL_PATTERN)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = None
    badge_number: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, pattern=_PHONE_PATTERN)
    is_active: Optional[bool] = None
    unlock: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _known_role(cls, value):
        if value is not None and value not in VALID_ROLES:
            raise ValueError(f"role must be one of: {', '.join(VALID_ROLES)}")
        return value

class PasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=1, max_length=200)

class TeamUpdate(BaseModel):
    assigned_team: List[str] = []

class AccessLogEntry(BaseModel):
    id: str
    username: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    case_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = {}
    # AuditLog names this column `timestamp`; the API exposes it as created_at
    # so both logs read the same way on the client.
    created_at: datetime = Field(..., validation_alias="timestamp")

    class Config:
        from_attributes = True
        populate_by_name = True

class NotificationLogEntry(BaseModel):
    id: str
    event_type: str
    severity: str
    channel: str
    recipient: str
    recipient_username: Optional[str] = None
    subject: Optional[str] = None
    status: str
    error: Optional[str] = None
    provider: Optional[str] = None
    actor_username: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Case Schemas ---
class CaseCreate(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    classification: Optional[str] = "RESTRICTED"
    lead_investigator: str

class CaseResponse(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    status: str
    classification: str
    lead_investigator: str
    assigned_team: List[str] = []
    created_at: datetime
    document_count: Optional[int] = 0
    evidence_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

# --- Document & Evidence Schemas ---
class DocumentResponse(BaseModel):
    document_id: str
    case_id: str
    filename: str
    title: str
    file_type: str
    sha256_hash: str
    extracted_text: Optional[str] = None
    uploaded_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class CustodyEventResponse(BaseModel):
    event_id: str
    evidence_id: str
    action: str
    performed_by: str
    ip_address: str
    sha256_at_event: str
    tamper_detected: bool
    details: Dict[str, Any] = {}
    created_at: datetime
    
    class Config:
        from_attributes = True

class EvidenceResponse(BaseModel):
    evidence_id: str
    case_id: str
    document_id: Optional[str] = None
    title: str
    evidence_type: str
    sha256_hash: str
    integrity_status: str
    blockchain_tx_id: Optional[str] = None
    blockchain_block_num: Optional[int] = None
    blockchain_timestamp: Optional[datetime] = None
    metadata_payload: Dict[str, Any] = {}
    created_at: datetime
    custody_events: List[CustodyEventResponse] = []
    
    class Config:
        from_attributes = True

class IntegrityVerificationResult(BaseModel):
    evidence_id: str
    title: str
    stored_hash: str
    recalculated_hash: str
    blockchain_hash: Optional[str] = None
    blockchain_tx_id: Optional[str] = None
    integrity_status: str # VERIFIED or TAMPER_DETECTED
    is_valid: bool
    verified_at: datetime
    message: str

# --- Graph & Workspace Schemas ---
class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: str # Person, Phone, Vehicle, Organization, Location, Account, Event
    properties: Dict[str, Any] = {}
    is_bridge: Optional[bool] = False
    is_hub: Optional[bool] = False
    centrality_score: Optional[float] = 0.0
    community_id: Optional[int] = 0

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    relationship_type: str
    properties: Dict[str, Any] = {}
    confidence: Optional[float] = 1.0
    evidence_ids: List[str] = []

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, Any] = {}

class MapEventFeature(BaseModel):
    event_id: str
    case_id: str
    title: str
    event_type: str
    latitude: float
    longitude: float
    location_name: str
    timestamp: datetime
    related_entities: List[str] = []
    evidence_id: Optional[str] = None
    confidence: float = 1.0

class TimelineEvent(BaseModel):
    id: str
    case_id: str
    title: str
    event_type: str
    start_time: datetime
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    related_entities: List[str] = []
    evidence_id: Optional[str] = None
    summary: str
    confidence: float = 1.0

# --- AI Investigator Schemas ---
class AIInvestigateRequest(BaseModel):
    case_id: str
    query: str
    history: List[Dict[str, str]] = [] # [{"role": "user", "content": "..."}, ...]
    # "standard" answers the question; "full" also attaches the complete record set
    # (entity roster, chronology, evidence register, analytics) to the same reply.
    detail_level: str = "standard"

class Citation(BaseModel):
    evidence_id: str
    document_id: Optional[str] = None
    source_title: str
    reference_location: str # e.g. "Line 42" or "Row 1004"
    quote_or_claim: str
    confidence: float = 0.95

class HighlightAction(BaseModel):
    target_type: str # graph_nodes, map_coordinates, timeline_event_ids
    node_ids: List[str] = []
    event_ids: List[str] = []
    coordinates: List[List[float]] = [] # [[lat, lon], ...]
    description: str

class AIInvestigateResponse(BaseModel):
    answer: str
    is_ambiguous: bool = False
    clarification_options: List[str] = []
    citations: List[Citation] = []
    counter_evidence: List[Dict[str, Any]] = []
    evidence_gaps: List[str] = []
    suggested_next_steps: List[str] = []
    confidence_level: str # HIGH, MEDIUM, LOW, INSUFFICIENT_DATA
    confidence_score: float = 0.95
    query_plan: Optional[List[Dict[str, Any]]] = None
    source_independence: Optional[Dict[str, Any]] = None
    visual_actions: Optional[HighlightAction] = None
    # Expandable full-detail blocks rendered inline in the chat. Each carries a
    # kind (stats, table, keyvalue, list, group) the UI knows how to draw.
    detail_sections: List[Dict[str, Any]] = []
    detail_stats: Optional[Dict[str, Any]] = None

# --- OSINT Schemas ---
class OSINTEvaluationRequest(BaseModel):
    case_id: str
    entity_id: str
    entity_name: str
    entity_type: str

class OSINTExtractedRecord(BaseModel):
    source_name: str
    source_url: str
    retrieval_timestamp: datetime
    reliability_score: float
    confidence: float
    extracted_claims: str
    is_potential_match: bool
    verification_warning: Optional[str] = None
    evidence_id: str

# --- Copilot Schemas ---
class CopilotQueryRequest(BaseModel):
    case_id: str
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[str] = None

class CopilotCitation(BaseModel):
    evidence_id: Optional[str] = None
    document_id: Optional[str] = None
    event_ids: List[str] = []
    source_title: str = ""
    supports: str = ""

class PlanStepOut(BaseModel):
    step: int
    tool: str
    arguments: Dict[str, Any] = {}
    record_count: int = 0
    outcome: str = ""

class CopilotResponse(BaseModel):
    answer: str
    confidence: str
    confidence_reason: str = ""
    requires_clarification: bool = False
    clarification_options: List[str] = []
    citations: List[CopilotCitation] = []
    contradictions: List[Dict[str, Any]] = []
    limitations: List[str] = []
    next_steps: List[str] = []
    entities: List[str] = []
    visual_actions: List[Dict[str, Any]] = []
    query_plan: List[PlanStepOut] = []
    planner: str = ""
    planner_note: str = ""
    grounding: Dict[str, Any] = {}

# --- Entity, relationship and event schemas ---
class EntityOut(BaseModel):
    entity_id: str
    case_id: str
    label: str
    entity_type: str
    aliases: List[str] = []
    properties: Dict[str, Any] = {}
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True

class HypothesisOut(BaseModel):
    hypothesis_id: str
    case_id: str
    title: str
    statement: str
    status: str
    created_by: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True

class HypothesisCreate(BaseModel):
    case_id: str
    title: str
    statement: str

class HypothesisStatusUpdate(BaseModel):
    status: str
    notes: Optional[str] = None

class LedgerBlockOut(BaseModel):
    block_number: int
    previous_hash: str
    block_hash: str
    payload: Dict[str, Any]
    sealed_by: str
    timestamp: datetime

    class Config:
        from_attributes = True
