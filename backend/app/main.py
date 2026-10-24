import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .bird_evaluator import list_evaluation_runs, run_bird_evaluation
from .community_engine import detect_graph_communities, get_community_by_id
from .config import settings
from .database import discover_schema, get_query_history, list_data_sources
from .graph_engine import (
    detect_and_manage_entity_resolution,
    find_bounded_paths,
    get_entity_details,
    get_entity_neighbors,
    get_full_graph,
    ingest_document_to_graph,
)
from .models import (
    AddCompanyRequest,
    AddRelationshipRequest,
    AskRequest,
    AskResponse,
    EntityResolveRequest,
    EvaluationRunRequest,
    GraphIngestRequest,
    GraphPathRequest,
    RetrievalSearchRequest,
    RoutingInspectRequest,
    SQLExecuteRequest,
    SQLValidateRequest,
)
from .retrieval_engine import search_documents_and_excerpts
from .router_engine import inspect_and_route_question
from .sample_data import (
    add_custom_company_record,
    add_custom_graph_relationship,
    ensure_sample_databases,
)
from .sql_engine import execute_sql_with_repair, validate_sql_query
from .validation_engine import answer_and_validate_question

logger = logging.getLogger("datatrust_ai")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_sample_databases()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.TAGLINE,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    ensure_sample_databases()
    sources = list_data_sources()
    graph = get_full_graph()
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "tagline": settings.TAGLINE,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_engine": "SQLite Read-Only (URI mode=ro + PRAGMA query_only + C Authorizer)",
        "connected_sources_count": len(sources),
        "graph_nodes_count": graph["total_nodes"],
        "graph_confirmed_edges_count": graph["confirmed_edge_count"],
        "graph_inferred_edges_count": graph["inferred_edge_count"],
        "llm_configured": settings.LLM_ENABLED,
        "llm_model": settings.LLM_MODEL,
        "llm_param_billions": settings.LLM_PARAM_BILLIONS,
        "fallback_mode": "active_deterministic_compiler" if not settings.LLM_ENABLED else "llm_with_deterministic_fallback",
        "embeddings_mode": "dense_embeddings" if settings.EMBEDDINGS_ENABLED else "tfidf_lexical_fallback",
    }


@app.get("/api/sources")
def get_sources():
    return {"sources": list_data_sources()}


