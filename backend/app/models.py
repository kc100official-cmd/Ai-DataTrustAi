from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


VerificationStatus = Literal[
    "Supported",
    "Partially supported",
    "Conflicting evidence",
    "Needs clarification",
    "Insufficient evidence",
]

RoutingStrategy = Literal[
    "sql_retrieval",
    "graph_retrieval",
    "semantic_retrieval",
    "hybrid_retrieval",
    "clarification_required",
    "insufficient_evidence",
]


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool
    is_primary_key: bool
    default_value: Optional[Any] = None
    null_count: int = 0
    distinct_count: int = 0
    sample_values: List[Any] = Field(default_factory=list)


class ForeignKeySchema(BaseModel):
    from_column: str
    to_table: str
    to_column: str


class TableSchema(BaseModel):
    table_name: str
    row_count: int
    duplicate_row_count: int = 0
    completeness_pct: float = 100.0
    columns: List[ColumnSchema]
    foreign_keys: List[ForeignKeySchema] = Field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)


class DatabaseSchemaResponse(BaseModel):
    source_id: str
    source_name: str
    description: str
    read_only_enforced: bool = True
    tables: List[TableSchema]
    relationships_summary: List[str] = Field(default_factory=list)
    quality_score: float = 100.0
    quality_notes: List[str] = Field(default_factory=list)


class SQLValidateRequest(BaseModel):
    source_id: str = "enterprise_supply_ops"
    sql: str


class SQLValidateResponse(BaseModel):
    is_valid: bool
    read_only_verified: bool
    statement_type: str
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    query_plan: List[str] = Field(default_factory=list)
    security_controls: List[str] = Field(default_factory=list)


class SQLExecuteRequest(BaseModel):
    source_id: str = "enterprise_supply_ops"
    sql: str
    question: Optional[str] = None
    allow_repair: bool = True


class SQLRepairAttempt(BaseModel):
    attempt_number: int
    original_sql: str
    error_message: str
    repaired_sql: str
    repair_reason: str
    succeeded: bool


class SQLResultValidation(BaseModel):
    is_valid: bool
    empty_output: bool = False
    has_missing_values: bool = False
    duplicate_row_count: int = 0
    suspicious_aggregates: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    checks_performed: List[str] = Field(default_factory=list)


class SQLExecuteResponse(BaseModel):
    source_id: str
    original_question: Optional[str] = None
    original_sql: str
    executed_sql: str
    execution_success: bool
    row_count: int = 0
    execution_time_ms: float = 0.0
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    validation: SQLResultValidation
    repair_attempts: List[SQLRepairAttempt] = Field(default_factory=list)
    error_message: Optional[str] = None
    chart_suggestion: Optional[Dict[str, Any]] = None


class ProvenanceRecord(BaseModel):
    source_id: str
    source_type: str  # "database_record", "document", "inferred_rule"
    source_record: str
    excerpt: str
    extraction_method: str
    confidence: float
    timestamp: str
    is_inferred: bool = False
    inference_rule: Optional[str] = None


class GraphNode(BaseModel):
    id: str
    name: str
    entity_type: str
    canonical_id: Optional[str] = None
    community_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceRecord
    is_merged_alias: bool = False
    aliases: List[str] = Field(default_factory=list)


class GraphEdge(BaseModel):
    id: str
    source: str
    source_name: str
    target: str
    target_name: str
    rel_type: str
    is_inferred: bool = False
    provenance: ProvenanceRecord


class EvidenceHop(BaseModel):
    step_index: int
    from_entity_id: str
    from_entity_name: str
    from_entity_type: str
    rel_type: str
    direction: str = "->"
    to_entity_id: str
    to_entity_name: str
    to_entity_type: str
    is_inferred: bool = False
    source_id: str
    source_type: str
    source_record: str
    excerpt: str
    extraction_method: str
    confidence: float


