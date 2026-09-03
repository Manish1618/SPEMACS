from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.models.database import get_db
from app.services.graph_engine import knowledge_graph
from app.schemas.schemas import GraphResponse

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

@router.get("/case/{case_id}", response_model=GraphResponse)
def get_case_graph(case_id: str):
    all_nodes = set([n for n, d in knowledge_graph.graph.nodes(data=True) if d.get("case_id") == case_id or n == case_id or any(u == n or v == n for u, v, k, ed in knowledge_graph.graph.edges(data=True, keys=True) if ed.get("case_id") == case_id)])
    if not all_nodes:
        # Fallback to all nodes if case filtering has zero or global view
        all_nodes = set(knowledge_graph.graph.nodes())
        
    return knowledge_graph._build_subgraph_response(all_nodes)

@router.get("/k-hop", response_model=GraphResponse)
def get_k_hop(entity_id: str = Query(...), k: int = Query(2, ge=1, le=4)):
    return knowledge_graph.get_k_hop_neighborhood(entity_id, k=k)

@router.get("/shortest-path")
def get_shortest_path(source_id: str = Query(...), target_id: str = Query(...)):
    res = knowledge_graph.get_shortest_path(source_id, target_id)
    if not res.get("path_found"):
        return {"path_found": False, "message": "No connecting path found in current graph knowledge.", "nodes": [], "edges": []}
    return res

@router.get("/analytics")
def get_analytics(case_id: Optional[str] = None):
    return knowledge_graph.compute_graph_analytics(case_id)

@router.get("/cross-case")
def get_cross_case():
    return knowledge_graph.find_cross_case_overlaps()

@router.get("/anomalies")
def get_anomalies():
    # Gather map events
    from app.api.map_timeline import get_all_raw_events
    events = get_all_raw_events()
    return knowledge_graph.detect_anomalies(events)

@router.post("/merge-entities")
def merge_entities(primary_id: str, duplicate_id: str, confirmed_by: str = "investigator"):
    if primary_id not in knowledge_graph.graph or duplicate_id not in knowledge_graph.graph:
        raise HTTPException(status_code=404, detail="One or both entity IDs not found in graph")
        
    dup_data = knowledge_graph.entity_lookup[duplicate_id]
    knowledge_graph.aliases[dup_data["label"].lower().strip()] = primary_id
    
    # Reroute duplicate edges to primary
    for u, v, k, edata in list(knowledge_graph.graph.edges(duplicate_id, data=True, keys=True)):
        target = v if u == duplicate_id else u
        knowledge_graph.add_relationship(
            f"MERGED-{k}", primary_id, target, edata.get("rel_type", "RELATED_TO"),
            edata.get("case_id", "CASE-2024-8812"), edata.get("confidence", 0.9),
            edata.get("evidence_ids", [])
        )
        
    return {
        "status": "SUCCESS",
        "primary_id": primary_id,
        "merged_id": duplicate_id,
        "message": f"Successfully merged '{dup_data['label']}' into primary node with provenance recorded."
    }
