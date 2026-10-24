"""Incremental retrieval index and source-backed contradiction extraction."""

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .document_safety import expand_query_terms, sanitize_document_text, tokenize


_STATUS_VALUES = {
    "active": "active", "operational": "active", "in service": "active", "suspended": "suspended",
    "inactive": "inactive", "terminated": "terminated", "cancelled": "cancelled", "canceled": "cancelled",
    "approved": "approved", "rejected": "rejected", "compliant": "compliant", "non-compliant": "non-compliant",
    "noncompliant": "non-compliant", "passed": "passed", "failed": "failed", "open": "open", "closed": "closed",
}
_STATUS_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(value) for value in _STATUS_VALUES), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_FACT_PATTERNS = [
    ("location", re.compile(r"\b(?:located in|operates in|based in|headquartered in|registered in)\s+([A-Z][A-Za-z.'’&-]*(?:\s+[A-Z][A-Za-z.'’&-]*){0,3})")),
    ("leadership", re.compile(r"\b(?:led by|managed by|directed by|principal is)\s+([A-Z][A-Za-z.'’&-]*(?:\s+[A-Z][A-Za-z.'’&-]*){0,3})")),
    ("ownership", re.compile(r"\b(?:owned by|controlled by)\s+([A-Z][A-Za-z.'’&-]*(?:\s+[A-Z][A-Za-z.'’&-]*){0,3})")),
]
_SENTENCE_RE = re.compile(r"(?<=[.!?।！？])\s+|[\r\n]+")
_NEGATION_RE = re.compile(r"(?:\bnot|\bnever|\bno longer|\bisn['’]?t|\bwasn['’]?t)\s*$", re.IGNORECASE)


