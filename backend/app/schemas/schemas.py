from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class LoginRequest(BaseModel):
    username: str
    password: str

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
    visual_actions: Optional[HighlightAction] = None

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
