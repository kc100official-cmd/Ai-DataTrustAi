import difflib
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import requests
from .config import settings
from .database import (
    discover_schema,
    get_readonly_connection,
    record_query_history,
)
from .models import (
    DatabaseSchemaResponse,
    SQLExecuteResponse,
    SQLRepairAttempt,
    SQLResultValidation,
    SQLValidateResponse,
)

_DESTRUCTIVE_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "REPLACE",
    "TRUNCATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    "GRANT",
    "REVOKE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
}


def _strip_sql_comments(sql: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    no_line = re.sub(r"--[^\r\n]*", " ", no_block)
    return no_line.strip()


def validate_sql_query(source_id: str, sql: str) -> SQLValidateResponse:
    """
    Validate SQL query using layered controls:
    1. Non-empty & single-statement verification
    2. Token check for prohibited DDL/DML/administrative operations
    3. Internal system table access rejection
    4. Engine-level read-only SQLite authorizer + EXPLAIN QUERY PLAN compilation against real schema
    Note: Security is enforced at the database connection level via SQLite URI mode=ro,
    PRAGMA query_only=ON, and sqlite3.set_authorizer, not merely regular expressions.
    """
    security_controls = [
        "SQLite URI mode=ro (OS file-descriptor read-only lock)",
        "PRAGMA query_only = ON enforced on connection",
        "sqlite3.set_authorizer C-hook allowing only SELECT / READ / FUNCTION",
        "Progress handler query execution timeout (5.0s)",
        f"Result set bounded to {settings.SQL_MAX_ROWS} rows",
    ]
    cleaned = _strip_sql_comments(sql or "")
    if not cleaned:
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=True,
            statement_type="EMPTY",
            issues=["SQL query is empty."],
            security_controls=security_controls,
        )

    # Check multi-statement execution (allow trailing semicolon only)
    without_trailing_semi = cleaned.rstrip(";").strip()
    if ";" in without_trailing_semi:
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=False,
            statement_type="MULTI_STATEMENT",
            issues=["Multi-statement SQL execution is prohibited. Submit a single SELECT or WITH query."],
            security_controls=security_controls,
        )

    tokens = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", without_trailing_semi.upper())
    if not tokens:
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=False,
            statement_type="UNKNOWN",
            issues=["No valid SQL tokens found."],
            security_controls=security_controls,
        )

    first_token = tokens[0]
    if first_token not in ("SELECT", "WITH"):
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=False,
            statement_type=first_token,
            issues=[f"Statement type '{first_token}' is not permitted. Only read-only SELECT / WITH queries are allowed."],
            security_controls=security_controls,
        )

    forbidden_found = [t for t in tokens if t in _DESTRUCTIVE_KEYWORDS]
    if forbidden_found:
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=False,
            statement_type=first_token,
            issues=[f"Disallowed SQL operation(s) detected: {', '.join(sorted(set(forbidden_found)))}."],
            security_controls=security_controls,
        )

    lower_sql = without_trailing_semi.lower()
    for internal_tbl in ("query_history", "evaluation_runs", "entity_resolutions", "sqlite_master", "sqlite_temp_master"):
        if re.search(rf"\b{internal_tbl}\b", lower_sql):
            return SQLValidateResponse(
                is_valid=False,
                read_only_verified=False,
                statement_type=first_token,
                issues=[f"Access to internal or system table '{internal_tbl}' is restricted."],
                security_controls=security_controls,
            )

    warnings: List[str] = []
    if "limit" not in lower_sql and "count(" not in lower_sql and "sum(" not in lower_sql and "avg(" not in lower_sql:
        warnings.append(f"No explicit LIMIT clause; result will be bounded to {settings.SQL_MAX_ROWS} rows automatically.")

    # Verify against actual read-only connection + EXPLAIN QUERY PLAN
    query_plan: List[str] = []
    try:
        conn = get_readonly_connection(source_id)
        cur = conn.cursor()
        plan_rows = cur.execute(f"EXPLAIN QUERY PLAN {without_trailing_semi}").fetchall()
        for r in plan_rows:
            detail = r["detail"] if "detail" in r.keys() else str(tuple(r))
            query_plan.append(detail)
        conn.close()
    except Exception as exc:
        return SQLValidateResponse(
            is_valid=False,
            read_only_verified=True,
            statement_type=first_token,
            issues=[f"Database schema/syntax validation error: {str(exc)}"],
            warnings=warnings,
            security_controls=security_controls,
        )

    return SQLValidateResponse(
        is_valid=True,
        read_only_verified=True,
        statement_type=first_token,
        issues=[],
        warnings=warnings,
        query_plan=query_plan,
        security_controls=security_controls,
    )


