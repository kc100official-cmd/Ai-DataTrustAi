const API_BASE = import.meta.env.VITE_API_BASE || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
    ...options,
  });
  if (!res.ok) {
    let errDetail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      errDetail = errJson.detail || JSON.stringify(errJson);
    } catch {
      errDetail = await res.text();
    }
    throw new Error(errDetail);
  }
  return res.json();
}

export interface HealthStatus {
  status: string;
  project: string;
  tagline: string;
  version: string;
  timestamp: string;
  database_engine: string;
  connected_sources_count: number;
  graph_nodes_count: number;
  graph_confirmed_edges_count: number;
  graph_inferred_edges_count: number;
  llm_configured: boolean;
  llm_model: string;
  llm_param_billions: number;
  fallback_mode: string;
  embeddings_mode: string;
}

export interface DataSourceInfo {
  source_id: string;
  source_name: string;
  filename: string;
  description: string;
  domain: string;
  table_count: number;
  tables: string[];
  total_rows: number;
  status: string;
}

export interface EvidenceHop {
  step_index: number;
  from_entity_id: string;
  from_entity_name: string;
  from_entity_type: string;
  rel_type: string;
  direction: string;
  to_entity_id: string;
  to_entity_name: string;
  to_entity_type: string;
  is_inferred: boolean;
  source_id: string;
  source_type: string;
  source_record: string;
  excerpt: string;
  extraction_method: string;
  confidence: number;
}

export interface EvidencePath {
  path_id: string;
  summary_chain: string;
  hops: EvidenceHop[];
  all_confirmed: boolean;
  has_inferred_hops: boolean;
  path_confidence: number;
  supporting_explanation: string;
}

export interface ClaimValidation {
  claim_id: string;
  claim_text: string;
  status: 'Supported' | 'Partially supported' | 'Conflicting evidence' | 'Needs clarification' | 'Insufficient evidence';
  is_direct_fact: boolean;
  supporting_sources: string[];
  evidence_excerpt: string;
  conflict_note?: string;
  missing_link_note?: string;
}

export interface RoutingDecision {
  question: string;
  selected_strategy: string;
  strategy_label: string;
  selection_rationale: string;
  sources_consulted: string[];
  alternative_strategy?: string;
  alternative_rationale?: string;
  evidence_coverage_score: number;
  clarification_needed: boolean;
  clarification_options: string[];
  ambiguity_detected?: string;
  classifier_mode: string;
  retrieval_steps: string[];
}

export interface SQLExecuteResponse {
  source_id: string;
  original_question?: string;
  original_sql: string;
  executed_sql: string;
  execution_success: boolean;
  row_count: number;
  execution_time_ms: number;
  columns: string[];
  rows: Record<string, any>[];
  validation: {
    is_valid: boolean;
    empty_output: boolean;
    has_missing_values: boolean;
    duplicate_row_count: number;
    suspicious_aggregates: string[];
    assumptions: string[];
    limitations: string[];
    checks_performed: string[];
  };
  repair_attempts: {
    attempt_number: number;
    original_sql: string;
    error_message: string;
    repaired_sql: string;
    repair_reason: string;
    succeeded: boolean;
  }[];
  error_message?: string;
  chart_suggestion?: {
    type: string;
    x_key: string;
    y_keys: string[];
    title: string;
  };
}

export interface AskResponse {
  question: string;
  source_id: string;
  community_id?: string;
  answer: string;
  verification_status: 'Supported' | 'Partially supported' | 'Conflicting evidence' | 'Needs clarification' | 'Insufficient evidence';
  verification_rationale: string;
  abstained: boolean;
  clarification_prompt?: string;
  clarification_choices: string[];
  routing: RoutingDecision;
  sql_result?: SQLExecuteResponse;
  evidence_paths: EvidencePath[];
  semantic_evidence: Record<string, any>[];
  claim_validations: ClaimValidation[];
  involved_entities: any[];
  missing_or_conflicting_notes: string[];
  execution_time_ms: number;
  generation_mode: string;
}

