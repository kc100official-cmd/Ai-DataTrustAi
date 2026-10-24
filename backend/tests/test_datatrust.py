import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_and_sources():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["project"] == "DataTrust AI"
    assert data["connected_sources_count"] >= 2
    assert data["graph_nodes_count"] > 10

    src_resp = client.get("/api/sources")
    assert src_resp.status_code == 200
    sources = src_resp.json()["sources"]
    source_ids = {s["source_id"] for s in sources}
    assert "enterprise_supply_ops" in source_ids
    assert "california_schools_bird_demo" in source_ids


def test_schema_discovery_and_quality_notes():
    resp = client.get("/api/schema?source_id=enterprise_supply_ops")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["read_only_enforced"] is True
    table_names = {t["table_name"] for t in schema["tables"]}
    assert {"regions", "facilities", "vendors", "procurement_contracts", "shipments", "quality_incidents"}.issubset(table_names)
    assert len(schema["relationships_summary"]) >= 5
    # Verify missing value detection (e.g. facilities headcount NULL or vendors contact_email/compliance_score NULL)
    assert any("missing (NULL)" in note for note in schema["quality_notes"])

    # Invalid source_id should return 404
    bad_resp = client.get("/api/schema?source_id=nonexistent_db")
    assert bad_resp.status_code == 404


