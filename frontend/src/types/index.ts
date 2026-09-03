export interface Case {
  case_id: string;
  title: string;
  description?: string;
  status: string;
  classification: string;
  lead_investigator: string;
  assigned_team: string[];
  created_at: string;
  document_count?: number;
  evidence_count?: number;
}

export interface GraphNode {
  id: string;
  label: string;
  entity_type: string;
  properties: Record<string, any>;
  is_bridge?: boolean;
  is_hub?: boolean;
  centrality_score?: number;
  community_id?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  relationship_type: string;
  confidence?: number;
  evidence_ids?: string[];
  properties?: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    total_nodes: number;
    total_edges: number;
    hubs_count: number;
    bridges_count: number;
  };
}

export interface MapEvent {
  event_id: string;
  case_id: string;
  title: string;
  event_type: string;
  latitude: number;
  longitude: number;
  location_name: string;
  timestamp: string;
  related_entities: string[];
  evidence_id?: string;
  confidence: number;
}

export interface TimelineEvent {
  id: string;
  case_id: string;
  title: string;
  event_type: string;
  start_time: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  related_entities: string[];
  evidence_id?: string;
  summary: string;
  confidence: number;
}

export interface CustodyEvent {
  event_id: string;
  evidence_id: string;
  action: string;
  performed_by: string;
  ip_address: string;
  sha256_at_event: string;
  tamper_detected: boolean;
  details: Record<string, any>;
  created_at: string;
}

export interface EvidenceItem {
  evidence_id: string;
  case_id: string;
  document_id?: string;
  title: string;
  evidence_type: string;
  sha256_hash: string;
  integrity_status: string;
  blockchain_tx_id?: string;
  blockchain_block_num?: number;
  blockchain_timestamp?: string;
  metadata_payload: Record<string, any>;
  created_at: string;
  custody_events: CustodyEvent[];
}

export interface Citation {
  evidence_id: string;
  document_id?: string;
  source_title: string;
  reference_location: string;
  quote_or_claim: string;
  confidence: number;
}

export interface HighlightAction {
  target_type: string;
  node_ids: string[];
  event_ids: string[];
  coordinates: number[][];
  description: string;
}

export interface AIResponse {
  answer: string;
  is_ambiguous: boolean;
  clarification_options: string[];
  citations: Citation[];
  counter_evidence: {
    source: string;
    claim: string;
    discrepancy: string;
  }[];
  evidence_gaps: string[];
  suggested_next_steps: string[];
  confidence_level: string;
  confidence_score: number;
  visual_actions?: HighlightAction;
}

export interface OSINTRecord {
  source_name: string;
  source_url: string;
  retrieval_timestamp: string;
  reliability_score: number;
  confidence: number;
  extracted_claims: string;
  is_potential_match: boolean;
  verification_warning?: string;
  evidence_id: string;
}
