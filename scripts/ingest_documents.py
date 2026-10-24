"""Import a JSON document list through DataTrust's incremental batch endpoint."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", type=Path, help="JSON array, or {\"documents\": [...]} containing title and text fields")
    parser.add_argument("--source-id", default="enterprise_supply_ops")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()

    raw: Any = json.loads(args.json_file.read_text(encoding="utf-8"))
    documents: List[Dict[str, str]] = raw.get("documents", []) if isinstance(raw, dict) else raw
    if not isinstance(documents, list) or not documents:
        raise SystemExit("The JSON file must contain a non-empty document array.")
    normalized = []
    for index, item in enumerate(documents):
        if not isinstance(item, dict) or not item.get("title") or not item.get("text"):
            raise SystemExit(f"Document {index} must have non-empty title and text fields.")
        normalized.append({
            "source_id": item.get("source_id", args.source_id),
            "document_id": item.get("document_id"),
            "title": str(item["title"]),
            "doc_type": str(item.get("doc_type", "audit_memo")),
            "text": str(item["text"]),
        })

    response = requests.post(
        f"{args.base_url.rstrip('/')}/api/graph/ingest/batch",
        json={"documents": normalized},
        timeout=300,
    )
    response.raise_for_status()
    result = response.json()
    print(json.dumps({
        "documents_requested": result["documents_requested"],
        "documents_processed": result["documents_processed"],
        "documents_created": result["documents_created"],
        "documents_updated": result["documents_updated"],
        "failed_count": result["failed_count"],
        "ignored_instruction_count": result["ignored_instruction_count"],
        "ingestion_time_ms": result["ingestion_time_ms"],
        "graph_size": result["graph_size"],
        "errors": result["errors"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