def test_sql_validation_and_rejection_of_unsafe_operations():
    # 1. Valid SELECT
    ok_resp = client.post(
        "/api/sql/validate",
        json={"source_id": "enterprise_supply_ops", "sql": "SELECT region_id, region_name FROM regions"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["is_valid"] is True
    assert ok_resp.json()["read_only_verified"] is True

    # 2. Reject destructive DROP / DELETE / UPDATE / INSERT / PRAGMA
    for unsafe_sql in [
        "DROP TABLE vendors",
        "DELETE FROM vendors WHERE vendor_id = 'VND-01'",
        "UPDATE procurement_contracts SET status = 'SUSPENDED'",
        "INSERT INTO regions VALUES ('X', 'Y', 'Z', 'LOW', 'A')",
        "PRAGMA writable_schema = ON",
        "SELECT * FROM regions; DROP TABLE regions;",
        "SELECT * FROM query_history",
    ]:
        bad = client.post(
            "/api/sql/validate",
            json={"source_id": "enterprise_supply_ops", "sql": unsafe_sql},
        )
        assert bad.status_code == 200
        body = bad.json()
        assert body["is_valid"] is False
        assert len(body["issues"]) > 0

        # Ensure execute endpoint also rejects unsafe SQL
        exec_bad = client.post(
            "/api/sql/execute",
            json={"source_id": "enterprise_supply_ops", "sql": unsafe_sql},
        )
        assert exec_bad.status_code == 200
        assert exec_bad.json()["execution_success"] is False


def test_sql_execution_and_bounded_repair():
    # Query with slightly wrong column name 'avg_math_score' instead of 'AvgScrMath' in california_schools_bird_demo
    repair_resp = client.post(
        "/api/sql/execute",
        json={
            "source_id": "california_schools_bird_demo",
            "sql": "SELECT sname, avg_math_score FROM satscores ORDER BY avg_math_score DESC",
            "question": "Top math scores",
            "allow_repair": True,
        },
    )
    assert repair_resp.status_code == 200
    data = repair_resp.json()
    assert data["execution_success"] is True
    assert len(data["repair_attempts"]) >= 1
    assert "AvgScrMath" in data["executed_sql"]
    assert data["row_count"] == 6


def test_sql_result_validation_empty_and_nulls():
    # Empty output detection
    empty_resp = client.post(
        "/api/sql/execute",
        json={
            "source_id": "enterprise_supply_ops",
            "sql": "SELECT * FROM regions WHERE region_id = 'NON_EXISTENT_REGION'",
        },
    )
    assert empty_resp.status_code == 200
    ed = empty_resp.json()
    assert ed["execution_success"] is True
    assert ed["row_count"] == 0
    assert ed["validation"]["empty_output"] is True
    assert ed["validation"]["is_valid"] is False

    # Missing value (NULL) detection on facilities.headcount
    null_resp = client.post(
        "/api/sql/execute",
        json={
            "source_id": "enterprise_supply_ops",
            "sql": "SELECT facility_name, headcount FROM facilities",
        },
    )
    assert null_resp.status_code == 200
    nd = null_resp.json()
    assert nd["validation"]["has_missing_values"] is True


def test_graph_extraction_provenance_and_path_replay():
    # 1. Test signature path: School A -> LOCATED_IN -> Region North
    path_resp = client.post(
        "/api/graph/path",
        json={
            "source_entity_id": "ENT-SCH-A",
            "target_entity_id": "ENT-LOC-CA-NORTH",
            "max_depth": 3,
            "include_inferred": False,
        },
    )
    assert path_resp.status_code == 200
    pdata = path_resp.json()
    assert pdata["path_found"] is True
    assert len(pdata["paths"]) >= 1
    first_path = pdata["paths"][0]
    assert "School A" in first_path["summary_chain"]
    assert "LOCATED_IN" in first_path["summary_chain"]
    assert "Region North" in first_path["summary_chain"]
    assert first_path["all_confirmed"] is True

    # 2. Test missing path behavior between disconnected domains
    no_path_resp = client.post(
        "/api/graph/path",
        json={
            "source_entity_id": "ENT-SCH-A",
            "target_entity_id": "ENT-VND-04",
            "max_depth": 4,
            "include_inferred": True,
        },
    )
    assert no_path_resp.status_code == 200
    assert no_path_resp.json()["path_found"] is False
    assert no_path_resp.json()["paths"] == []

    # 3. Test ingesting a new document into the Knowledge Graph
    ing_resp = client.post(
        "/api/graph/ingest",
        json={
            "source_id": "enterprise_supply_ops",
            "title": "Q4 Gwalior Sub-Tier Inspection",
            "doc_type": "inspection_note",
            "text": "Director Ananya Sharma confirmed that Gwalior Heavy Engineering Hub operates in Region North and supplies Project Mercury.",
        },
    )
    assert ing_resp.status_code == 200
    assert ing_resp.json()["document_id"].startswith("DOC-ING-")
    assert len(ing_resp.json()["relationships_extracted"]) >= 1


def test_entity_resolution_reversible_merge_and_unmerge():
    # 1. Detect duplicate candidates
    det_resp = client.post("/api/entities/resolve", json={"action": "detect"})
    assert det_resp.status_code == 200
    resolutions = det_resp.json()["resolutions"]
    assert len(resolutions) >= 2
    res_ids = {r["resolution_id"] for r in resolutions}
    assert "RES-01" in res_ids

    # 2. Merge RES-01 (Apex Laboratories Inc. -> Apex Labs)
    merge_resp = client.post(
        "/api/entities/resolve",
        json={"action": "merge", "resolution_id": "RES-01"},
    )
    assert merge_resp.status_code == 200
    assert merge_resp.json()["active_merged_count"] >= 1

    # Verify canonical entity ENT-VND-01 preserves merged source records
    ent_resp = client.get("/api/graph/entity/ENT-VND-01")
    assert ent_resp.status_code == 200
    assert len(ent_resp.json()["merged_source_records"]) >= 1

    # 3. Unmerge RES-01 to verify reversibility
    unmerge_resp = client.post(
        "/api/entities/resolve",
        json={"action": "unmerge", "resolution_id": "RES-01"},
    )
    assert unmerge_resp.status_code == 200
    res_status = {r["resolution_id"]: r["status"] for r in unmerge_resp.json()["resolutions"]}
    assert res_status["RES-01"] == "SUGGESTED"


def test_community_detection():
    resp = client.get("/api/graph/communities?source_id=enterprise_supply_ops")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_communities"] >= 2
    comm0 = data["communities"][0]
    assert "community_id" in comm0
    assert "quality_metrics" in comm0
    assert "graph_modularity_q" in comm0["quality_metrics"]

    detail_resp = client.get(f"/api/graph/community/{comm0['community_id']}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["community_id"] == comm0["community_id"]


def test_intelligent_routing_and_end_to_end_ask_flows():
    # 1. SQL Retrieval
    sql_ask = client.post(
        "/api/ask",
        json={
            "source_id": "enterprise_supply_ops",
            "question": "What is the total facility budget and contract value by region?",
        },
    )
    assert sql_ask.status_code == 200
    s_body = sql_ask.json()
    assert s_body["routing"]["selected_strategy"] in ("sql_retrieval", "hybrid_retrieval")
    assert s_body["sql_result"]["execution_success"] is True
    assert s_body["verification_status"] in ("Supported", "Partially supported")

    # 2. Graph / Evidence Path Replay on California Schools
    graph_ask = client.post(
        "/api/ask",
        json={
            "source_id": "california_schools_bird_demo",
            "question": "How is School A connected to Region North and what are its SAT math scores?",
        },
    )
    assert graph_ask.status_code == 200
    g_body = graph_ask.json()
    assert g_body["verification_status"] == "Supported"
    assert len(g_body["evidence_paths"]) >= 1
    assert "School A" in g_body["evidence_paths"][0]["summary_chain"]

    # 3. Conflicting Evidence detection on Adani Green Energy
    conflict_ask = client.post(
        "/api/ask",
        json={
            "source_id": "enterprise_supply_ops",
            "question": "Verify the contract status and compliance audit status for Adani Green Energy at Morena.",
        },
    )
    assert conflict_ask.status_code == 200
    c_body = conflict_ask.json()
    assert c_body["verification_status"] == "Conflicting evidence"
    assert any(c["status"] == "Conflicting evidence" for c in c_body["claim_validations"])

    # 4. Clarification Required for ambiguous entity 'Mercury'
    clar_ask = client.post(
        "/api/ask",
        json={
            "source_id": "enterprise_supply_ops",
            "question": "Tell me about Mercury.",
        },
    )
    assert clar_ask.status_code == 200
    cl_body = clar_ask.json()
    assert cl_body["routing"]["selected_strategy"] == "clarification_required"
    assert cl_body["verification_status"] == "Needs clarification"
    assert cl_body["abstained"] is True
    assert len(cl_body["clarification_choices"]) == 2

    # 5. Insufficient Evidence / Verified Abstention for out-of-domain question
    abst_ask = client.post(
        "/api/ask",
        json={
            "source_id": "enterprise_supply_ops",
            "question": "What was the Bitcoin cryptocurrency trading volume in Atlantis?",
        },
    )
    assert abst_ask.status_code == 200
    ab_body = abst_ask.json()
    assert ab_body["routing"]["selected_strategy"] == "insufficient_evidence"
    assert ab_body["verification_status"] == "Insufficient evidence"
    assert ab_body["abstained"] is True


def test_bird_benchmark_pipeline_and_8b_restriction():
    # 1. Valid <= 8B model smoke run
    ok_eval = client.post(
        "/api/evaluations/run",
        json={
            "dataset_mode": "bird_smoke_synthetic",
            "model_name": "llama3.1:8b-instruct-q4_K_M",
            "model_param_billions": 8.0,
            "max_questions": 6,
        },
    )
    assert ok_eval.status_code == 200
    ev_data = ok_eval.json()
    assert ev_data["restricted_workflow_compliant"] is True
    assert ev_data["is_official_bird_benchmark"] is False
    assert ev_data["total_questions"] == 6
    assert ev_data["execution_accuracy_pct"] == 100.0
    assert "question_id,db_id" in ev_data["csv_export"]

    # 2. Reject > 8B model (e.g. 70B model) per restricted benchmark rule
    bad_eval = client.post(
        "/api/evaluations/run",
        json={
            "dataset_mode": "bird_smoke_synthetic",
            "model_name": "llama3.1:70b-instruct",
            "model_param_billions": 70.0,
            "max_questions": 6,
        },
    )
    assert bad_eval.status_code == 400
    assert "exceeding the restricted benchmark ceiling" in bad_eval.json()["detail"]


def test_custom_data_studio_add_company_and_relationship():
    add_resp = client.post(
        "/api/data/company",
        json={
            "vendor_name": "Hindustan Aeronautics (HAL)",
            "city": "Gwalior",
            "tier_level": 1,
            "compliance_score": 97.5,
            "primary_product": "Avionics & Composite Airframes",
            "contract_value_usd": 4100000.0,
            "facility_id": "FAC-GWL",
            "contract_status": "ACTIVE",
        },
    )
    assert add_resp.status_code == 200
    added = add_resp.json()
    assert added["vendor_name"] == "Hindustan Aeronautics (HAL)"
    assert added["entity_id"].startswith("ENT-")

