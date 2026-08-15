export type WorkflowId = "ingestion" | "query" | "evaluation";
export type JobState = "queued" | "running" | "retrying" | "succeeded" | "failed";
export type FlowStatus = "running" | "completed" | "skipped" | "failed";

export interface ConnectionConfig {
  apiBaseUrl: string;
  tenantId: string;
  adminKey: string;
  queryKey: string;
}

export interface FlowEvent {
  operation_id: string;
  stage: string;
  status: FlowStatus;
  message: string;
  duration_ms: number | null;
  data: Record<string, unknown>;
  recorded_at: string;
}

export interface IngestionResult {
  document_id: string;
  checksum: string;
  parents_indexed: number;
  chunks_indexed: number;
}

export interface IngestionAccepted {
  job_id: string;
  document_id: string;
  state: JobState;
}

export interface IngestionStatus {
  job_id: string;
  state: JobState;
  document_id: string;
  tenant_id: string;
  stage: string;
  message: string | null;
  result: IngestionResult | null;
  events: FlowEvent[];
  updated_at: string;
}

export interface Citation {
  source_id: string;
  document_id: string;
  title: string;
  section: string;
  source_name: string;
  relevance_score: number;
  document_checksum: string | null;
  chunk_id: string | null;
}

export interface QueryResponse {
  request_id: string;
  category: string;
  confidence: "high" | "medium" | "low";
  requires_human_review: boolean;
  routing_destination: string | null;
  answered: boolean;
  answer: string;
  escalation_reasons: string[];
  sensitive_data_types: string[];
  citations: Citation[];
}

export interface EvidencePreview {
  document_id: string;
  title: string;
  section: string;
  source_name: string;
  score: number;
  excerpt: string;
}

export type QueryStreamMessage =
  | { type: "stage"; event: FlowEvent }
  | { type: "result"; response: QueryResponse; evidence: EvidencePreview[] }
  | { type: "error"; status: number; detail: string };

export interface EvaluationAccepted {
  job_id: string;
  state: JobState;
}

export interface EvaluationStatus {
  job_id: string;
  state: JobState;
  tenant_id: string;
  stage: string;
  deep_eval: boolean;
  message: string | null;
  metrics: Record<string, unknown> | null;
  events: FlowEvent[];
  updated_at: string;
}

export interface BackendHealth {
  status: string;
  checks?: Record<string, string>;
}
