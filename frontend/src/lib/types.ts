export type WorkspaceTab = "intake" | "calendar" | "contracts" | "conflicts";
export type ContractStatus = "complete" | "failed";
export type DateProvenance = "explicit" | "derived";
export type LifecycleStatus = "active" | "upcoming" | "expired" | "undated" | "review" | "failed";
export type MetricIconName = "contracts" | "clauses" | "dates" | "confidence";

export interface ContractClause {
  id: string;
  category: string;
  text: string;
  confidence: number;
}

export interface ContractParty {
  text: string;
  raw_text?: string;
  normalized_name?: string;
  entity_type?: string;
  confidence: number;
  resolution_confidence?: number;
  party_id?: string | null;
  canonical_name?: string | null;
}

export interface ContractDate {
  date: string;
  event_desc: string;
  confidence: number;
  provenance: DateProvenance;
  evidence?: string | null;
  start_offset?: number | null;
  end_offset?: number | null;
}

export interface ContractText {
  content: string;
  confidence: number;
  character_count: number;
  sha256: string;
}

export interface ContractRecord {
  id: string;
  batch_id: string;
  source: string;
  relative_path: string;
  file_type: string;
  confidence: number;
  clauses: ContractClause[];
  parties: ContractParty[];
  dates: ContractDate[];
  status: ContractStatus;
  error: string | null;
  created_at: string | null;
  has_conflicts: boolean;
  text?: ContractText | null;
}

export interface ContractsResponse {
  contracts: ContractRecord[];
}

export interface UploadEntry {
  file: File;
  path: string;
}

export interface RejectedUpload {
  source: string;
  reason: string;
}

export interface UploadResponse {
  contracts: ContractRecord[];
  rejected: RejectedUpload[];
  conflict_analysis_error?: string;
}

export interface ConflictClause {
  id: string;
  contract_id: string;
  source: string;
  relative_path: string;
  text: string;
  confidence: number;
  categories: GroupedClauseCategory[];
}

export interface ContractConflict {
  id: string;
  confidence: number;
  model_confidence: number;
  scope: "within_contract" | "shared_party";
  shared_parties: string[];
  clauses: [ConflictClause, ConflictClause];
  created_at: string | null;
}

export interface ConflictsResponse {
  conflicts: ContractConflict[];
}

export interface SearchMatch {
  contract_id: string;
  source: string;
  relative_path: string;
  snippet: string;
  line_number: number;
  score: number;
  start_offset: number;
  end_offset: number;
}

export interface SearchResponse {
  query: string;
  matches: SearchMatch[];
}

export interface CalendarEvent {
  id: string;
  contractId?: string;
  date: string;
  summary: string;
  source: string;
  confidence: number;
  provenance: DateProvenance;
  evidence?: string;
  startOffset?: number;
  endOffset?: number;
}

export interface GroupedClauseCategory {
  name: string;
  confidence: number;
}

export interface GroupedClause {
  text: string;
  categories: GroupedClauseCategory[];
  clauseIds: string[];
}

export interface Lifecycle {
  status: LifecycleStatus;
  label: string;
  term: string;
}

export interface ToastState {
  message: string;
  error: boolean;
}
