import sqlite3
from typing import Any, Dict, List, Optional
import numpy as np
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .config import settings
from .sample_data import ensure_sample_databases, get_graph_db_path


def search_documents_and_excerpts(
    query: str,
    source_id: Optional[str] = None,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Retrieve relevant documents and provenance excerpts.
    Uses configured dense embeddings when enabled & reachable; otherwise transparently
    uses TF-IDF lexical/n-gram cosine similarity fallback.
    """
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
    conn.close()

    corpus: List[Dict[str, Any]] = []
    for d in doc_rows:
        corpus.append(
            {
                "id": d["id"],
                "source_id": d["source_id"],
                "title": d["title"],
                "doc_type": d["doc_type"],
                "excerpt": d["content"],
                "record_type": "document",
                "created_at": d["created_at"],
            }
        )

    seen_excerpts = {c["excerpt"] for c in corpus}
    for r in rel_rows:
        ex = r["excerpt"]
        if ex not in seen_excerpts:
            seen_excerpts.add(ex)
            corpus.append(
                {
                    "id": r["id"],
                    "source_id": r["source_db"],
                    "title": f"Provenance ({r['source_record']})",
                    "doc_type": r["source_type"],
                    "excerpt": ex,
                    "record_type": "graph_provenance",
                    "created_at": r["timestamp"],
                }
            )

    if not corpus or not query.strip():
        return {
            "query": query,
            "retrieval_method": "tfidf_lexical_fallback",
            "embeddings_active": False,
            "results": [],
        }

    texts = [f"{item['title']} {item['excerpt']}" for item in corpus]

    # Try dense embeddings if configured
    if settings.EMBEDDINGS_ENABLED and settings.EMBEDDING_ENDPOINT:
        dense_scores = _try_dense_embeddings(query, texts)
        if dense_scores is not None:
            ranked = sorted(
                zip(corpus, dense_scores), key=lambda x: x[1], reverse=True
            )[:top_k]
            return {
                "query": query,
                "retrieval_method": f"dense_embeddings ({settings.EMBEDDING_MODEL})",
                "embeddings_active": True,
                "results": [
                    {**item, "score": round(float(sc), 4)}
                    for item, sc in ranked
                    if sc > 0.05
                ],
            }

    # Deterministic TF-IDF lexical & bi-gram fallback
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    tfidf_matrix = vectorizer.fit_transform(texts + [query])
    query_vec = tfidf_matrix[-1]
    doc_vecs = tfidf_matrix[:-1]
    sims = cosine_similarity(query_vec, doc_vecs).flatten()

    ranked_items = sorted(zip(corpus, sims), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for item, score in ranked_items:
        if score > 0.01:
            results.append(
                {
                    **item,
                    "score": round(float(score), 4),
                    "retrieval_mode": "tfidf_lexical_fallback",
                }
            )

    return {
        "query": query,
        "retrieval_method": "tfidf_lexical_fallback",
        "embeddings_active": False,
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