def ensure_document_store(conn: sqlite3.Connection) -> None:
    """Create the incremental index and backfill it once for existing documents."""
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_metadata (
            document_id TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            ignored_instruction_count INTEGER NOT NULL DEFAULT 0,
            indexed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS document_terms (
            document_id TEXT NOT NULL,
            term TEXT NOT NULL,
            frequency INTEGER NOT NULL,
            in_title INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (document_id, term)
        );
        CREATE INDEX IF NOT EXISTS idx_document_terms_term ON document_terms(term, document_id);
        CREATE TABLE IF NOT EXISTS document_claims (
            claim_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            title TEXT NOT NULL,
            claim_key TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            value TEXT NOT NULL,
            excerpt TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_document_claims_key ON document_claims(claim_key, value, document_id);
        """
    )
    if cur.execute("PRAGMA user_version").fetchone()[0] >= 1:
        return

    entity_rows = cur.execute("SELECT name, entity_type FROM entities ORDER BY length(name) DESC").fetchall()
    entity_names = [(row[0], row[1]) for row in entity_rows]
    doc_rows = cur.execute("SELECT id, source_id, title, doc_type, content FROM documents").fetchall()
    for row in doc_rows:
        index_document(
            conn,
            document_id=row[0],
            source_id=row[1],
            title=row[2],
            content=row[4],
            entity_names=entity_names,
        )
    cur.execute("PRAGMA user_version = 1")


def index_document(
    conn: sqlite3.Connection,
    document_id: str,
    source_id: str,
    title: str,
    content: str,
    entity_names: Optional[Sequence[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Replace one document's postings and claims in the same SQLite transaction."""
    safe_content, ignored_count = sanitize_document_text(content)
    safe_title, ignored_title_count = sanitize_document_text(title)
    ignored_count += ignored_title_count
    title_terms = Counter(tokenize(safe_title))
    all_terms = Counter(tokenize(f"{safe_title} {safe_content}"))
    terms = [
        (document_id, term, frequency, int(term in title_terms))
        for term, frequency in all_terms.items()
    ]
    cur = conn.cursor()
    cur.execute("DELETE FROM document_terms WHERE document_id = ?", (document_id,))
    cur.execute("DELETE FROM document_claims WHERE document_id = ?", (document_id,))
    cur.execute("DELETE FROM document_metadata WHERE document_id = ?", (document_id,))
    cur.executemany(
        "INSERT INTO document_terms (document_id, term, frequency, in_title) VALUES (?, ?, ?, ?)",
        terms,
    )

    content_hash = hashlib.sha256(f"{safe_title}\n{safe_content}".encode("utf-8")).hexdigest()
    cur.execute(
        "INSERT INTO document_metadata VALUES (?, ?, ?, ?, ?)",
        (document_id, content_hash, sum(all_terms.values()), ignored_count, datetime.now(timezone.utc).isoformat()),
    )
    names = entity_names
    if names is None:
        names = [(r[0], r[1]) for r in cur.execute("SELECT name, entity_type FROM entities ORDER BY length(name) DESC")]
    claims = extract_document_claims(document_id, source_id, safe_title, safe_content, names)
    cur.executemany(
        """INSERT OR REPLACE INTO document_claims
           (claim_id, document_id, source_id, title, claim_key, subject, predicate, value, excerpt)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        claims,
    )
    return {"token_count": sum(all_terms.values()), "ignored_instruction_count": ignored_count, "content_hash": content_hash}


def extract_document_claims(
    document_id: str,
    source_id: str,
    title: str,
    content: str,
    entity_names: Sequence[Tuple[str, str]],
) -> List[Tuple[str, str, str, str, str, str, str, str, str]]:
    claims = []
    for sentence in _SENTENCE_RE.split(content):
        clean = sentence.strip()
        if not clean:
            continue
        normalized_sentence = clean.casefold()
        subject_matches = [
            (name, entity_type)
            for name, entity_type in entity_names
            if len(name.strip()) > 2 and name.casefold() in normalized_sentence
        ]
        def find_subject(end_position: int, status_clause: bool = False) -> Optional[str]:
            if subject_matches:
                # Prefer a specific named organization/person/product over broad place nodes.
                return sorted(subject_matches, key=lambda pair: (pair[1].lower() in {"location", "region"}, -len(pair[0])))[0][0]
            lead = clean[:end_position]
            suffix = r"\s+(?:status\s*(?:is|=|:)\s*|(?:is|was|has\s+been|remains)\s*)$" if status_clause else r"\s*$"
            subject_match = re.search(
                r"\b([A-Z][A-Za-z0-9&.'’()-]*(?:\s+[A-Z][A-Za-z0-9&.'’()-]*){0,5})" + suffix,
                lead,
            )
            if not subject_match:
                return None
            subject = re.sub(r"\s+status$", "", subject_match.group(1), flags=re.IGNORECASE).strip()
            if subject.casefold() in {"the company", "this company", "the organization", "the vendor", "it"}:
                return None
            return subject or None

        for match in _STATUS_RE.finditer(clean):
            prefix = clean[max(0, match.start() - 16):match.start()]
            if _NEGATION_RE.search(prefix):
                continue
            subject = find_subject(match.start(), status_clause=True)
            if not subject:
                continue
            raw_value = match.group(0).casefold()
            value = _STATUS_VALUES[raw_value]
            claim_key = f"{_normalize_claim_subject(subject)}|status"
            claim_id = hashlib.sha1(f"{document_id}:{claim_key}:{value}:{clean}".encode("utf-8")).hexdigest()
            claims.append((claim_id, document_id, source_id, title, claim_key, subject, "status", value, clean[:1200]))

        for predicate, pattern in _FACT_PATTERNS:
            for match in pattern.finditer(clean):
                subject = find_subject(match.start())
                value = match.group(1).strip().rstrip(".,;:")
                if not subject or not value:
                    continue
                claim_key = f"{_normalize_claim_subject(subject)}|{predicate}"
                normalized_value = _normalize_claim_subject(value)
                claim_id = hashlib.sha1(f"{document_id}:{claim_key}:{normalized_value}:{clean}".encode("utf-8")).hexdigest()
                claims.append((claim_id, document_id, source_id, title, claim_key, subject, predicate, value, clean[:1200]))
    return claims


def _normalize_claim_subject(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def search_document_scores(
    conn: sqlite3.Connection,
    query: str,
    source_id: Optional[str] = None,
) -> Dict[str, float]:
    terms = sorted(expand_query_terms(query))
    if not terms:
        return {}
    params: List[Any] = list(terms)
    source_clause = ""
    if source_id:
        source_clause = " AND d.source_id = ?"
        params.append(source_id)
    placeholders = ",".join("?" for _ in terms)
    rows = conn.execute(
        f"""SELECT t.document_id, t.term, t.frequency, t.in_title
            FROM document_terms t JOIN documents d ON d.id = t.document_id
            WHERE t.term IN ({placeholders}){source_clause}""",
        params,
    ).fetchall()
    if not rows:
        return {}

    if source_id:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents WHERE source_id = ?", (source_id,)).fetchone()[0]
        df_rows = conn.execute(
            f"""SELECT t.term, COUNT(*) AS df FROM document_terms t
                JOIN documents d ON d.id = t.document_id
                WHERE t.term IN ({placeholders}) AND d.source_id = ? GROUP BY t.term""",
            (*terms, source_id),
        ).fetchall()
    else:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        df_rows = conn.execute(
            f"SELECT term, COUNT(*) AS df FROM document_terms WHERE term IN ({placeholders}) GROUP BY term",
            terms,
        ).fetchall()
    if not doc_count:
        return {}

    df = {row[0]: row[1] for row in df_rows}
    weights = {term: math.log(1 + (doc_count + 1) / (df.get(term, 0) + 1)) for term in terms}
    total_weight = sum(weights.values()) or 1.0
    matched: Dict[str, Dict[str, Tuple[int, bool]]] = defaultdict(dict)
    for row in rows:
        matched[row[0]][row[1]] = (row[2], bool(row[3]))
    scores = {}
    for doc_id, term_rows in matched.items():
        score = 0.0
        for term, (frequency, in_title) in term_rows.items():
            frequency_boost = min(1.0 + 0.12 * math.log1p(frequency), 1.45)
            title_boost = 1.25 if in_title else 1.0
            score += weights[term] * frequency_boost * title_boost
        scores[doc_id] = min(1.0, score / total_weight)
    return scores


def get_document_conflict_groups(
    conn: sqlite3.Connection,
    document_ids: Optional[Iterable[str]] = None,
    source_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: List[Any] = []
    where = []
    if source_id:
        where.append("c.source_id = ?")
        params.append(source_id)
    condition = "WHERE " + " AND ".join(where) if where else ""
    rows = conn.execute(
        f"""SELECT c.document_id, c.source_id, c.title, c.claim_key, c.subject, c.predicate,
                   c.value, c.excerpt
            FROM document_claims c {condition}
            ORDER BY c.claim_key, c.document_id""",
        params,
    ).fetchall()
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["claim_key"]].append({
            "document_id": row["document_id"], "source_id": row["source_id"], "title": row["title"],
            "subject": row["subject"], "predicate": row["predicate"], "value": row["value"], "excerpt": row["excerpt"],
        })
    requested = set(document_ids or [])
    conflicts = []
    for claim_key, claims in groups.items():
        values = {claim["value"] for claim in claims}
        docs = {claim["document_id"] for claim in claims}
        if len(values) < 2 or len(docs) < 2:
            continue
        if requested and not docs.intersection(requested):
            continue
        conflicts.append({"claim_key": claim_key, "subject": claims[0]["subject"], "predicate": claims[0]["predicate"], "claims": claims})
    return conflicts

