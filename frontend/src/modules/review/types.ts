export type SaveState = "idle" | "saving" | "saved" | "error";
export type ReviewTab = "entities" | "relationships";
export type EntityListFilter = "pending" | "accepted";

export interface EntityDraft {
  name: string;
  entity_type: string;
  evidence_text: string;
  scope: "current" | "all";
}

export interface RelationDraft {
  start_entity_id: string;
  relation_type: string;
  end_entity_id: string;
  evidence_text: string;
}

export interface ReviewMeta {
  operation: "source" | "create" | "update" | "delete";
  deleted: boolean;
  added: boolean;
  modified: boolean;
  scope?: "current" | "all";
  version?: number;
}

export interface TaskInfo {
  document: {
    title: string;
    schema_version: string;
    total_chunks: number;
    total_pages?: number;
    pdf_available: boolean;
  };
  documents: Array<{
    document_id: string;
    title: string;
    chunk_count: number;
    pdf_available: boolean;
  }>;
  progress: {
    approved: number;
    total: number;
    percent: number;
    issues: number;
    modified: number;
  };
  input_hash: string;
  version: number;
}

export interface ChunkSummary {
  chunk_id: string;
  index: number;
  section_title: string;
  page_start?: number;
  page_end?: number;
  text_preview: string;
  entity_count: number;
  relation_count: number;
  issue_count: number;
  status: "pending" | "approved" | "modified";
  approved: boolean;
  has_changes: boolean;
  _source_title?: string;
  _doc_id?: string;
}

export interface ChunkRecord {
  chunk_id: string;
  section_title?: string;
  section_path?: string[];
  page_start?: number;
  page_end?: number;
  text: string;
  /** Multi-document source tracking */
  _source_title?: string;
  _doc_id?: string;
}

export interface EntityType {
  value: string;
  label: string;
  contract_label: string;
}

export interface RelationType {
  value: string;
  label: string;
  source_type: string;
  target_type: string;
}

export interface EntityRecord {
  entity_id: string;
  chunk_id: string;
  name: string;
  entity_type: string;
  evidence_text?: string;
  status?: string;
  confidence?: number;
  review_canonical_id?: string;
  canonical_entity_id?: string;
  evidence_spans?: Array<{ start?: number; end?: number; text?: string }>;
  /** output.json / entity_nodes format: single evidence span object */
  evidence_span?: { evidence_id?: string; start?: number; end?: number; raw_text?: string; normalized_text?: string };
  entity_status?: string;
  source_title?: string;
  document_core_disease?: string;
  metadata?: Record<string, unknown>;
  _review: ReviewMeta;
}

export interface Conflict {
  code: string;
  message: string;
}

export interface RelationshipRecord {
  relation_id: string;
  chunk_id?: string;
  source_chunk_id?: string;
  target_chunk_id?: string;
  start_entity_id: string;
  end_entity_id: string;
  relation_type: string;
  evidence_text?: string;
  status?: string;
  confidence?: number;
  conflicts: Conflict[];
  source_title?: string;
  _review: ReviewMeta;
}

export interface EntityOption {
  id: string;
  name: string;
  entity_type: string;
  canonical: string;
}

export interface ChunkDetail {
  chunk: ChunkRecord;
  entities: EntityRecord[];
  relationships: RelationshipRecord[];
  entity_options: EntityOption[];
  entity_types: EntityType[];
  relation_types: RelationType[];
  review: {
    status: "pending" | "approved";
    has_changes: boolean;
    issue_count: number;
  };
  version: number;
}