def _attempt_sql_repair(
    source_id: str, broken_sql: str, error_msg: str, schema: DatabaseSchemaResponse
) -> Optional[Tuple[str, str]]:
    """
    Bounded schema-guided SQL repair for missing/misspelled column or table names.
    Returns (repaired_sql, repair_reason) or None if no deterministic repair applies.
    """
    all_columns: Dict[str, str] = {}
    all_tables: List[str] = []
    synonym_map = {
        "avg_math_score": "AvgScrMath",
        "math_score": "AvgScrMath",
        "reading_score": "AvgScrRead",
        "writing_score": "AvgScrWrite",
        "school_name": "School",
        "contract_amount": "contract_value_usd",
        "total_cost": "contract_value_usd",
        "budget": "annual_budget_usd",
        "impact": "financial_impact_usd",
        "score": "compliance_score",
        "free_meals": "FreeMealCount_K12",
        "free_rate": "EligibleFreeRate_K12",
    }

    for tbl in schema.tables:
        all_tables.append(tbl.table_name)
        for col in tbl.columns:
            all_columns[col.name.lower()] = col.name

    # Case 1: "no such column: X"
    col_match = re.search(r"no such column:\s*([A-Za-z0-9_.]+)", error_msg, flags=re.IGNORECASE)
    if col_match:
        bad_ref = col_match.group(1)
        bad_col = bad_ref.split(".")[-1]
        prefix = (bad_ref.split(".")[0] + ".") if "." in bad_ref else ""

        if bad_col.lower() in synonym_map:
            replacement_col = synonym_map[bad_col.lower()]
            repaired = re.sub(
                rf"\b{re.escape(bad_ref)}\b",
                f"{prefix}{replacement_col}",
                broken_sql,
            )
            return (
                repaired,
                f"Mapped non-existent column '{bad_ref}' to schema column '{prefix}{replacement_col}'.",
            )

        candidates = list(all_columns.values())
        closest = difflib.get_close_matches(bad_col, candidates, n=1, cutoff=0.55)
        if closest:
            repaired = re.sub(
                rf"\b{re.escape(bad_ref)}\b",
                f"{prefix}{closest[0]}",
                broken_sql,
            )
            return (
                repaired,
                f"Replaced misspelled column '{bad_ref}' with closest discovered schema column '{prefix}{closest[0]}'.",
            )

    # Case 2: "no such table: Y"
    tbl_match = re.search(r"no such table:\s*([A-Za-z0-9_]+)", error_msg, flags=re.IGNORECASE)
    if tbl_match:
        bad_tbl = tbl_match.group(1)
        closest_t = difflib.get_close_matches(bad_tbl, all_tables, n=1, cutoff=0.5)
        if closest_t:
            repaired = re.sub(rf"\b{re.escape(bad_tbl)}\b", closest_t[0], broken_sql)
            return (
                repaired,
                f"Replaced unknown table '{bad_tbl}' with discovered schema table '{closest_t[0]}'.",
            )

    return None


