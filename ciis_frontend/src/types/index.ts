/**
 * Domain types for the CIIS platform.
 *
 * Phase-2 artifact types mirror the engine's pydantic models exactly
 * (backend/modules/investigation/<module>/models.py). The frontend NEVER
 * computes forensic values - these types describe engine output verbatim.
 */

// ---------------------------------------------------------------- auth
export type Role = "administrator" | "investigator" | "analyst" | "viewer";

export interface UserPreference {
  theme: "dark" | "light";
  language: string;
  notifications_enabled: boolean;
  items_per_page: number;
}

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  badge_number: string;
  department: string;
  is_active: boolean;
  permissions: string[];
  preference: UserPreference | null;
  date_joined: string;
  last_login: string | null;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

// ---------------------------------------------------------------- shared
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
  unread_count?: number;
}

/** Envelope every stored Phase-2 artifact is wrapped in. */
export interface ArtifactDocument<T> {
  report_type: string;
  report_version: number;
  schema_version: string;
  case_id: string;
  generated_at: string;
  report: T;
}

// ---------------------------------------------------------------- cases
export type CaseStatus = "open" | "active" | "completed" | "archived";

export interface CaseSummary {
  case_id: string;
  created_at: string;
  title: string;
  description: string;
  investigator_notes: string;
  evidence_count: number;
  status: CaseStatus;
  assigned_to: string | null;
  tags: string[];
  priority: CasePriority | null;
  priority_override: string;
  updated_at: string;
}

export interface CaseDetail extends CaseSummary {
  evidence: EvidenceRow[];
}

export interface CaseHistoryEntry {
  id: number;
  case_id: string;
  username: string;
  action: string;
  detail: string;
  created_at: string;
}

// ------------------------------------------------------------- evidence
export interface EvidenceRow {
  evidence_id: string;
  case_id: string;
  original_file_name: string;
  stored_file_name: string;
  file_extension: string;
  file_size_bytes: string;
  sha256_before: string;
  sha256_after: string;
  hash_verified: string;
  upload_time: string;
  processing_time: string;
  status: "uploaded" | "processed" | "failed";
  investigator_notes: string;
}

export interface OcrLine {
  text: string;
  confidence: number;
  bbox: number[][];
}

export interface OcrPage {
  page: number;
  confidence: number;
  text: string;
  lines: OcrLine[];
}

export interface EvidenceOcr {
  case_id: string;
  evidence_id: string;
  file_name: string;
  file_hash: string;
  file_size: string;
  upload_time: string;
  processing_time_ms: number;
  pages: OcrPage[];
  [key: string]: unknown;
}

export interface EvidenceDetail {
  record: EvidenceRow;
  ocr: EvidenceOcr | null;
  forensics: Record<string, unknown>;
}

export interface BackgroundJob {
  id: number;
  job_type: "evidence_processing" | "case_analysis";
  status: "queued" | "running" | "completed" | "failed";
  case_id: string;
  evidence_id: string;
  detail: string;
  error: string;
  created_by: string;
  created_at: string;
  finished_at: string | null;
}

// -------------------------------------------------- Phase-2: correlation
export interface CorrelationFactor {
  factor: string;
  weight: number;
  matches: number;
  contribution: number;
  supporting_evidence: string[];
  reason: string;
}

export interface EvidencePairCorrelation {
  evidence_a: string;
  evidence_b: string;
  correlation_weight: number;
  correlation_confidence: number;
  relationship_strength: string;
  factors: CorrelationFactor[];
  correlation_reasons: string[];
  explanation: string;
}

export interface CorrelationAnalysis {
  case_id: string;
  evidence_ids: string[];
  pair_count: number;
  related_pair_count: number;
  pairs: EvidencePairCorrelation[];
  strength_distribution: Record<string, number>;
  strongest_pair: string;
  analysis_time_ms: number;
}

// -------------------------------------------------------- Phase-2: graph
export interface GraphNode {
  id: string;
  node_type: string;
  label: string;
  properties: Record<string, string>;
}

export interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
  weight: number;
  explanation: string;
}

