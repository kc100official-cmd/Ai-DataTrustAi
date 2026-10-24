import difflib
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
from .config import settings
from .models import (
    EvidenceHop,
    EvidencePath,
    GraphEdge,
    GraphNode,
    ProvenanceRecord,
)
from .sample_data import ensure_sample_databases, get_graph_db_path


def _get_graph_conn() -> sqlite3.Connection:
    ensure_sample_databases()
    conn = sqlite3.connect(str(get_graph_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_node(row: sqlite3.Row, aliases_map: Optional[Dict[str, List[str]]] = None) -> GraphNode:
    attrs = {}
    try:
        attrs = json.loads(row["attributes_json"] or "{}")
    except Exception:
        attrs = {}
    node_id = row["id"]
    return GraphNode(
        id=node_id,
        name=row["name"],
        entity_type=row["entity_type"],
        canonical_id=row["canonical_id"],
        attributes=attrs,
        provenance=ProvenanceRecord(
            source_id=row["source_id"],
            source_type=row["source_type"],
            source_record=row["source_record"],
            excerpt=row["excerpt"],
            extraction_method=row["extraction_method"],
            confidence=float(row["confidence"]),
            timestamp=row["timestamp"],
            is_inferred=False,
        ),
        is_merged_alias=bool(row["is_merged"]),
        aliases=(aliases_map or {}).get(node_id, []),
    )


def _row_to_edge(row: sqlite3.Row, entity_names: Dict[str, str]) -> GraphEdge:
    src_id = row["source_entity_id"]
    tgt_id = row["target_entity_id"]
    return GraphEdge(
        id=row["id"],
        source=src_id,
        source_name=entity_names.get(src_id, src_id),
        target=tgt_id,
        target_name=entity_names.get(tgt_id, tgt_id),
        rel_type=row["rel_type"],
        is_inferred=bool(row["is_inferred"]),
        provenance=ProvenanceRecord(
            source_id=row["source_id"],
            source_type=row["source_type"],
            source_record=row["source_record"],
            excerpt=row["excerpt"],
            extraction_method=row["extraction_method"],
            confidence=float(row["confidence"]),
            timestamp=row["timestamp"],
            is_inferred=bool(row["is_inferred"]),
            inference_rule=row["inference_rule"],
        ),
    )


def get_full_graph(
    source_id: Optional[str] = None,
    rel_type: Optional[str] = None,
    include_inferred: bool = True,
    include_merged_aliases: bool = False,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve bounded knowledge graph nodes and edges with full provenance."""
    conn = _get_graph_conn()
    cur = conn.cursor()

    where_clauses = []
    params: List[Any] = []
    if source_id:
        where_clauses.append("source_db = ?")
        params.append(source_id)
    if not include_merged_aliases:
        where_clauses.append("is_merged = 0")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    ent_rows = cur.execute(
        f"SELECT * FROM entities {where_sql} LIMIT ?",
        (*params, settings.GRAPH_MAX_NODES),
    ).fetchall()

    # Build alias map for merged entities
    merged_rows = cur.execute("SELECT id, name, canonical_id FROM entities WHERE is_merged = 1").fetchall()
    aliases_map: Dict[str, List[str]] = {}
    canonical_redirect: Dict[str, str] = {}
    for mr in merged_rows:
        cid = mr["canonical_id"]
        if cid:
            aliases_map.setdefault(cid, []).append(f"{mr['name']} ({mr['id']})")
            canonical_redirect[mr["id"]] = cid

    all_ent_rows = cur.execute("SELECT id, name FROM entities").fetchall()
    entity_names = {r["id"]: r["name"] for r in all_ent_rows}

    nodes: List[GraphNode] = [_row_to_node(r, aliases_map) for r in ent_rows]
    if search_query:
        q_low = search_query.lower().strip()
        matched_ids = {
            n.id
            for n in nodes
            if q_low in n.name.lower()
            or q_low in n.entity_type.lower()
            or q_low in n.id.lower()
            or any(q_low in a.lower() for a in n.aliases)
        }
    else:
        matched_ids = {n.id for n in nodes}

    edge_clauses = []
    edge_params: List[Any] = []
    if source_id:
        edge_clauses.append("source_db = ?")
        edge_params.append(source_id)
    if rel_type and rel_type != "ALL":
        edge_clauses.append("rel_type = ?")
        edge_params.append(rel_type)
    if not include_inferred:
        edge_clauses.append("is_inferred = 0")

    edge_where = ("WHERE " + " AND ".join(edge_clauses)) if edge_clauses else ""
    rel_rows = cur.execute(f"SELECT * FROM relationships {edge_where}", edge_params).fetchall()
    conn.close()

    edges: List[GraphEdge] = []
    included_node_ids = set(matched_ids)
    node_lookup = {n.id: n for n in nodes}

    for r in rel_rows:
        e = _row_to_edge(r, entity_names)
        # If an alias was merged and include_merged_aliases is False, redirect edge endpoint to canonical node
        if not include_merged_aliases:
            if e.source in canonical_redirect:
                e.source = canonical_redirect[e.source]
                e.source_name = entity_names.get(e.source, e.source)
            if e.target in canonical_redirect:
                e.target = canonical_redirect[e.target]
                e.target_name = entity_names.get(e.target, e.target)
        if search_query:
            if e.source in matched_ids or e.target in matched_ids:
                edges.append(e)
                included_node_ids.add(e.source)
                included_node_ids.add(e.target)
        else:
            if e.source in node_lookup and e.target in node_lookup:
                edges.append(e)

    final_nodes = [n for n in nodes if n.id in included_node_ids]
    rel_types = sorted({e.rel_type for e in edges})

    return {
        "nodes": [n.model_dump() for n in final_nodes],
        "edges": [e.model_dump() for e in edges],
        "relationship_types": rel_types,
        "confirmed_edge_count": sum(1 for e in edges if not e.is_inferred),
        "inferred_edge_count": sum(1 for e in edges if e.is_inferred),
        "total_nodes": len(final_nodes),
    }


def get_entity_details(entity_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_graph_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
    if not row:
        conn.close()
        return None

    merged_rows = cur.execute(
        "SELECT id, name, source_record, excerpt FROM entities WHERE canonical_id = ? AND is_merged = 1",
        (entity_id,),
    ).fetchall()
    aliases = [f"{r['name']} ({r['id']})" for r in merged_rows]
    merged_ids = [r["id"] for r in merged_rows]
    node = _row_to_node(row, {entity_id: aliases})

    all_names = {r["id"]: r["name"] for r in cur.execute("SELECT id, name FROM entities").fetchall()}
    lookup_ids = [entity_id, *merged_ids]
    placeholders = ",".join("?" for _ in lookup_ids)
    rel_rows = cur.execute(
        f"SELECT * FROM relationships WHERE source_entity_id IN ({placeholders}) OR target_entity_id IN ({placeholders})",
        (*lookup_ids, *lookup_ids),
    ).fetchall()
    edges: List[GraphEdge] = []
    for r in rel_rows:
        e = _row_to_edge(r, all_names)
        if e.source in merged_ids:
            e.source = entity_id
            e.source_name = all_names.get(entity_id, entity_id)
        if e.target in merged_ids:
            e.target = entity_id
            e.target_name = all_names.get(entity_id, entity_id)
        edges.append(e)
    conn.close()

    return {
        "entity": node.model_dump(),
        "merged_source_records": [dict(r) for r in merged_rows],
        "relationships": [e.model_dump() for e in edges],
    }


def get_entity_neighbors(
    entity_id: str,
    rel_type: Optional[str] = None,
    depth: int = 1,
    include_inferred: bool = True,
) -> Dict[str, Any]:
    """Bounded neighbor expansion up to configurable depth limit."""
    bounded_depth = max(1, min(depth, settings.GRAPH_MAX_DEPTH))
    conn = _get_graph_conn()
    cur = conn.cursor()

    all_ent_rows = cur.execute("SELECT * FROM entities").fetchall()
    canonical_redirect = {
        r["id"]: r["canonical_id"]
        for r in all_ent_rows
        if r["is_merged"] and r["canonical_id"]
    }
    aliases_map: Dict[str, List[str]] = {}
    for r in all_ent_rows:
        if r["is_merged"] and r["canonical_id"]:
            aliases_map.setdefault(r["canonical_id"], []).append(f"{r['name']} ({r['id']})")
    ent_map = {r["id"]: _row_to_node(r, aliases_map) for r in all_ent_rows}
    name_map = {r["id"]: r["name"] for r in all_ent_rows}

    if entity_id in canonical_redirect:
        entity_id = canonical_redirect[entity_id]

    if entity_id not in ent_map:
        conn.close()
        raise ValueError(f"Entity '{entity_id}' not found in knowledge graph.")

    rel_rows = cur.execute("SELECT * FROM relationships").fetchall()
    conn.close()

    all_edges: List[GraphEdge] = []
    for r in rel_rows:
        e = _row_to_edge(r, name_map)
        if e.source in canonical_redirect:
            e.source = canonical_redirect[e.source]
            e.source_name = name_map.get(e.source, e.source)
        if e.target in canonical_redirect:
            e.target = canonical_redirect[e.target]
            e.target_name = name_map.get(e.target, e.target)
        all_edges.append(e)
    if not include_inferred:
        all_edges = [e for e in all_edges if not e.is_inferred]
    if rel_type and rel_type != "ALL":
        all_edges = [e for e in all_edges if e.rel_type == rel_type]

    visited_nodes = {entity_id}
    frontier = {entity_id}
    collected_edges: Dict[str, GraphEdge] = {}

    for _ in range(bounded_depth):
        next_frontier = set()
        for e in all_edges:
            if e.source in frontier or e.target in frontier:
                collected_edges[e.id] = e
                if e.source not in visited_nodes and len(visited_nodes) < settings.GRAPH_MAX_NODES:
                    visited_nodes.add(e.source)
                    next_frontier.add(e.source)
                if e.target not in visited_nodes and len(visited_nodes) < settings.GRAPH_MAX_NODES:
                    visited_nodes.add(e.target)
                    next_frontier.add(e.target)
        frontier = next_frontier
        if not frontier:
            break

    return {
        "center_entity_id": entity_id,
        "depth_applied": bounded_depth,
        "nodes": [ent_map[nid].model_dump() for nid in visited_nodes if nid in ent_map],
        "edges": [e.model_dump() for e in collected_edges.values()],
    }


def find_bounded_paths(
    source_entity_id: str,
    target_entity_id: str,
    max_depth: int = 4,
    include_inferred: bool = True,
) -> List[EvidencePath]:
    """
    Find bounded shortest and multi-hop supporting paths between two entities.
    Constructs EvidencePath objects for Evidence Path Replay.
    Never fabricates a path if none exists.
    """
    bounded_depth = max(1, min(max_depth, settings.GRAPH_MAX_DEPTH))
    conn = _get_graph_conn()
    cur = conn.cursor()

    ent_rows = cur.execute("SELECT * FROM entities").fetchall()
    canonical_redirect = {
        r["id"]: r["canonical_id"]
        for r in ent_rows
        if r["is_merged"] and r["canonical_id"]
    }
    aliases_map: Dict[str, List[str]] = {}
    for r in ent_rows:
        if r["is_merged"] and r["canonical_id"]:
            aliases_map.setdefault(r["canonical_id"], []).append(f"{r['name']} ({r['id']})")
    ent_map = {r["id"]: _row_to_node(r, aliases_map) for r in ent_rows}
    name_map = {r["id"]: r["name"] for r in ent_rows}

    if source_entity_id in canonical_redirect:
        source_entity_id = canonical_redirect[source_entity_id]
    if target_entity_id in canonical_redirect:
        target_entity_id = canonical_redirect[target_entity_id]

    if source_entity_id not in ent_map or target_entity_id not in ent_map:
        conn.close()
        return []

    rel_rows = cur.execute("SELECT * FROM relationships").fetchall()
    conn.close()

    G = nx.Graph()
    edge_lookup: Dict[Tuple[str, str], List[Tuple[GraphEdge, str]]] = {}

    for r in rel_rows:
        if not include_inferred and r["is_inferred"]:
            continue
        e = _row_to_edge(r, name_map)
        if e.source in canonical_redirect:
            e.source = canonical_redirect[e.source]
            e.source_name = name_map.get(e.source, e.source)
        if e.target in canonical_redirect:
            e.target = canonical_redirect[e.target]
            e.target_name = name_map.get(e.target, e.target)
        if e.source == e.target:
            continue
        G.add_edge(e.source, e.target)
        edge_lookup.setdefault((e.source, e.target), []).append((e, "->"))
        edge_lookup.setdefault((e.target, e.source), []).append((e, "<-"))

    if not G.has_node(source_entity_id) or not G.has_node(target_entity_id):
        return []
    if not nx.has_path(G, source_entity_id, target_entity_id):
        return []

    paths_out: List[EvidencePath] = []
    try:
        raw_paths = list(
            nx.all_simple_paths(G, source=source_entity_id, target=target_entity_id, cutoff=bounded_depth)
        )
        # Sort by shortest hop count first
        raw_paths.sort(key=len)
    except Exception:
        return []

    for idx, node_seq in enumerate(raw_paths[:3]):
        hops: List[EvidenceHop] = []
        chain_parts: List[str] = [ent_map[node_seq[0]].name]
        all_confirmed = True
        confidences: List[float] = []

        for step_i in range(len(node_seq) - 1):
            u = node_seq[step_i]
            v = node_seq[step_i + 1]
            candidates = edge_lookup.get((u, v), [])
            # Prefer confirmed edges over inferred edges when multiple edges exist between u and v
            candidates.sort(key=lambda item: (item[0].is_inferred, -item[0].provenance.confidence))
            chosen_edge, direction = candidates[0]
            if chosen_edge.is_inferred:
                all_confirmed = False
            confidences.append(chosen_edge.provenance.confidence)

            u_node = ent_map[u]
            v_node = ent_map[v]
            arrow_str = f"→ {chosen_edge.rel_type} →" if direction == "->" else f"← {chosen_edge.rel_type} ←"
            if chosen_edge.is_inferred:
                arrow_str += " [INFERRED]"
            chain_parts.append(f"{arrow_str} {v_node.name}")

            hops.append(
                EvidenceHop(
                    step_index=step_i + 1,
                    from_entity_id=u,
                    from_entity_name=u_node.name,
                    from_entity_type=u_node.entity_type,
                    rel_type=chosen_edge.rel_type,
                    direction=direction,
                    to_entity_id=v,
                    to_entity_name=v_node.name,
                    to_entity_type=v_node.entity_type,
                    is_inferred=chosen_edge.is_inferred,
                    source_id=chosen_edge.provenance.source_id,
                    source_type=chosen_edge.provenance.source_type,
                    source_record=chosen_edge.provenance.source_record,
                    excerpt=chosen_edge.provenance.excerpt,
                    extraction_method=chosen_edge.provenance.extraction_method,
                    confidence=chosen_edge.provenance.confidence,
                )
            )

        avg_conf = round(sum(confidences) / max(1, len(confidences)), 3)
        explanation = (
            f"Verified {len(hops)}-hop path connecting '{ent_map[source_entity_id].name}' to "
            f"'{ent_map[target_entity_id].name}' via {', '.join(h.source_record for h in hops)}."
        )
        if not all_confirmed:
            explanation += " Contains inferred transitive relationship(s); treat inferred hops as derived hypotheses, not direct database facts."

        paths_out.append(
            EvidencePath(
                path_id=f"PATH-{idx + 1}",
                summary_chain=" ".join(chain_parts),
                hops=hops,
                all_confirmed=all_confirmed,
                has_inferred_hops=not all_confirmed,
                path_confidence=avg_conf,
                supporting_explanation=explanation,
            )
        )

    return paths_out


def ingest_document_to_graph(
    source_id: str,
    title: str,
    doc_type: str,
    text: str,
) -> Dict[str, Any]:
    """
    Extract entities and typed relationships from raw text with full provenance,
    persist them into SQLite graph store, and generate merge suggestions if duplicates exist.
    """
    conn = _get_graph_conn()
    cur = conn.cursor()
    ts = datetime.now(timezone.utc).isoformat()
    doc_hash = hashlib.sha1(f"{title}:{text}".encode("utf-8")).hexdigest()[:8].upper()
    doc_id = f"DOC-ING-{doc_hash}"

    cur.execute(
        "INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?)",
        (doc_id, source_id, title, doc_type, text, ts),
    )

    existing_rows = cur.execute("SELECT id, name, entity_type FROM entities WHERE source_db = ?", (source_id,)).fetchall()
    existing_by_name = {r["name"].lower(): (r["id"], r["name"], r["entity_type"]) for r in existing_rows}

    extracted_entities: List[Dict[str, Any]] = []
    extracted_edges: List[Dict[str, Any]] = []

    # 1. Match known entities mentioned in text
    mentioned_entities: List[Tuple[str, str, str]] = []
    for low_name, (eid, ename, etype) in existing_by_name.items():
        if low_name in text.lower():
            mentioned_entities.append((eid, ename, etype))

    # 2. Pattern NER for new capitalized entities with type indicators (including Indian corporate & city patterns)
    patterns = [
        (r"\b([A-Z][A-Za-z0-9&\-]+(?:\s+[A-Z][A-Za-z0-9&\-]+)*\s+(?:Labs|Laboratories|Corp|Inc\.|GmbH|Ltd\.?|Limited|Industries|Energy|Services|Forge|Motors|Pharma|Power|Steel|Semi|Semiconductors|Systems|Logistics|Academy|High|Plant|Hub|Park|Complex|Tower|Core|Foundry|Fab|Optics))\b", "Organization"),
        (r"\b(Region\s+[A-Z][A-Za-z]+|[A-Z][a-z]+\s+(?:County|Corridor|District|City))\b", "Location"),
        (r"\b(?:Director|Principal|Manager|Dr\.|Chairman|CEO)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b", "Person"),
        (r"\b(Project\s+[A-Z][A-Za-z0-9\-]+|[A-Z][A-Za-z\-]+\s+(?:Modules|Wafers|Transformers|Substrates|Initiative|Turbines|Arrays|Enzymes|Barrels|Powertrains|Suite))\b", "Product"),
        (r"\b(INC-\d+|CNT-\d+|SHP-\d+|DOC-\d{4}-\d+)\b", "Event"),
    ]

    for pat, etype in patterns:
        for match in re.finditer(pat, text):
            candidate_name = match.group(1).strip()
            low_cand = candidate_name.lower()
            if low_cand in existing_by_name:
                continue
            new_id = f"ENT-{hashlib.md5(f'{source_id}:{candidate_name}'.encode()).hexdigest()[:7].upper()}"
            excerpt = text[max(0, match.start() - 40) : min(len(text), match.end() + 60)].strip()
            cur.execute(
                "INSERT OR IGNORE INTO entities VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (
                    new_id,
                    source_id,
                    candidate_name,
                    etype,
                    None,
                    json.dumps({"ingested_from": doc_id}),
                    doc_id,
                    "document",
                    f"{doc_id}:{title}",
                    excerpt,
                    "pattern_ner",
                    0.90,
                    ts,
                ),
            )
            existing_by_name[low_cand] = (new_id, candidate_name, etype)
            mentioned_entities.append((new_id, candidate_name, etype))
            extracted_entities.append({"id": new_id, "name": candidate_name, "entity_type": etype})

    # 3. Extract sentence-level typed relationships between mentioned entities
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    rel_Rules = [
        (r"\b(?:located in|operates in|in\s+Region)\b", "LOCATED_IN"),
        (r"\b(?:supplies|supplies to|supplier to|under contract)\b", "SUPPLIES_TO"),
        (r"\b(?:works for|led by|leads|principal of)\b", "WORKS_FOR"),
        (r"\b(?:manages|oversees|director of)\b", "MANAGES"),
        (r"\b(?:owns|manufactures|produces)\b", "OWNS"),
        (r"\b(?:caused by|attributed to|triggered by)\b", "CAUSED_BY"),
        (r"\b(?:part of|partners with|under the)\b", "PART_OF"),
        (r"\b(?:suspended|references|audit of|directive)\b", "REFERENCES"),
    ]

    for sent in sentences:
        sent_low = sent.lower()
        in_sent = []
        for eid, ename, etype in mentioned_entities:
            pos = sent_low.find(ename.lower())
            if pos != -1:
                in_sent.append((pos, eid, ename, etype))
        in_sent.sort(key=lambda x: x[0])
        if len(in_sent) >= 2:
            detected_rel = "RELATED_TO"
            for rpat, rlabel in rel_Rules:
                if re.search(rpat, sent, flags=re.IGNORECASE):
                    detected_rel = rlabel
                    break
            for i in range(len(in_sent) - 1):
                _, src_id, src_name, _ = in_sent[i]
                _, tgt_id, tgt_name, _ = in_sent[i + 1]
                if src_id == tgt_id:
                    continue
                rel_id = f"REL-{hashlib.md5(f'{doc_id}:{src_id}:{detected_rel}:{tgt_id}'.encode()).hexdigest()[:8].upper()}"
                cur.execute(
                    "INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)",
                    (
                        rel_id,
                        source_id,
                        src_id,
                        tgt_id,
                        detected_rel,
                        doc_id,
                        "document",
                        f"{doc_id}:{title}",
                        sent,
                        "pattern_ner",
                        0.89,
                        ts,
                    ),
                )
                extracted_edges.append(
                    {
                        "id": rel_id,
                        "source": src_id,
                        "source_name": src_name,
                        "rel_type": detected_rel,
                        "target": tgt_id,
                        "target_name": tgt_name,
                        "is_inferred": False,
                    }
                )

    # 4. If entities were mentioned/extracted but no pairwise sentence edges formed, create a Document node and link them via REFERENCES
    if mentioned_entities and not extracted_edges:
        doc_ent_id = f"ENT-{doc_id}"
        cur.execute(
            "INSERT OR IGNORE INTO entities VALUES (?, ?, ?, 'Document', NULL, ?, ?, 'document', ?, ?, 'pattern_ner', 1.0, ?, 0)",
            (
                doc_ent_id,
                source_id,
                f"{title} ({doc_id})",
                json.dumps({"doc_id": doc_id, "doc_type": doc_type}),
                doc_id,
                f"{doc_id}:{title}",
                text[:160].strip(),
                ts,
            ),
        )
        extracted_entities.append({"id": doc_ent_id, "name": f"{title} ({doc_id})", "entity_type": "Document"})
        seen_eids = set()
        for eid, ename, _ in mentioned_entities:
            if eid in seen_eids or eid == doc_ent_id:
                continue
            seen_eids.add(eid)
            rel_id = f"REL-{hashlib.md5(f'{doc_id}:{doc_ent_id}:REFERENCES:{eid}'.encode()).hexdigest()[:8].upper()}"
            cur.execute(
                "INSERT OR REPLACE INTO relationships VALUES (?, ?, ?, ?, 'REFERENCES', ?, 'document', ?, ?, 'pattern_ner', 0.92, ?, 0, NULL)",
                (
                    rel_id,
                    source_id,
                    doc_ent_id,
                    eid,
                    doc_id,
                    f"{doc_id}:{title}",
                    text[:160].strip(),
                    ts,
                ),
            )
            extracted_edges.append(
                {
                    "id": rel_id,
                    "source": doc_ent_id,
                    "source_name": f"{title} ({doc_id})",
                    "rel_type": "REFERENCES",
                    "target": eid,
                    "target_name": ename,
                    "is_inferred": False,
                }
            )

    conn.commit()
    conn.close()

    return {
        "document_id": doc_id,
        "source_id": source_id,
        "title": title,
        "entities_extracted": extracted_entities,
        "relationships_extracted": extracted_edges,
        "total_mentioned_entities": len(mentioned_entities),
    }


def _normalize_entity_name(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\b(inc\.?|corp\.?|llc|gmbh|ltd\.?|laboratories|labs|semiconductors|semi|systems)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def detect_and_manage_entity_resolution(
    action: str = "detect",
    duplicate_entity_id: Optional[str] = None,
    canonical_entity_id: Optional[str] = None,
    resolution_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect duplicate/alias entities, execute reversible merges, or unmerge previously merged entities.
    Original source records and provenance are always preserved.
    """
    conn = _get_graph_conn()
    cur = conn.cursor()
    ts = datetime.now(timezone.utc).isoformat()

    if action == "merge":
        if resolution_id:
            res_row = cur.execute("SELECT * FROM entity_resolutions WHERE id = ?", (resolution_id,)).fetchone()
            if not res_row:
                conn.close()
                raise ValueError(f"Resolution ID '{resolution_id}' not found.")
            dup_id = res_row["duplicate_entity_id"]
            can_id = res_row["canonical_entity_id"]
            cur.execute("UPDATE entity_resolutions SET status = 'MERGED', updated_at = ? WHERE id = ?", (ts, resolution_id))
        elif duplicate_entity_id and canonical_entity_id:
            dup_id = duplicate_entity_id
            can_id = canonical_entity_id
            rid = f"RES-{hashlib.md5(f'{dup_id}:{can_id}'.encode()).hexdigest()[:6].upper()}"
            cur.execute(
                "INSERT OR REPLACE INTO entity_resolutions VALUES (?, ?, ?, ?, ?, ?, 'MERGED', ?)",
                (
                    rid,
                    dup_id,
                    can_id,
                    0.90,
                    f"User-confirmed entity resolution merging {dup_id} into {can_id}.",
                    json.dumps([f"Merged {dup_id} -> {can_id} preserving provenance"]),
                    ts,
                ),
            )
        else:
            conn.close()
            raise ValueError("Provide resolution_id or both duplicate_entity_id and canonical_entity_id to merge.")

        cur.execute("UPDATE entities SET canonical_id = ?, is_merged = 1 WHERE id = ?", (can_id, dup_id))
        conn.commit()

    elif action == "unmerge":
        if resolution_id:
            res_row = cur.execute("SELECT * FROM entity_resolutions WHERE id = ?", (resolution_id,)).fetchone()
            if not res_row:
                conn.close()
                raise ValueError(f"Resolution ID '{resolution_id}' not found.")
            dup_id = res_row["duplicate_entity_id"]
            cur.execute("UPDATE entity_resolutions SET status = 'SUGGESTED', updated_at = ? WHERE id = ?", (ts, resolution_id))
            cur.execute("UPDATE entities SET is_merged = 0 WHERE id = ?", (dup_id,))
        elif duplicate_entity_id:
            cur.execute("UPDATE entities SET is_merged = 0 WHERE id = ?", (duplicate_entity_id,))
            cur.execute(
                "UPDATE entity_resolutions SET status = 'SUGGESTED', updated_at = ? WHERE duplicate_entity_id = ?",
                (ts, duplicate_entity_id),
            )
        else:
            conn.close()
            raise ValueError("Provide resolution_id or duplicate_entity_id to unmerge.")
        conn.commit()

    # Also dynamically scan for any additional high-similarity entity pairs
    ent_rows = cur.execute("SELECT * FROM entities").fetchall()
    ent_dict = {r["id"]: dict(r) for r in ent_rows}

    for i in range(len(ent_rows)):
        for j in range(i + 1, len(ent_rows)):
            e1 = ent_rows[i]
            e2 = ent_rows[j]
            if e1["source_db"] != e2["source_db"] or e1["entity_type"] != e2["entity_type"]:
                continue
            n1 = _normalize_entity_name(e1["name"])
            n2 = _normalize_entity_name(e2["name"])
            if not n1 or not n2:
                continue
            sim = difflib.SequenceMatcher(None, n1, n2).ratio()
            if sim >= 0.82 and e1["id"] != e2["id"]:
                existing = cur.execute(
                    "SELECT id FROM entity_resolutions WHERE (duplicate_entity_id = ? AND canonical_entity_id = ?) OR (duplicate_entity_id = ? AND canonical_entity_id = ?)",
                    (e1["id"], e2["id"], e2["id"], e1["id"]),
                ).fetchone()
                if not existing:
                    rid = f"RES-{hashlib.md5(f'{e2['id']}:{e1['id']}'.encode()).hexdigest()[:6].upper()}"
                    cur.execute(
                        "INSERT INTO entity_resolutions VALUES (?, ?, ?, ?, ?, ?, 'SUGGESTED', ?)",
                        (
                            rid,
                            e2["id"],
                            e1["id"],
                            round(sim, 2),
                            f"Normalized token similarity ({round(sim * 100)}%) between '{e2['name']}' and '{e1['name']}'.",
                            json.dumps([e1["excerpt"], e2["excerpt"]]),
                            ts,
                        ),
                    )
    conn.commit()

    res_rows = cur.execute("SELECT * FROM entity_resolutions ORDER BY similarity_score DESC").fetchall()
    conn.close()

    candidates = []
    for r in res_rows:
        dup_ent = ent_dict.get(r["duplicate_entity_id"], {})
        can_ent = ent_dict.get(r["canonical_entity_id"], {})
        candidates.append(
            {
                "resolution_id": r["id"],
                "duplicate_entity_id": r["duplicate_entity_id"],
                "duplicate_name": dup_ent.get("name", r["duplicate_entity_id"]),
                "duplicate_source_record": dup_ent.get("source_record", ""),
                "canonical_entity_id": r["canonical_entity_id"],
                "canonical_name": can_ent.get("name", r["canonical_entity_id"]),
                "canonical_source_record": can_ent.get("source_record", ""),
                "similarity_score": r["similarity_score"],
                "reason": r["reason"],
                "evidence": json.loads(r["evidence_json"] or "[]"),
                "status": r["status"],
                "reversible": True,
                "updated_at": r["updated_at"],
            }
        )

    return {
        "action_performed": action,
        "resolutions": candidates,
        "active_merged_count": sum(1 for c in candidates if c["status"] == "MERGED"),
        "pending_suggestions_count": sum(1 for c in candidates if c["status"] == "SUGGESTED"),
    }