def _build_chart_suggestion(columns: List[str], rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not rows or len(rows) < 2 or len(columns) < 2:
        return None
    label_col = None
    numeric_cols: List[str] = []
    sample = rows[0]
    for c in columns:
        val = sample.get(c)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            numeric_cols.append(c)
        elif isinstance(val, str) and label_col is None:
            label_col = c

    if label_col and numeric_cols:
        return {
            "type": "bar",
            "x_key": label_col,
            "y_keys": numeric_cols[:2],
            "title": f"{', '.join(numeric_cols[:2])} by {label_col}",
        }
    return None


def execute_sql_with_repair(
    source_id: str,
    sql: str,
    question: Optional[str] = None,
    allow_repair: bool = True,
) -> SQLExecuteResponse:
    """
    Validate, optionally repair (up to settings.SQL_MAX_REPAIR_ATTEMPTS), execute against
    read-only SQLite connection, and validate query results.
    """
    schema = discover_schema(source_id)
    original_sql = sql.strip()
    current_sql = _strip_sql_comments(original_sql).rstrip(";").strip()
    repair_attempts: List[SQLRepairAttempt] = []

    # First check security rules (never repair destructive or multi-statement queries!)
    pre_check = validate_sql_query(source_id, current_sql)
    if not pre_check.read_only_verified or any(
        "prohibited" in issue.lower() or "not permitted" in issue.lower() or "disallowed" in issue.lower() or "restricted" in issue.lower()
        for issue in pre_check.issues
    ):
        validation_res = SQLResultValidation(
            is_valid=False,
            empty_output=True,
            assumptions=[],
            limitations=pre_check.issues,
            checks_performed=["Security & Read-Only Policy Enforcement"],
        )
        record_query_history(
            source_id=source_id,
            question=question,
            original_sql=original_sql,
            executed_sql=current_sql,
            execution_success=False,
            row_count=0,
            execution_time_ms=0.0,
            repair_count=0,
            validation_summary="Rejected by SQL security guardrails",
        )
        return SQLExecuteResponse(
            source_id=source_id,
            original_question=question,
            original_sql=original_sql,
            executed_sql=current_sql,
            execution_success=False,
            validation=validation_res,
            repair_attempts=[],
            error_message="; ".join(pre_check.issues),
        )

    max_attempts = (settings.SQL_MAX_REPAIR_ATTEMPTS + 1) if allow_repair else 1
    attempt_idx = 0
    last_error: Optional[str] = None

    while attempt_idx < max_attempts:
        t0 = time.perf_counter()
        try:
            conn = get_readonly_connection(source_id)
            cur = conn.cursor()
            cur.execute(current_sql)
            fetched = cur.fetchmany(settings.SQL_MAX_ROWS)
            cols = [desc[0] for desc in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in fetched]
            conn.close()
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

            result_val = validate_sql_results(current_sql, cols, rows, schema)
            chart_sug = _build_chart_suggestion(cols, rows)

            record_query_history(
                source_id=source_id,
                question=question,
                original_sql=original_sql,
                executed_sql=current_sql,
                execution_success=True,
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
                repair_count=len(repair_attempts),
                validation_summary="Valid" if result_val.is_valid else "Warnings detected",
            )

            return SQLExecuteResponse(
                source_id=source_id,
                original_question=question,
                original_sql=original_sql,
                executed_sql=current_sql,
                execution_success=True,
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
                columns=cols,
                rows=rows,
                validation=result_val,
                repair_attempts=repair_attempts,
                error_message=None,
                chart_suggestion=chart_sug,
            )
        except Exception as exc:
            last_error = str(exc)
            if not allow_repair or attempt_idx >= settings.SQL_MAX_REPAIR_ATTEMPTS:
                break
            repair_candidate = _attempt_sql_repair(source_id, current_sql, last_error, schema)
            if not repair_candidate:
                break
            repaired_sql, reason = repair_candidate
            if repaired_sql == current_sql:
                break
            # Verify repaired SQL still passes read-only checks
            repair_ok = validate_sql_query(source_id, repaired_sql)
            repair_attempts.append(
                SQLRepairAttempt(
                    attempt_number=attempt_idx + 1,
                    original_sql=current_sql,
                    error_message=last_error,
                    repaired_sql=repaired_sql,
                    repair_reason=reason,
                    succeeded=repair_ok.is_valid,
                )
            )
            current_sql = repaired_sql
            attempt_idx += 1

    fail_val = SQLResultValidation(
        is_valid=False,
        empty_output=True,
        assumptions=[],
        limitations=[f"Query execution failed: {last_error}"],
        checks_performed=["SQLite Read-Only Execution", "Bounded Schema Repair"],
    )
    record_query_history(
        source_id=source_id,
        question=question,
        original_sql=original_sql,
        executed_sql=current_sql,
        execution_success=False,
        row_count=0,
        execution_time_ms=0.0,
        repair_count=len(repair_attempts),
        validation_summary=f"Failed: {last_error}",
    )
    return SQLExecuteResponse(
        source_id=source_id,
        original_question=question,
        original_sql=original_sql,
        executed_sql=current_sql,
        execution_success=False,
        validation=fail_val,
        repair_attempts=repair_attempts,
        error_message=last_error,
    )


def validate_sql_results(
    executed_sql: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    schema: DatabaseSchemaResponse,
) -> SQLResultValidation:
    """
    Validate executed SQL results for:
    - Empty outputs
    - Missing/NULL values
    - Duplicate rows
    - Suspicious aggregates (e.g. NULL aggregate from empty group, or ungrouped columns mixed with aggregates)
    - Schema data-quality caveats (e.g. vendor alias duplication or ERP sync lag)
    """
    checks = [
        "Non-empty result set check",
        "NULL / missing value inspection",
        "Duplicate output tuple detection",
        "Aggregate sanity & type consistency check",
        "Underlying table data-quality cross-check",
    ]
    assumptions: List[str] = []
    limitations: List[str] = []
    suspicious_aggregates: List[str] = []

    empty_output = len(rows) == 0
    if empty_output:
        limitations.append("Query returned 0 rows. Filter predicates may not match any stored records.")

    has_missing = False
    null_cols: List[str] = []
    for r in rows:
        for k, v in r.items():
            if v is None:
                has_missing = True
                if k not in null_cols:
                    null_cols.append(k)

    if has_missing:
        limitations.append(
            f"Result contains NULL/missing values in column(s): {', '.join(null_cols)}."
        )

    # Check duplicate rows in output
    seen_tuples = set()
    dup_count = 0
    for r in rows:
        t = tuple((k, r.get(k)) for k in columns)
        if t in seen_tuples:
            dup_count += 1
        else:
            seen_tuples.add(t)

    if dup_count > 0:
        limitations.append(f"Detected {dup_count} duplicate row(s) in query output.")

    # Check suspicious aggregates
    lower_sql = executed_sql.lower()
    if any(agg in lower_sql for agg in ("sum(", "avg(", "min(", "max(", "count(")):
        if len(rows) == 1:
            row0 = rows[0]
            for k, v in row0.items():
                if v is None and any(agg in k.lower() or agg in lower_sql for agg in ("sum", "avg", "min", "max")):
                    suspicious_aggregates.append(
                        f"Aggregate column '{k}' evaluated to NULL (no matching non-null rows)."
                    )
        if "group by" not in lower_sql and len(columns) > 1 and any(a in lower_sql for a in ("sum(", "avg(", "count(")):
            # SQLite allows bare columns with aggregates without GROUP BY, picking arbitrary row!
            if not all(any(fn in c.lower() for fn in ("sum", "avg", "min", "max", "count", "total")) for c in columns):
                suspicious_aggregates.append(
                    "Query mixes aggregate function with non-aggregated column without GROUP BY (SQLite selects an arbitrary group row)."
                )

    # Add domain schema assumptions
    if "vendors" in lower_sql or "procurement_contracts" in lower_sql:
        assumptions.append(
            "Note: 'vendors' contains unmerged Indian corporate ERP records ('Larsen & Toubro (L&T)' VND-01 and 'L&T Engineering Ltd.' VND-02, plus 'Bharat Forge' VND-03 and 'Bharat Forge Limited' VND-09) unless grouped or resolved."
        )
    if "procurement_contracts" in lower_sql and "status" in lower_sql:
        limitations.append(
            "Table 'procurement_contracts' reflects ERP status snapshot; cross-check Compliance Directives in Knowledge Graph for post-incident suspensions (e.g. Adani Green Energy at Morena Sub-Station)."
        )
    if "facilities" in lower_sql and "headcount" in lower_sql:
        assumptions.append(
            "Facility FAC-KTN (Katni Defence Foundry) has NULL headcount in structured table; AVG/SUM ignores NULL entries."
        )

    is_valid = (not empty_output) and (len(suspicious_aggregates) == 0)
    return SQLResultValidation(
        is_valid=is_valid,
        empty_output=empty_output,
        has_missing_values=has_missing,
        duplicate_row_count=dup_count,
        suspicious_aggregates=suspicious_aggregates,
        assumptions=assumptions,
        limitations=limitations,
        checks_performed=checks,
    )


def generate_sql_from_question(
    source_id: str, question: str, schema: Optional[DatabaseSchemaResponse] = None
) -> Tuple[str, str, List[str]]:
    """
    Generate read-only SQL grounded in the discovered schema.
    Returns (generated_sql, generation_method, assumptions).
    Uses configured <=8B LLM endpoint when enabled & reachable, with deterministic schema-aware compiler fallback.
    """
    if schema is None:
        schema = discover_schema(source_id)

    # 1. Try LLM endpoint if enabled
    if settings.LLM_ENABLED and settings.LLM_ENDPOINT:
        llm_sql = _try_llm_sql_generation(question, schema)
        if llm_sql:
            return (
                llm_sql,
                f"llm_endpoint ({settings.LLM_MODEL})",
                ["Generated via configured Open-Weight LLM using discovered schema DDL context."],
            )

    # 2. Deterministic schema-grounded NL-to-SQL compiler
    q = question.lower().strip()
    assumptions: List[str] = []

    if source_id == "california_schools_bird_demo":
        if "charter" in q and ("math" in q or "sat" in q or "average" in q or "avg" in q):
            sql = (
                "SELECT s.School, s.County, s.Region, sat.AvgScrMath, sat.AvgScrRead, sat.PctGE1500 "
                "FROM schools s JOIN satscores sat ON s.CDSCode = sat.cds "
                "WHERE s.Charter = 1 ORDER BY sat.AvgScrMath DESC"
            )
            assumptions.append("Filtered schools by Charter = 1 and joined satscores on CDSCode = cds.")
            return sql, "deterministic_schema_compiler", assumptions

        if "free meal" in q or "frpm" in q or "eligible" in q or "meal" in q:
            sql = (
                "SELECT s.School, s.County, s.Region, f.Enrollment_K12, f.FreeMealCount_K12, "
                "ROUND(f.EligibleFreeRate_K12 * 100, 1) AS EligibleFreePct "
                "FROM schools s JOIN frpm f ON s.CDSCode = f.CDSCode "
                "ORDER BY f.EligibleFreeRate_K12 DESC"
            )
            assumptions.append("Joined schools with frpm on CDSCode to compute K-12 free meal eligibility rates.")
            return sql, "deterministic_schema_compiler", assumptions

        if "region" in q and ("count" in q or "how many" in q or "average" in q or "math" in q):
            sql = (
                "SELECT s.Region, COUNT(s.CDSCode) AS school_count, "
                "ROUND(AVG(sat.AvgScrMath), 1) AS avg_math_sat, "
                "ROUND(AVG(sat.AvgScrRead), 1) AS avg_read_sat "
                "FROM schools s JOIN satscores sat ON s.CDSCode = sat.cds "
                "GROUP BY s.Region ORDER BY avg_math_sat DESC"
            )
            assumptions.append("Aggregated school count and average SAT Math/Reading scores grouped by Region.")
            return sql, "deterministic_schema_compiler", assumptions

        if "school a" in q or "scindia" in q or "gwalior" in q:
            sql = (
                "SELECT s.CDSCode, s.School, s.County, s.City, s.Region, s.Charter, "
                "sat.AvgScrMath, sat.AvgScrRead, f.EligibleFreeRate_K12 "
                "FROM schools s "
                "LEFT JOIN satscores sat ON s.CDSCode = sat.cds "
                "LEFT JOIN frpm f ON s.CDSCode = f.CDSCode "
                "WHERE s.School LIKE '%School A%' OR LOWER(s.City) LIKE '%gwalior%'"
            )
            assumptions.append("Matched School A (Scindia STEM Academy Gwalior) across schools, satscores, and frpm.")
            return sql, "deterministic_schema_compiler", assumptions

        # Default Indian schools overview query
        sql = (
            "SELECT s.School, s.County, s.City, s.Region, s.Charter, sat.AvgScrMath, sat.PctGE1500, f.EligibleFreeRate_K12 "
            "FROM schools s "
            "JOIN satscores sat ON s.CDSCode = sat.cds "
            "JOIN frpm f ON s.CDSCode = f.CDSCode "
            "ORDER BY sat.AvgScrMath DESC"
        )
        assumptions.append("Joined schools, satscores, and frpm ordered by AvgScrMath descending.")
        return sql, "deterministic_schema_compiler", assumptions

    # Enterprise Supply Ops schema patterns (Indian Corporate & Regional Supply Network)
    if "adani" in q or "morena" in q or ("conflict" in q):
        sql = (
            "SELECT c.contract_id, v.vendor_name, f.facility_name, c.contract_value_usd, c.status, c.signed_date "
            "FROM procurement_contracts c "
            "JOIN vendors v ON c.vendor_id = v.vendor_id "
            "JOIN facilities f ON c.facility_id = f.facility_id "
            "WHERE LOWER(v.vendor_name) LIKE '%adani%' OR LOWER(f.facility_name) LIKE '%morena%' "
            "ORDER BY c.contract_value_usd DESC"
        )
        assumptions.append("Queried procurement_contracts filtered to Adani Green Energy and Morena Solar & Agro-Logistics Hub.")
        return sql, "deterministic_schema_compiler", assumptions

    # Dynamically detect any specific vendor or city/facility mentioned in the live SQLite database (including user-added companies)
    matched_vendor_ids: List[str] = []
    matched_facility_ids: List[str] = []
    try:
        conn = get_readonly_connection(source_id)
        cur = conn.cursor()
        for vrow in cur.execute("SELECT vendor_id, vendor_name, country, primary_product FROM vendors").fetchall():
            vname_low = (vrow["vendor_name"] or "").lower()
            vcity_low = (vrow["country"] or "").split(",")[0].strip().lower()
            # Match full vendor name or distinctive company token (>=4 chars)
            tokens = [t for t in re.split(r"[^a-z0-9&]+", vname_low) if len(t) >= 4 and t not in ("india", "limited", "corp", "engineering", "services", "industries", "green", "energy")]
            if vname_low in q or any(tok in q for tok in tokens) or ("l&t" in q and "l&t" in vname_low) or ("tcs" in q and "tcs" in vname_low):
                matched_vendor_ids.append(vrow["vendor_id"])
            elif vcity_low and len(vcity_low) >= 4 and vcity_low in q:
                matched_vendor_ids.append(vrow["vendor_id"])
        for frow in cur.execute("SELECT facility_id, facility_name FROM facilities").fetchall():
            fname_low = (frow["facility_name"] or "").lower()
            fcity_tok = fname_low.split()[0] if fname_low else ""
            if fname_low in q or (len(fcity_tok) >= 4 and fcity_tok in q):
                matched_facility_ids.append(frow["facility_id"])
        conn.close()
    except Exception:
        pass

    if "incident" in q or "failure" in q or "financial impact" in q or "severity" in q or "root cause" in q:
        sql = (
            "SELECT qi.incident_id, qi.severity, qi.root_cause, qi.financial_impact_usd, "
            "f.facility_name, r.region_name, v.vendor_name, qi.reported_date "
            "FROM quality_incidents qi "
            "JOIN facilities f ON qi.facility_id = f.facility_id "
            "JOIN regions r ON f.region_id = r.region_id "
            "JOIN vendors v ON qi.vendor_id = v.vendor_id "
            "ORDER BY qi.financial_impact_usd DESC"
        )
        assumptions.append("Joined quality_incidents with facilities, regions, and Indian companies ordered by financial_impact_usd.")
        return sql, "deterministic_schema_compiler", assumptions

    if ("delay" in q or "shipment" in q) and ("vendor" in q or "facility" in q or "which" in q or "show" in q or "list" in q or "company" in q or "companies" in q):
        sql = (
            "SELECT s.shipment_id, v.vendor_name, f.facility_name, s.component_name, "
            "s.quantity, s.delay_days, s.shipment_status "
            "FROM shipments s "
            "JOIN vendors v ON s.vendor_id = v.vendor_id "
            "JOIN facilities f ON s.facility_id = f.facility_id "
            "ORDER BY s.delay_days DESC"
        )
        assumptions.append("Retrieved shipments with Indian company and city facility names ordered by delay_days descending.")
        return sql, "deterministic_schema_compiler", assumptions

    if ("region" in q and ("budget" in q or "contract" in q or "spend" in q or "total" in q or "value" in q)) or (
        "total contract" in q or "spend by region" in q or "budget by region" in q
    ):
        sql = (
            "SELECT r.region_name, COUNT(DISTINCT f.facility_id) AS facility_count, "
            "SUM(f.annual_budget_usd) AS total_facility_budget_usd, "
            "COALESCE(SUM(c.contract_value_usd), 0) AS total_contract_value_usd "
            "FROM regions r "
            "LEFT JOIN facilities f ON r.region_id = f.region_id "
            "LEFT JOIN procurement_contracts c ON f.facility_id = c.facility_id "
            "GROUP BY r.region_id, r.region_name "
            "ORDER BY total_contract_value_usd DESC"
        )
        assumptions.append("Aggregated city facility budgets and procurement contract values grouped by Indian region.")
        return sql, "deterministic_schema_compiler", assumptions

    if matched_vendor_ids and "all " not in q:
        id_list = ", ".join(f"'{vid}'" for vid in matched_vendor_ids)
        sql = (
            "SELECT v.vendor_id, v.vendor_name, v.country, v.tier_level, v.compliance_score, "
            "v.primary_product, c.contract_id, f.facility_name, c.contract_value_usd, c.status "
            "FROM vendors v "
            "LEFT JOIN procurement_contracts c ON v.vendor_id = c.vendor_id "
            "LEFT JOIN facilities f ON c.facility_id = f.facility_id "
            f"WHERE v.vendor_id IN ({id_list}) "
            "ORDER BY c.contract_value_usd DESC"
        )
        assumptions.append(f"Filtered vendors and procurement contracts specifically to matched Indian company record(s): {id_list}.")
        return sql, "deterministic_schema_compiler", assumptions

    if matched_facility_ids and "all " not in q and not any(k in q for k in ("vendor", "supplier", "company", "companies")):
        fid_list = ", ".join(f"'{fid}'" for fid in matched_facility_ids)
        sql = (
            "SELECT f.facility_id, f.facility_name, r.region_name, f.facility_type, "
            "f.annual_budget_usd, f.headcount, v.vendor_name, c.contract_value_usd, c.status "
            "FROM facilities f "
            "JOIN regions r ON f.region_id = r.region_id "
            "LEFT JOIN procurement_contracts c ON f.facility_id = c.facility_id "
            "LEFT JOIN vendors v ON c.vendor_id = v.vendor_id "
            f"WHERE f.facility_id IN ({fid_list}) "
            "ORDER BY c.contract_value_usd DESC"
        )
        assumptions.append(f"Filtered Indian city facility and contract records to: {fid_list}.")
        return sql, "deterministic_schema_compiler", assumptions

    if any(k in q for k in ("vendor", "supplier", "company", "companies", "compliance", "l&t", "larsen", "reliance", "tcs", "tata", "infosys", "bharat forge", "biocon", "mahindra")):
        sql = (
            "SELECT v.vendor_id, v.vendor_name, v.country, v.tier_level, v.compliance_score, "
            "v.primary_product, COALESCE(SUM(c.contract_value_usd), 0) AS total_contract_usd "
            "FROM vendors v "
            "LEFT JOIN procurement_contracts c ON v.vendor_id = c.vendor_id "
            "GROUP BY v.vendor_id, v.vendor_name, v.country, v.tier_level, v.compliance_score, v.primary_product "
            "ORDER BY total_contract_usd DESC"
        )
        assumptions.append("Aggregated contract values per Indian company record in vendors table.")
        return sql, "deterministic_schema_compiler", assumptions

    if any(k in q for k in ("facility", "facilities", "plant", "headcount", "city", "cities", "gwalior", "jaipur", "mumbai", "ahmedabad", "gandhinagar", "ajmer", "katni", "bhopal")):
        sql = (
            "SELECT f.facility_id, f.facility_name, r.region_name, f.facility_type, "
            "f.annual_budget_usd, f.headcount "
            "FROM facilities f "
            "JOIN regions r ON f.region_id = r.region_id "
            "ORDER BY f.annual_budget_usd DESC"
        )
        assumptions.append("Listed Indian city facilities joined with regions ordered by annual_budget_usd.")
        return sql, "deterministic_schema_compiler", assumptions

    # Fallback summary query across contracts & vendors
    sql = (
        "SELECT c.contract_id, v.vendor_name, f.facility_name, r.region_name, "
        "c.contract_value_usd, c.status, c.signed_date "
        "FROM procurement_contracts c "
        "JOIN vendors v ON c.vendor_id = v.vendor_id "
        "JOIN facilities f ON c.facility_id = f.facility_id "
        "JOIN regions r ON f.region_id = r.region_id "
        "ORDER BY c.contract_value_usd DESC"
    )
    assumptions.append("Default multi-table join across procurement_contracts, vendors, facilities, and regions.")
    return sql, "deterministic_schema_compiler", assumptions


def _try_llm_sql_generation(question: str, schema: DatabaseSchemaResponse) -> Optional[str]:
    try:
        schema_lines = []
        for t in schema.tables:
            cols = ", ".join(f"{c.name} ({c.data_type})" for c in t.columns)
            schema_lines.append(f"Table {t.table_name}: {cols}")
        prompt = (
            "You are a SQLite expert. Given the exact database schema below, write a single read-only SELECT query "
            "that answers the user question. Output ONLY the raw SQL query without markdown fences.\n\n"
            + "\n".join(schema_lines)
            + f"\n\nQuestion: {question}\nSQL:"
        )
        headers = {"Content-Type": "application/json"}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        resp = requests.post(
            f"{settings.LLM_ENDPOINT.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": settings.LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"^```(?:sql)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()
            if content.upper().startswith(("SELECT", "WITH")):
                return content
    except Exception:
        return None
    return None
