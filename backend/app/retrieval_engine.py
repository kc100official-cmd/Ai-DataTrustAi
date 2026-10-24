import sqlite3
from typing import Any, Dict, List, Optional, Set
import numpy as np
import requests
from sklearn.metrics.pairwise import cosine_similarity
from .config import settings
from .document_safety import expand_query_terms, sanitize_document_text, tokenize
from .document_store import get_document_conflict_groups, search_document_scores
from .sample_data import ensure_sample_databases, get_graph_db_path


def search_documents_and_excerpts(
    query: str,
    source_id: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Search the incrementally maintained document index and graph provenance."""
    ensure_sample_databases()
    conn = sqlite3.connect(str(get_graph_db_path()))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if source_id:
        doc_rows = cur.execute("SELECT * FROM documents WHERE source_id = ?", (source_id,)).fetchall()
        rel_rows = cur.execute("SELECT * FROM relationships WHERE source_db = ?", (source_id,)).fetchall()
    else:
        doc_rows = cur.execute("SELECT * FROM documents").fetchall()
        rel_rows = cur.execute("SELECT * FROM relationships").fetchall()
    if not doc_rows or not query.strip():
        conn.close()
        return {"query": query, "retrieval_method": "incremental_lexical_index", "embeddings_active": False, "results": []}

    safe_text_by_id = {row["id"]: sanitize_document_text(row["content"])[0] for row in doc_rows}
    safe_title_by_id = {row["id"]: sanitize_document_text(row["title"])[0] for row in doc_rows}
    corpus = [
        {
            "id": row["id"], "source_id": row["source_id"], "title": safe_title_by_id[row["id"]],
            "doc_type": row["doc_type"], "excerpt": safe_text_by_id[row["id"]],
            "record_type": "document", "created_at": row["created_at"],
        }
        for row in doc_rows
    ]
    texts = [f"{item['title']} {item['excerpt']}" for item in corpus]
    ranked_scores: Dict[str, float] = {}
    retrieval_method = "incremental_lexical_index"
    embeddings_active = False

    if settings.EMBEDDINGS_ENABLED and settings.EMBEDDING_ENDPOINT:
        dense_scores = _try_dense_embeddings(query, texts)
        if dense_scores is not None:
            ranked_scores = {item["id"]: float(score) for item, score in zip(corpus, dense_scores)}
            retrieval_method = f"dense_embeddings ({settings.EMBEDDING_MODEL})"
            embeddings_active = True
    if not embeddings_active:
        ranked_scores = search_document_scores(conn, query, source_id=source_id)

    ranked_docs = sorted(
        ((item, ranked_scores.get(item["id"], 0.0)) for item in corpus),
        key=lambda pair: pair[1], reverse=True,
    )
    results = [
        {**item, "score": round(float(score), 4), "retrieval_mode": retrieval_method, "conflicts": []}
        for item, score in ranked_docs[:max(1, min(top_k, 50))]
        if score > (0.05 if embeddings_active else 0.0)
    ]

    # Preserve graph-provenance search alongside document retrieval without rebuilding an index.
    query_terms: Set[str] = expand_query_terms(query)
    seen_excerpts = {item["excerpt"] for item in results}
    if query_terms:
        for row in rel_rows:
            excerpt = sanitize_document_text(row["excerpt"])[0]
            if not excerpt or excerpt in seen_excerpts:
                continue
            matched = query_terms.intersection(tokenize(excerpt))
            score = len(matched) / max(1, len(query_terms))
            if score > 0.08:
                seen_excerpts.add(excerpt)
                results.append({
                    "id": row["id"], "source_id": row["source_db"],
                    "title": f"Provenance ({row['source_record']})", "doc_type": row["source_type"],
                    "excerpt": excerpt, "record_type": "graph_provenance", "created_at": row["timestamp"],
                    "score": round(score, 4), "retrieval_mode": "graph_provenance_match", "conflicts": [],
                })
    results.sort(key=lambda item: item["score"], reverse=True)
    results = results[:max(1, min(top_k, 50))]

    document_ids = [item["id"] for item in results if item["record_type"] == "document"]
    conflict_groups = get_document_conflict_groups(conn, document_ids=document_ids, source_id=source_id)
    conflicts_by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for group in conflict_groups:
        for claim in group["claims"]:
            conflicts_by_doc.setdefault(claim["document_id"], []).append(group)
    for item in results:
        if item["record_type"] == "document":
            item["conflicts"] = conflicts_by_doc.get(item["id"], [])
    conn.close()
    return {
        "query": query,
        "retrieval_method": retrieval_method,
        "embeddings_active": embeddings_active,
        "index_mode": "incremental_document_terms",
        "results": results,
    }


def _try_dense_embeddings(query: str, texts: List[str]) -> Optional[List[float]]:
    try:
        resp = requests.post(
            settings.EMBEDDING_ENDPOINT,
            json={"model": settings.EMBEDDING_MODEL, "input": [query] + texts},
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if len(data) == len(texts) + 1:
                vecs = np.array([d["embedding"] for d in data])
                q_vec = vecs[0:1]
                d_vecs = vecs[1:]
                sims = cosine_similarity(q_vec, d_vecs).flatten()
                return sims.tolist()
    except Exception:
        return None
    return None