export interface RelationshipGraph {
  case_id: string;
  directed: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphStatistics {
  case_id: string;
  node_count: number;
  edge_count: number;
  nodes_by_type: Record<string, number>;
  edges_by_type: Record<string, number>;
  density: number;
  connected_components: number;
  largest_component_size: number;
  average_degree: number;
  top_hubs: Record<string, string>[];
}

export interface GraphSummary {
  case_id: string;
  headline: string;
  key_connectors: string[];
  observations: string[];
}

// ---------------------------------------------------- Phase-2: campaigns
export interface CampaignMembership {
  evidence_id: string;
  linked_via: string[];
  link_reasons: string[];
  membership_explanation: string;
}

export interface Campaign {
  campaign_id: string;
  case_id: string;
  members: string[];
  memberships: CampaignMembership[];
  campaign_confidence: number;
  signature: string[];
  shared_brands: string[];
  shared_domains: string[];
  timeline_start: string;
  timeline_end: string;
  statistics: Record<string, number>;
  summary: string;
}

export interface CampaignAnalysis {
  case_id: string;
  campaign_count: number;
  campaigns: Campaign[];
  unclustered_evidence: string[];
  analysis_time_ms: number;
}

// ----------------------------------------------------- Phase-2: suspects
export interface SuspectScoreComponent {
  name: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface SuspectProfile {
  suspect_id: string;
  identity_type: string;
  identity_value: string;
  aliases: string[];
  evidence_ids: string[];
  evidence_count: number;
  components: SuspectScoreComponent[];
  confidence_score: number;
  confidence_level: string;
  relationship_strength: string;
  risk_level: string;
  threat_flagged: boolean;
  first_seen: string;
  last_seen: string;
  explanation: string;
}

export interface SuspectAssessment {
  case_id: string;
  suspect_count: number;
  suspects: SuspectProfile[];
  top_suspect: string;
  analysis_time_ms: number;
  methodology: string;
}

// ----------------------------------------------------- Phase-2: timeline
export interface TimelineEvent {
  timestamp: string;
  event_type: string;
  evidence_id: string;
  description: string;
  stages: string[];
  critical: boolean;
  critical_reasons: string[];
}

export interface AttackStage {
  stage: string;
  evidence_ids: string[];
  first_seen: string;
  last_seen: string;
  matched_keywords: string[];
  explanation: string;
}

export interface TimelineAnalysis {
  case_id: string;
  events: TimelineEvent[];
  attack_stages: AttackStage[];
  stage_progression: string[];
  progression_consistent: boolean;
  milestones: TimelineEvent[];
  critical_events: TimelineEvent[];
  summary: string;
  statistics: Record<string, number>;
  analysis_time_ms: number;
}

// ---------------------------------------------------- Phase-2: analytics
export interface ValueCount {
  value: string;
  count: number;
}

export interface CaseAnalytics {
  case_id: string;
  evidence_count: number;
  entity_statistics: Record<string, number>;
  top_entities: Record<string, ValueCount[]>;
  threat_statistics: Record<string, number>;
  brand_statistics: ValueCount[];
  wallet_statistics: ValueCount[];
  url_statistics: ValueCount[];
  device_statistics: ValueCount[];
  metadata_statistics: Record<string, number>;
  campaign_statistics: Record<string, number>;
  timeline_statistics: Record<string, number>;
  evidence_quality_statistics: Record<string, number>;
  correlation_statistics: Record<string, number>;
  analysis_time_ms: number;
}

// ----------------------------------------------------- Phase-2: priority
export interface PriorityComponent {
  name: string;
  score: number;
  weight: number;
  available: boolean;
  explanation: string;
}

export interface CasePriority {
  case_id: string;
  components: PriorityComponent[];
  priority_score: number;
  priority_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  high_risk_indicators: string[];
  investigation_recommendation: string;
  explanation: string;
  computed_at: string;
}

// ------------------------------------------------------------- reports
export interface ReportFile {
  file_name: string;
  format: "json" | "markdown";
  size_bytes: number;
  generated_at: string | null;
  modified_at: number;
}

// --------------------------------------------------------------- audit
export interface AuditEntry {
  source: "evidence_pipeline" | "investigation" | "platform";
  timestamp: string;
  case_id: string;
  evidence_id: string;
  module: string;
  action: string;
  level: string;
  detail: string;
  username: string;
}

// -------------------------------------------------------- notifications
export type NotificationType =
  | "processing_complete"
  | "high_priority"
  | "forgery_warning"
  | "threat_detected"
  | "report_generated"
  | "system_error";

export interface AppNotification {
  id: number;
  type: NotificationType;
  title: string;
  message: string;
  case_id: string;
  evidence_id: string;
  read: boolean;
  created_at: string;
}

// ------------------------------------------------------------ dashboard
export interface DashboardData {
  totals: {
    cases: number;
    active_cases: number;
    completed_cases: number;
    archived_cases: number;
    evidence: number;
    high_priority_cases: number;
    campaigns: number;
    unread_notifications: number;
  };
  priority_distribution: Record<string, number>;
  threat_distribution: Record<string, number>;
  high_priority_cases: { case_id: string; band: string; score: number | null }[];
  processing: BackgroundJob[];
  recent_activity: {
    id: number;
    username: string;
    module: string;
    action: string;
    case_id: string;
    detail: string;
    created_at: string;
  }[];
  engine_health: Record<string, unknown>;
}

// -------------------------------------------------------------- settings
export interface SystemSettings {
  ocr: Record<string, unknown>;
  preprocessing: Record<string, unknown>;
  storage: Record<string, unknown>;
  supported_extensions: string[];
  investigation: Record<string, unknown>;
  health: Record<string, unknown>;
}

export interface ArtifactAvailability {
  case_id: string;
  artifacts: Record<string, boolean>;
}