class EvidencePath(BaseModel):
    path_id: str
    summary_chain: str  # e.g. "School A -> LOCATED_IN -> Region North"
    hops: List[EvidenceHop]
    all_confirmed: bool
    has_inferred_hops: bool
    path_confidence: float
    supporting_explanation: str


class ClaimValidation(BaseModel):
    claim_id: str
    claim_text: str
    status: VerificationStatus
    is_direct_fact: bool
    supporting_sources: List[str] = Field(default_factory=list)
    evidence_excerpt: str
    conflict_note: Optional[str] = None
    missing_link_note: Optional[str] = None


class RoutingDecision(BaseModel):
    question: str
    selected_strategy: RoutingStrategy
    strategy_label: str
    selection_rationale: str
    sources_consulted: List[str]
    alternative_strategy: Optional[RoutingStrategy] = None
    alternative_rationale: Optional[str] = None
    evidence_coverage_score: float = Field(
        description="Measurable ratio of resolved query entities/clauses with direct supporting evidence (0.0 to 1.0)"
    )
    clarification_needed: bool = False
    clarification_options: List[str] = Field(default_factory=list)
    ambiguity_detected: Optional[str] = None
    classifier_mode: str = "deterministic_rules"
    retrieval_steps: List[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str
    source_id: str = "enterprise_supply_ops"
    community_id: Optional[str] = None
    preferred_strategy: Optional[RoutingStrategy] = None


class AskResponse(BaseModel):
    question: str
    source_id: str
    community_id: Optional[str] = None
    answer: str
    verification_status: VerificationStatus
    verification_rationale: str
    abstained: bool = False
    clarification_prompt: Optional[str] = None
    clarification_choices: List[str] = Field(default_factory=list)
    routing: RoutingDecision
    sql_result: Optional[SQLExecuteResponse] = None
    evidence_paths: List[EvidencePath] = Field(default_factory=list)
    semantic_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    claim_validations: List[ClaimValidation] = Field(default_factory=list)
    involved_entities: List[GraphNode] = Field(default_factory=list)
    missing_or_conflicting_notes: List[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    generation_mode: str = "deterministic_verified_synthesis"


class GraphIngestRequest(BaseModel):
    source_id: str = "enterprise_supply_ops"
    document_id: Optional[str] = None
    title: str
    doc_type: str = "audit_memo"
    text: str


class GraphBatchIngestRequest(BaseModel):
    documents: List[GraphIngestRequest] = Field(min_length=1, max_length=2000)


class GraphPathRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    max_depth: int = 4
    include_inferred: bool = True


class EntityResolveRequest(BaseModel):
    action: Literal["detect", "merge", "unmerge"] = "detect"
    duplicate_entity_id: Optional[str] = None
    canonical_entity_id: Optional[str] = None
    resolution_id: Optional[str] = None


class RetrievalSearchRequest(BaseModel):
    query: str
    source_id: Optional[str] = None
    top_k: int = 5


class RoutingInspectRequest(BaseModel):
    question: str
    source_id: str = "enterprise_supply_ops"
    community_id: Optional[str] = None


class EvaluationRunRequest(BaseModel):
    dataset_mode: Literal["bird_smoke_synthetic", "bird_external_path"] = "bird_smoke_synthetic"
    custom_dataset_path: Optional[str] = None
    model_name: str = "llama3.1:8b-instruct-q4_K_M"
    model_param_billions: float = 8.0
    max_questions: int = 10


class AddCompanyRequest(BaseModel):
    vendor_name: str
    city: str = "Gwalior"
    tier_level: int = 1
    compliance_score: float = 95.0
    primary_product: str = "Enterprise AI & Industrial Systems"
    contract_value_usd: float = 2500000.0
    facility_id: str = "FAC-GWL"
    contract_status: str = "ACTIVE"


class AddRelationshipRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    rel_type: str = "CONNECTED_TO"
    excerpt: str = "User-defined relationship added via Data Studio."
    is_inferred: bool = False

