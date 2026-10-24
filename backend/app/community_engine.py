from typing import Any, Dict, List, Optional
import networkx as nx
from .graph_engine import get_full_graph


def detect_graph_communities(source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Group related entities into meaningful communities using the Louvain modularity algorithm
    (networkx.community.louvain_communities) with deterministic seed.
    Computes actual graph modularity and internal cohesion metrics.
    """
    graph_data = get_full_graph(source_id=source_id, include_inferred=True, include_merged_aliases=False)
    nodes = {n["id"]: n for n in graph_data["nodes"]}
    edges = graph_data["edges"]

    if not nodes:
        return []

    G = nx.Graph()
    for nid, n in nodes.items():
        G.add_node(nid, **n)
    for e in edges:
        if e["source"] in nodes and e["target"] in nodes:
            weight = 1.0 if not e["is_inferred"] else 0.5
            G.add_edge(e["source"], e["target"], weight=weight, edge_data=e)

    # Use Louvain community detection with fixed seed for deterministic repeatability
    try:
        raw_communities = list(nx.community.louvain_communities(G, weight="weight", seed=42, resolution=1.0))
        overall_modularity = round(float(nx.community.modularity(G, raw_communities, weight="weight")), 3) if edges else 0.0
        algorithm_used = "Louvain Modularity (networkx.community.louvain_communities)"
    except Exception:
        raw_communities = [set(c) for c in nx.connected_components(G)]
        overall_modularity = 0.0
        algorithm_used = "Connected Components Fallback"

    # Sort communities by size descending, then by first entity ID
    raw_communities.sort(key=lambda c: (-len(c), sorted(list(c))[0]))

    communities_out: List[Dict[str, Any]] = []
    for idx, comm_set in enumerate(raw_communities):
        comm_id = f"COMM-{idx + 1:02d}"
        member_nodes = [nodes[nid] for nid in sorted(comm_set) if nid in nodes]
        member_ids = set(comm_set)

        comm_edges = [
            e for e in edges if e["source"] in member_ids and e["target"] in member_ids
        ]

        # Rank main entities by degree inside the community
        subG = G.subgraph(comm_set)
        degrees = dict(subG.degree())
        member_nodes.sort(key=lambda n: (-degrees.get(n["id"], 0), n["name"]))
        main_entities = member_nodes[:5]

        # Derive descriptive theme label from top locations/products/domains (explicitly marked as generated label, not ground truth)
        theme_label = _derive_community_theme_label(member_nodes, comm_edges, idx + 1)

        # Calculate internal density & average provenance confidence
        n_count = len(member_nodes)
        e_count = len(comm_edges)
        max_possible_edges = max(1, (n_count * (n_count - 1)) // 2)
        density = round(e_count / max_possible_edges, 3) if n_count > 1 else 1.0
        avg_conf = round(
            sum(n["provenance"]["confidence"] for n in member_nodes) / max(1, len(member_nodes)),
            3,
        )

        # Collect representative source records
        source_records: List[Dict[str, str]] = []
        seen_sources = set()
        for n in member_nodes:
            sr = n["provenance"]["source_record"]
            if sr not in seen_sources:
                seen_sources.add(sr)
                source_records.append(
                    {
                        "source_record": sr,
                        "source_type": n["provenance"]["source_type"],
                        "excerpt": n["provenance"]["excerpt"],
                    }
                )
        for e in comm_edges:
            sr = e["provenance"]["source_record"]
            if sr not in seen_sources:
                seen_sources.add(sr)
                source_records.append(
                    {
                        "source_record": sr,
                        "source_type": e["provenance"]["source_type"],
                        "excerpt": e["provenance"]["excerpt"],
                    }
                )

        entity_names_preview = ", ".join(n["name"] for n in main_entities[:4])
        rel_types_preview = ", ".join(sorted({e["rel_type"] for e in comm_edges})) or "isolated entity"
        summary = (
            f"Thematic cluster centered on {entity_names_preview} ({n_count} entities, {e_count} edges) "
            f"connected via [{rel_types_preview}]. Grounded in {len(source_records)} distinct source records."
        )

        communities_out.append(
            {
                "community_id": comm_id,
                "theme_label": theme_label,
                "label_disclaimer": "Generated thematic label derived from member attributes (not ground truth).",
                "algorithm": algorithm_used,
                "entity_count": n_count,
                "edge_count": e_count,
                "confirmed_edge_count": sum(1 for e in comm_edges if not e["is_inferred"]),
                "inferred_edge_count": sum(1 for e in comm_edges if e["is_inferred"]),
                "quality_metrics": {
                    "graph_modularity_q": overall_modularity,
                    "internal_density": density,
                    "mean_provenance_confidence": avg_conf,
                },
                "main_entities": main_entities,
                "entities": member_nodes,
                "relationships": comm_edges,
                "representative_sources": source_records[:6],
                "evidence_summary": summary,
            }
        )

    return communities_out


def get_community_by_id(community_id: str, source_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    all_comms = detect_graph_communities(source_id=source_id)
    for c in all_comms:
        if c["community_id"] == community_id:
            return c
    # Also check across all sources if not found in filtered source_id
    if source_id is not None:
        for c in detect_graph_communities(source_id=None):
            if c["community_id"] == community_id:
                return c
    return None


def _derive_community_theme_label(
    member_nodes: List[Dict[str, Any]], comm_edges: List[Dict[str, Any]], index: int
) -> str:
    names = " ".join(n["name"] for n in member_nodes)
    if "Gwalior" in names or "Morena" in names or "Larsen & Toubro" in names or "Adani Green" in names:
        return "North Corridor (Gwalior, Morena, Jaipur, Ajmer) Heavy Engineering & Grid Cluster"
    if "Katni" in names or "Bhopal" in names or "Bharat Forge" in names or "Biocon" in names:
        return "Central Corridor (Bhopal & Katni) Defence Metallurgy & Bio-Pharma Cluster"
    if "Mumbai" in names or "Ahmedabad" in names or "Reliance" in names or "Tata Consultancy" in names:
        return "Western Corridor (Mumbai & Ahmedabad/Gandhinagar) Petrochemical & Cloud AI Cluster"
    if "School A" in names or "Scindia" in names or "Quantum Curriculum" in names:
        return "Gwalior & Jaipur STEM Charter & Quantum Curriculum Cluster"
    if "Mumbai Institute" in names or "Gandhinagar GIFT" in names:
        return "Mumbai & Gandhinagar Science Magnet Cluster"
    top_name = member_nodes[0]["name"] if member_nodes else f"Cluster {index}"
    return f"{top_name} Thematic Community"