@app.get("/api/schema")
def get_schema(source_id: str = Query("enterprise_supply_ops")):
    try:
        return discover_schema(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to introspect database schema.")


@app.get("/api/sql/history")
def get_sql_history_endpoint(
    source_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    return {"history": get_query_history(source_id=source_id, limit=limit)}


@app.post("/api/sql/validate")
def validate_sql_endpoint(req: SQLValidateRequest):
    try:
        return validate_sql_query(req.source_id, req.sql)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/sql/execute")
def execute_sql_endpoint(req: SQLExecuteRequest):
    try:
        return execute_sql_with_repair(
            source_id=req.source_id,
            sql=req.sql,
            question=req.question,
            allow_repair=req.allow_repair,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/ask", response_model=AskResponse)
def ask_question_endpoint(req: AskRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        return answer_and_validate_question(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/graph")
def get_graph_overview(
    source_id: Optional[str] = Query(None),
    rel_type: Optional[str] = Query(None),
    include_inferred: bool = Query(True),
    include_merged_aliases: bool = Query(False),
    search: Optional[str] = Query(None),
):
    return get_full_graph(
        source_id=source_id,
        rel_type=rel_type,
        include_inferred=include_inferred,
        include_merged_aliases=include_merged_aliases,
        search_query=search,
    )


@app.post("/api/graph/ingest")
def ingest_graph_document(req: GraphIngestRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=422, detail="Document text cannot be empty.")
    try:
        return ingest_document_to_graph(
            source_id=req.source_id,
            title=req.title,
            doc_type=req.doc_type,
            text=req.text,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Ingestion error: {str(exc)}")


@app.get("/api/graph/entity/{entity_id}")
def get_graph_entity(entity_id: str):
    detail = get_entity_details(entity_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found.")
    return detail


@app.get("/api/graph/neighbors/{entity_id}")
def get_graph_neighbors(
    entity_id: str,
    rel_type: Optional[str] = Query(None),
    depth: int = Query(1, ge=1, le=5),
    include_inferred: bool = Query(True),
):
    try:
        return get_entity_neighbors(
            entity_id=entity_id,
            rel_type=rel_type,
            depth=depth,
            include_inferred=include_inferred,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/graph/path")
def find_graph_paths_endpoint(req: GraphPathRequest):
    paths = find_bounded_paths(
        source_entity_id=req.source_entity_id,
        target_entity_id=req.target_entity_id,
        max_depth=req.max_depth,
        include_inferred=req.include_inferred,
    )
    return {
        "source_entity_id": req.source_entity_id,
        "target_entity_id": req.target_entity_id,
        "path_found": len(paths) > 0,
        "paths": [p.model_dump() for p in paths],
    }


@app.get("/api/graph/communities")
def get_communities_endpoint(source_id: Optional[str] = Query(None)):
    comms = detect_graph_communities(source_id=source_id)
    return {
        "total_communities": len(comms),
        "communities": comms,
    }


@app.get("/api/graph/community/{community_id}")
def get_community_detail_endpoint(
    community_id: str,
    source_id: Optional[str] = Query(None),
):
    comm = get_community_by_id(community_id=community_id, source_id=source_id)
    if not comm:
        raise HTTPException(status_code=404, detail=f"Community '{community_id}' not found.")
    return comm


@app.post("/api/entities/resolve")
def resolve_entities_endpoint(req: EntityResolveRequest):
    try:
        return detect_and_manage_entity_resolution(
            action=req.action,
            duplicate_entity_id=req.duplicate_entity_id,
            canonical_entity_id=req.canonical_entity_id,
            resolution_id=req.resolution_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/retrieval/search")
def retrieval_search_endpoint(req: RetrievalSearchRequest):
    return search_documents_and_excerpts(
        query=req.query,
        source_id=req.source_id,
        top_k=req.top_k,
    )


@app.post("/api/routing/inspect")
def routing_inspect_endpoint(req: RoutingInspectRequest):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        return inspect_and_route_question(
            question=req.question,
            source_id=req.source_id,
            community_id=req.community_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/evaluations")
def get_evaluations_endpoint():
    return list_evaluation_runs()


@app.post("/api/evaluations/run")
def run_evaluation_endpoint(req: EvaluationRunRequest):
    try:
        return run_bird_evaluation(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/data/company")
def add_company_endpoint(req: AddCompanyRequest):
    if not req.vendor_name or not req.vendor_name.strip():
        raise HTTPException(status_code=422, detail="Company name must not be empty.")
    try:
        return add_custom_company_record(
            company_name=req.vendor_name.strip(),
            city=req.city.strip(),
            tier_level=req.tier_level,
            compliance_score=req.compliance_score,
            primary_product=req.primary_product.strip(),
            contract_value_usd=req.contract_value_usd,
            facility_id=req.facility_id,
            contract_status=req.contract_status,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to add company: {str(exc)}")


@app.post("/api/data/relationship")
def add_relationship_endpoint(req: AddRelationshipRequest):
    try:
        return add_custom_graph_relationship(
            source_entity_id=req.source_entity_id,
            target_entity_id=req.target_entity_id,
            rel_type=req.rel_type,
            excerpt=req.excerpt,
            is_inferred=req.is_inferred,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to add relationship: {str(exc)}")


@app.post("/api/data/reset")
def reset_data_endpoint():
    ensure_sample_databases(force_reset=True)
    return {
        "status": "reset_complete",
        "message": "Indian Corporate & Regional Supply Network databases and Knowledge Graph re-initialized.",
    }

