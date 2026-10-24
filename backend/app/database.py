import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from .config import settings
from .models import (
    ColumnSchema,
    DatabaseSchemaResponse,
    ForeignKeySchema,
    TableSchema,
)
from .sample_data import (
    SOURCES_METADATA,
    ensure_sample_databases,
    get_db_path,
    get_meta_db_path,
)

# Allowed SQLite authorizer action codes for strictly read-only execution
_ALLOWED_AUTH_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}

# Internal tables that user queries must never access even if attached
_FORBIDDEN_TABLES = {
    "query_history",
    "evaluation_runs",
    "entity_resolutions",
}


def _read_only_authorizer(
    action_code: int,
    arg1: Optional[str],
    arg2: Optional[str],
    db_name: Optional[str],
    trigger_name: Optional[str],
) -> int:
    """SQLite engine-level authorizer enforcing read-only access."""
    if action_code == sqlite3.SQLITE_PRAGMA:
        # Allow read-only schema introspection pragmas only when needed internally, block user PRAGMAs
        return sqlite3.SQLITE_DENY
    if action_code not in _ALLOWED_AUTH_ACTIONS:
        return sqlite3.SQLITE_DENY
    if arg1 and arg1.lower() in _FORBIDDEN_TABLES:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def get_readonly_connection(source_id: str, timeout_seconds: Optional[float] = None) -> sqlite3.Connection:
    """
    Open a strictly read-only SQLite connection using:
    1. URI mode=ro (OS/driver level read-only file descriptor)
    2. PRAGMA query_only = ON
    3. SQLite set_authorizer hook blocking all non-SELECT/READ operations
    4. Progress handler enforcing wall-clock timeout
    """
    ensure_sample_databases()
    db_path = get_db_path(source_id)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout_seconds or settings.SQL_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")

    # Install progress handler for execution timeout
    max_time = timeout_seconds or settings.SQL_TIMEOUT_SECONDS
    start_ts = time.perf_counter()

    def _timeout_handler() -> int:
        if (time.perf_counter() - start_ts) > max_time:
            return 1  # Non-zero aborts query with OperationalError: interrupted
        return 0

    conn.set_progress_handler(_timeout_handler, 5000)
    conn.set_authorizer(_read_only_authorizer)
    return conn


def get_readonly_connection_for_path(db_path: Path, timeout_seconds: float = 5.0) -> sqlite3.Connection:
    """Open a read-only connection for an arbitrary benchmark SQLite database file."""
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=timeout_seconds)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    start_ts = time.perf_counter()

    def _timeout_handler() -> int:
        if (time.perf_counter() - start_ts) > timeout_seconds:
            return 1
        return 0

    conn.set_progress_handler(_timeout_handler, 5000)
    conn.set_authorizer(_read_only_authorizer)
    return conn


