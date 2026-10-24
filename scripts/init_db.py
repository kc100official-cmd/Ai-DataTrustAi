"""Initialize or reset sample SQLite databases and Knowledge Graph store for DataTrust AI."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.sample_data import ensure_sample_databases
from backend.app.database import list_data_sources
from backend.app.graph_engine import get_full_graph


def main() -> None:
    print("Initializing DataTrust AI sample databases and persistent Knowledge Graph...")
    ensure_sample_databases()
    sources = list_data_sources()
    graph = get_full_graph()
    print(f"Connected SQLite Sources ({len(sources)}):")
    for s in sources:
        print(
            f"  - {s['source_id']} ({s['source_name']}): {s['table_count']} tables, {s['total_rows']} rows [{s['status']}]"
        )
    print(
        f"Knowledge Graph Ready: {graph['total_nodes']} entities, "
        f"{graph['confirmed_edge_count']} confirmed edges, "
        f"{graph['inferred_edge_count']} inferred edges."
    )


if __name__ == "__main__":
    main()