export const api = {
  getHealth: () => request<HealthStatus>('/api/health'),
  getSources: () => request<{ sources: DataSourceInfo[] }>('/api/sources'),
  getSchema: (sourceId: string) => request<any>(`/api/schema?source_id=${encodeURIComponent(sourceId)}`),
  getSqlHistory: (sourceId?: string) =>
    request<{ history: any[] }>(`/api/sql/history${sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : ''}`),
  validateSql: (source_id: string, sql: string) =>
    request<any>('/api/sql/validate', { method: 'POST', body: JSON.stringify({ source_id, sql }) }),
  executeSql: (source_id: string, sql: string, question?: string, allow_repair = true) =>
    request<SQLExecuteResponse>('/api/sql/execute', {
      method: 'POST',
      body: JSON.stringify({ source_id, sql, question, allow_repair }),
    }),
  ask: (question: string, source_id: string, community_id?: string, preferred_strategy?: string) =>
    request<AskResponse>('/api/ask', {
      method: 'POST',
      body: JSON.stringify({ question, source_id, community_id, preferred_strategy }),
    }),
  getGraph: (params: {
    source_id?: string;
    rel_type?: string;
    include_inferred?: boolean;
    include_merged_aliases?: boolean;
    search?: string;
  }) => {
    const q = new URLSearchParams();
    if (params.source_id) q.set('source_id', params.source_id);
    if (params.rel_type) q.set('rel_type', params.rel_type);
    if (params.include_inferred !== undefined) q.set('include_inferred', String(params.include_inferred));
    if (params.include_merged_aliases !== undefined) q.set('include_merged_aliases', String(params.include_merged_aliases));
    if (params.search) q.set('search', params.search);
    return request<any>(`/api/graph?${q.toString()}`);
  },
  getEntityDetail: (entityId: string) => request<any>(`/api/graph/entity/${encodeURIComponent(entityId)}`),
  getNeighbors: (entityId: string, depth = 1, includeInferred = true) =>
    request<any>(`/api/graph/neighbors/${encodeURIComponent(entityId)}?depth=${depth}&include_inferred=${includeInferred}`),
  findPaths: (source_entity_id: string, target_entity_id: string, max_depth = 4, include_inferred = true) =>
    request<{ path_found: boolean; paths: EvidencePath[] }>('/api/graph/path', {
      method: 'POST',
      body: JSON.stringify({ source_entity_id, target_entity_id, max_depth, include_inferred }),
    }),
  ingestDocument: (source_id: string, title: string, doc_type: string, text: string) =>
    request<any>('/api/graph/ingest', {
      method: 'POST',
      body: JSON.stringify({ source_id, title, doc_type, text }),
    }),
  getCommunities: (sourceId?: string) =>
    request<{ total_communities: number; communities: any[] }>(
      `/api/graph/communities${sourceId ? `?source_id=${encodeURIComponent(sourceId)}` : ''}`
    ),
  getCommunityDetail: (communityId: string) =>
    request<any>(`/api/graph/community/${encodeURIComponent(communityId)}`),
  resolveEntities: (payload: {
    action: 'detect' | 'merge' | 'unmerge';
    resolution_id?: string;
    duplicate_entity_id?: string;
    canonical_entity_id?: string;
  }) =>
    request<any>('/api/entities/resolve', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  inspectRouting: (question: string, source_id: string, community_id?: string) =>
    request<RoutingDecision>('/api/routing/inspect', {
      method: 'POST',
      body: JSON.stringify({ question, source_id, community_id }),
    }),
  searchRetrieval: (query: string, source_id?: string, top_k = 5) =>
    request<any>('/api/retrieval/search', {
      method: 'POST',
      body: JSON.stringify({ query, source_id, top_k }),
    }),
  getEvaluations: () => request<any>('/api/evaluations'),
  runEvaluation: (payload: {
    dataset_mode: 'bird_smoke_synthetic' | 'bird_external_path';
    custom_dataset_path?: string;
    model_name: string;
    model_param_billions: number;
    max_questions: number;
  }) =>
    request<any>('/api/evaluations/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  addCompany: (payload: {
    vendor_name: string;
    city: string;
    tier_level: number;
    compliance_score: number;
    primary_product: string;
    contract_value_usd: number;
    facility_id: string;
    contract_status: string;
  }) =>
    request<any>('/api/data/company', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  addRelationship: (payload: {
    source_entity_id: string;
    target_entity_id: string;
    rel_type: string;
    excerpt: string;
    is_inferred: boolean;
  }) =>
    request<any>('/api/data/relationship', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  resetData: () =>
    request<any>('/api/data/reset', {
      method: 'POST',
    }),
};