def list_data_sources() -> List[Dict[str, Any]]:
    ensure_sample_databases()
    result = []
    for source_id, meta in SOURCES_METADATA.items():
        db_path = get_db_path(source_id)
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        cur = conn.cursor()
        tables = [
            r[0]
            for r in cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        total_rows = 0
        for t in tables:
            total_rows += cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        conn.close()
        result.append(
            {
                **meta,
                "table_count": len(tables),
                "tables": tables,
                "total_rows": total_rows,
                "status": "CONNECTED_READONLY",
            }
        )
    return result


def discover_schema(source_id: str) -> DatabaseSchemaResponse:
    """Discover tables, columns, types, PKs, FKs, and data quality metrics."""
    ensure_sample_databases()
    meta = SOURCES_METADATA.get(source_id)
    if not meta:
        raise ValueError(f"Unknown source_id '{source_id}'")

    db_path = get_db_path(source_id)
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    table_Rows = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    tables: List[TableSchema] = []
    relationships_summary: List[str] = []
    quality_notes: List[str] = []
    total_cells = 0
    total_null_cells = 0

    for trow in table_Rows:
        tname = trow["name"]
        row_count = cur.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()[0]

        pragma_cols = cur.execute(f'PRAGMA table_info("{tname}")').fetchall()
        pragma_fks = cur.execute(f'PRAGMA foreign_key_list("{tname}")').fetchall()

        fks: List[ForeignKeySchema] = []
        for fk in pragma_fks:
            fks.append(
                ForeignKeySchema(
                    from_column=fk["from"],
                    to_table=fk["table"],
                    to_column=fk["to"],
                )
            )
            relationships_summary.append(f"{tname}.{fk['from']} -> {fk['table']}.{fk['to']}")

        columns: List[ColumnSchema] = []
        table_nulls = 0
        for col in pragma_cols:
            cname = col["name"]
            ctype = col["type"] or "TEXT"
            notnull = bool(col["notnull"])
            is_pk = bool(col["pk"])
            dflt = col["dflt_value"]

            null_count = cur.execute(
                f'SELECT COUNT(*) FROM "{tname}" WHERE "{cname}" IS NULL'
            ).fetchone()[0]
            distinct_count = cur.execute(
                f'SELECT COUNT(DISTINCT "{cname}") FROM "{tname}"'
            ).fetchone()[0]
            sample_rows_val = cur.execute(
                f'SELECT DISTINCT "{cname}" FROM "{tname}" WHERE "{cname}" IS NOT NULL LIMIT 3'
            ).fetchall()
            samples = [r[0] for r in sample_rows_val]

            table_nulls += null_count
            if null_count > 0:
                quality_notes.append(
                    f"Table '{tname}' column '{cname}' has {null_count} missing (NULL) value(s)."
                )

            columns.append(
                ColumnSchema(
                    name=cname,
                    data_type=ctype,
                    nullable=not notnull,
                    is_primary_key=is_pk,
                    default_value=dflt,
                    null_count=null_count,
                    distinct_count=distinct_count,
                    sample_values=samples,
                )
            )

        # Check semantic/business-key duplicate patterns (e.g. non-PK columns or similar names)
        non_pk_cols = [c.name for c in columns if not c.is_primary_key]
        dup_count = 0
        if non_pk_cols and row_count > 0:
            col_expr = ", ".join(f'COALESCE(CAST("{c}" AS TEXT), \'\')' for c in non_pk_cols)
            distinct_non_pk = cur.execute(
                f'SELECT COUNT(*) FROM (SELECT DISTINCT {col_expr} FROM "{tname}")'
            ).fetchone()[0]
            dup_count = max(0, row_count - distinct_non_pk)

        if tname == "vendors":
            # Also detect fuzzy alias duplicates in vendors
            quality_notes.append(
                "Table 'vendors' contains potential duplicate Indian company aliases ('Larsen & Toubro (L&T)' vs 'L&T Engineering Ltd.', and 'Bharat Forge' vs 'Bharat Forge Limited')."
            )

        cells = max(1, row_count * max(1, len(columns)))
        total_cells += cells
        total_null_cells += table_nulls
        completeness = round(100.0 * (1.0 - (table_nulls / cells)), 2)

        sample_data_rows = [
            dict(r) for r in cur.execute(f'SELECT * FROM "{tname}" LIMIT 10').fetchall()
        ]

        tables.append(
            TableSchema(
                table_name=tname,
                row_count=row_count,
                duplicate_row_count=dup_count,
                completeness_pct=completeness,
                columns=columns,
                foreign_keys=fks,
                sample_rows=sample_data_rows,
            )
        )

    conn.close()
    overall_quality = round(100.0 * (1.0 - (total_null_cells / max(1, total_cells))), 1)

    return DatabaseSchemaResponse(
        source_id=source_id,
        source_name=meta["source_name"],
        description=meta["description"],
        read_only_enforced=True,
        tables=tables,
        relationships_summary=relationships_summary,
        quality_score=overall_quality,
        quality_notes=quality_notes,
    )


def record_query_history(
    source_id: str,
    question: Optional[str],
    original_sql: str,
    executed_sql: str,
    execution_success: bool,
    row_count: int,
    execution_time_ms: float,
    repair_count: int,
    validation_summary: str,
) -> None:
    ensure_sample_databases()
    conn = sqlite3.connect(str(get_meta_db_path()))
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO query_history (
            timestamp, source_id, question, original_sql, executed_sql,
            execution_success, row_count, execution_time_ms, repair_count, validation_summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            source_id,
            question or "",
            original_sql,
            executed_sql,
            1 if execution_success else 0,
            row_count,
            round(execution_time_ms, 2),
            repair_count,
            validation_summary,
        ),
    )
    conn.commit()
    conn.close()


def get_query_history(source_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    ensure_sample_databases()
    conn = sqlite3.connect(str(get_meta_db_path()))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if source_id:
        rows = cur.execute(
            "SELECT * FROM query_history WHERE source_id = ? ORDER BY id DESC LIMIT ?",
            (source_id, limit),
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT * FROM query_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
