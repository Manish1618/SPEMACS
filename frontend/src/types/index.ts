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

export interface PlanStep {
  step: number;
  action: string;
  description: string;
  status: string;
}

export interface SourceIndependence {
  reported_sources_count: number;
  independent_sources_count: number;
  derivative_sources_count: number;
  primary_origin: string;
}

export interface CrossCaseEvidenceRef {
  evidence_id: string;
  title: string;
  case_id: string | null;
  evidence_type?: string;
  integrity_status: string;
  sha256_hash?: string;
  readable: boolean;
}

export interface CrossCasePathStep {
  from: string;
  from_label: string;
  rel_type: string;
  rel_id: string;
  to: string;
  to_label: string;
  assertion_kind?: string;
  evidence_ids?: string[];
}

export interface CrossCaseViewSync {
  node_ids: string[];
  event_ids: string[];
  coordinates: number[][];
  timeline_from: string | null;
  timeline_to: string | null;
}

/**
 * One detected relationship between the active case and another investigation.
 * `confidence` is how sure the engine is that the link exists in the records -
 * never a measure of suspicion. `interpretation` carries that in words.
 */
export interface CrossCaseLink {
  link_id: string;
  basis: string;
  basis_label: string;
  summary: string;
  explanation: string[];
  case_a: { case_id: string; title: string };
  case_b: { case_id: string; title: string };
  entities: {
    entity_id: string;
    label: string;
    entity_type: string;
    registered_case_id: string | null;
    appears_in_cases: string[];
  }[];
  hops: number;
  path: CrossCasePathStep[];
  supporting_evidence: CrossCaseEvidenceRef[];
  contradicting_evidence: { source: string; claim: string; discrepancy: string }[];
  confidence: number;
  confidence_band: 'HIGH' | 'MODERATE' | 'LOW';
  confidence_meaning: string;
  uncertainty: string[];
  requires_human_verification: boolean;
  interpretation: string;
  view_sync: CrossCaseViewSync;
}

export interface CrossCaseReport {
  case_id: string;
  case_title?: string;
  authorised: boolean;
  generated_at?: string;
  links: CrossCaseLink[];
  related_cases: {
    case_id: string;
    title: string;
    status: string;
    link_count: number;
    strongest_confidence: number;
    strongest_basis: string;
    bases: string[];
  }[];
  summary?: {
    link_count: number;
    related_case_count: number;
    by_basis: Record<string, number>;
    by_band: Record<string, number>;
    needs_verification: number;
  };
  authorisation: {
    username: string;
    role: string;
    cases_in_scope: string[];
    cases_out_of_scope: number;
    note: string;
  } | string;
  caveat: string;
  confidence_meaning?: string;
}

export interface DetailStat {
  label: string;
  value: string | number;
  tone?: 'good' | 'bad';
}

/**
 * One expandable block of the full record set. The backend picks the kind and
 * fills only the fields that kind uses, so the chat can render any section it is
 * handed without knowing what the section is about.
 */
export interface DetailSection {
  section_id: string;
  title: string;
  kind: 'stats' | 'keyvalue' | 'table' | 'list' | 'group';
  summary?: string;
  stats?: DetailStat[];
  pairs?: [string, string][];
  columns?: string[];
  rows?: string[][];
  total_rows?: number;
  items?: string[];
  children?: DetailSection[];
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
  query_plan?: PlanStep[];
  source_independence?: SourceIndependence;
  visual_actions?: HighlightAction;
  detail_sections?: DetailSection[];
  detail_stats?: Record<string, number> | null;
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

// --- Authentication ---
export type UserRole =
  | 'ADMIN'
  | 'CRIME_BRANCH_HEAD'
  | 'LEAD_INVESTIGATOR'
  | 'INVESTIGATOR'
  | 'ANALYST'
  | 'AUDITOR';

export const USER_ROLES: UserRole[] = [
  'ADMIN',
  'CRIME_BRANCH_HEAD',
  'LEAD_INVESTIGATOR',
  'INVESTIGATOR',
  'ANALYST',
  'AUDITOR',
];

/** The signed-in caller, as returned by /auth/login, /auth/refresh and /auth/me. */
export interface AuthUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  badge_number?: string | null;
  accessible_cases: string[];
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: AuthUser;
}

export interface AuthConfig {
  demo_mode: boolean;
  demo_credentials: { username: string; password: string; role: string }[];
  min_password_length: number;
  access_token_expire_minutes: number;
}

/** A row in the administrator's user table. */
export interface ManagedUser {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  badge_number?: string | null;
  /** E.164, e.g. +919876543210. The number access alerts are texted to. */
  phone_number?: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at?: string | null;
  is_locked: boolean;
  accessible_cases: string[];
}

/** One row of the access record shown to administrators and the Crime Branch head. */
export interface AccessLogEntry {
  id: string;
  username: string;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  case_id?: string | null;
  ip_address?: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

/** What the platform tried to send about an access event, and whether it landed. */
export interface NotificationLogEntry {
  id: string;
  event_type: string;
  severity: 'INFO' | 'HIGH';
  channel: 'EMAIL' | 'SMS';
  recipient: string;
  recipient_username?: string | null;
  subject?: string | null;
  status: 'SENT' | 'FAILED' | 'SKIPPED';
  error?: string | null;
  provider?: string | null;
  actor_username?: string | null;
  created_at: string;
}

export interface AlertConfig {
  alerts_enabled: boolean;
  recipients: {
    username: string;
    full_name: string;
    email: string;
    phone_number?: string | null;
    sms_reachable: boolean;
  }[];
  fallback_email?: string | null;
  fallback_phone?: string | null;
  email: { configured: boolean; host?: string | null; port: number; from: string; events: string };
  sms: { provider: string; configured: boolean; from?: string | null; events: string };
  privileged_roles: string;
}
