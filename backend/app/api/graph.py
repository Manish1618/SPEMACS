"""Knowledge graph endpoints, projected from the persisted entity and relationship stores."""

from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import AuditLog, Entity, Relationship
from app.schemas.schemas import EntityOut, GraphResponse
from app.services import retrieval
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


def _context(db: Session, user, case_id: Optional[str] = None) -> AccessContext:
    return AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )


def _project(db: Session, entities: List[Entity], relationships: List[Relationship], analytics: dict) -> dict:
    scores = {r["entity_id"]: r for r in analytics.get("records", [])}
    known = {e.entity_id for e in entities}
    return {
        "nodes": [
            {
                "id": e.entity_id,
                "label": e.label,
                "entity_type": e.entity_type,
                "properties": {
                    **(e.properties or {}),
                    "aliases": e.aliases or [],
                    **({"latitude": e.latitude, "longitude": e.longitude} if e.latitude else {}),
                },
                "is_hub": scores.get(e.entity_id, {}).get("degree_centrality", 0) > 0.15,
                "is_bridge": scores.get(e.entity_id, {}).get("is_articulation_point", False),
                "centrality_score": scores.get(e.entity_id, {}).get("degree_centrality", 0.0),
                "community_id": scores.get(e.entity_id, {}).get("community_id", 0),
            }
            for e in entities
        ],
        "edges": [
            {
                "id": r.rel_id,
                "source": r.source_id,
                "target": r.target_id,
                "label": r.rel_type,
                "relationship_type": r.rel_type,
                "confidence": r.confidence or 1.0,
                "evidence_ids": r.evidence_ids or [],
                "properties": {
                    **(r.properties or {}),
                    "assertion_kind": r.assertion_kind,
                    "first_recorded": r.valid_from.isoformat() if r.valid_from else None,
                },
            }
            for r in relationships
            if r.source_id in known and r.target_id in known
        ],
        "stats": {
            "total_nodes": len(entities),
            "total_edges": len([r for r in relationships if r.source_id in known and r.target_id in known]),
            "hubs_count": sum(1 for e in entities if scores.get(e.entity_id, {}).get("degree_centrality", 0) > 0.15),
            "bridges_count": sum(1 for e in entities if scores.get(e.entity_id, {}).get("is_articulation_point")),
            "density": analytics.get("summary", {}).get("density"),
            "communities": analytics.get("summary", {}).get("community_count"),
        },
    }


@router.get("/case/{case_id}", response_model=GraphResponse)
def case_graph(case_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_case_access(db, user, case_id)
    ctx = _context(db, user, case_id)

    entities = db.query(Entity).filter(Entity.case_id == case_id).all()
    relationships = db.query(Relationship).filter(Relationship.case_id == case_id).all()

    # Pull in counterparties held under another case so cross-case edges resolve.
    referenced = {r.source_id for r in relationships} | {r.target_id for r in relationships}
    missing = referenced - {e.entity_id for e in entities}
    if missing:
        extra = (
            db.query(Entity)
            .filter(Entity.entity_id.in_(missing), Entity.case_id.in_(ctx.allowed_cases))
            .all()
        )
        entities = entities + extra

    analytics = retrieval.graph_analytics(db, ctx, case_id=case_id)
    return _project(db, entities, relationships, analytics)


@router.get("/k-hop", response_model=GraphResponse)
def k_hop(
    entity_id: str = Query(...),
    k: int = Query(2, ge=1, le=4),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ctx = _context(db, user)
    result = retrieval.get_neighborhood(db, ctx, entity_id=entity_id, hops=k)
    if not result.get("records"):
        raise HTTPException(status_code=404, detail=result.get("note", "Entity not found."))

    node_ids = [n["entity_id"] for n in result["records"][0]["nodes"]]
    rel_ids = [e["rel_id"] for e in result["records"][0]["edges"]]
    entities = db.query(Entity).filter(Entity.entity_id.in_(node_ids)).all()
    relationships = db.query(Relationship).filter(Relationship.rel_id.in_(rel_ids)).all()
    analytics = retrieval.graph_analytics(db, ctx)
    return _project(db, entities, relationships, analytics)


@router.get("/shortest-path")
def shortest_path(
    source_id: str = Query(...),
    target_id: str = Query(...),
    max_hops: int = Query(5, ge=1, le=8),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ctx = _context(db, user)
    result = retrieval.find_paths(
        db, ctx, source_id=source_id, target_id=target_id, max_hops=max_hops
    )
    paths = result.get("records") or []
    if not paths:
        return {"path_found": False, "message": result.get("note", ""), "paths": [], "nodes": [], "edges": []}

    node_ids, rel_ids = set(), []
    for path in paths:
        for link in path["links"]:
            node_ids.add(link["source_id"])
            node_ids.add(link["target_id"])
            rel_ids.append(link["rel_id"])

    entities = db.query(Entity).filter(Entity.entity_id.in_(node_ids)).all()
    relationships = db.query(Relationship).filter(Relationship.rel_id.in_(rel_ids)).all()
    projected = _project(db, entities, relationships, retrieval.graph_analytics(db, ctx))
    projected["path_found"] = True
    projected["paths"] = paths
    return projected


@router.get("/analytics")
def analytics(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return retrieval.graph_analytics(db, _context(db, user, case_id), case_id=case_id)


@router.get("/cross-case")
def cross_case(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return retrieval.find_cross_case_entities(db, _context(db, user))


@router.get("/anomalies")
def anomalies(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return retrieval.detect_anomalies(db, _context(db, user, case_id), case_id=case_id)


@router.get("/entities", response_model=List[EntityOut])
def list_entities(
    case_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    query = db.query(Entity).filter(Entity.case_id.in_(scope))
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type.upper())
    rows = query.order_by(Entity.entity_type, Entity.label).all()
    if search:
        needle = search.lower()
        rows = [r for r in rows if needle in r.label.lower()]
    return rows


@router.get("/entity/{entity_id}")
def entity_profile(entity_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = retrieval.get_entity_profile(db, _context(db, user), entity_id)
    if not result.get("records"):
        raise HTTPException(status_code=404, detail=result.get("note") or result.get("authorisation", "Not found."))
    return result["records"][0]


@router.get("/resolution-candidates")
def resolution_candidates(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return retrieval.find_resolution_candidates(db, _context(db, user, case_id), case_id=case_id)


@router.post("/merge-entities")
def merge_entities(
    primary_id: str = Body(...),
    duplicate_id: str = Body(...),
    justification: str = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Merge a confirmed duplicate into its canonical record.

    An investigator must supply a justification. A merge asserts that two records
    describe one subject; done wrongly it manufactures connections that were never
    in the data, so the action is recorded with who authorised it and why, and the
    duplicate is retained rather than deleted.
    """
    primary = db.query(Entity).filter(Entity.entity_id == primary_id).first()
    duplicate = db.query(Entity).filter(Entity.entity_id == duplicate_id).first()
    if primary is None or duplicate is None:
        raise HTTPException(status_code=404, detail="One or both entities do not exist.")
    if primary_id == duplicate_id:
        raise HTTPException(status_code=400, detail="An entity cannot be merged into itself.")

    require_case_access(db, user, primary.case_id)
    require_case_access(db, user, duplicate.case_id)

    if not justification.strip():
        raise HTTPException(
            status_code=400, detail="A justification is required to record a merge."
        )

    moved = 0
    for rel in db.query(Relationship).filter(
        (Relationship.source_id == duplicate_id) | (Relationship.target_id == duplicate_id)
    ).all():
        if rel.source_id == duplicate_id:
            rel.source_id = primary_id
        if rel.target_id == duplicate_id:
            rel.target_id = primary_id
        moved += 1

    merged_aliases = sorted(
        set(primary.aliases or []) | set(duplicate.aliases or []) | {duplicate.label}
        - {primary.label}
    )
    primary.aliases = merged_aliases
    duplicate.canonical_id = primary_id
    duplicate.merged_by = user.username
    duplicate.merge_confidence = 1.0

    db.add(
        AuditLog(
            username=user.username,
            action="MERGE_ENTITIES",
            resource_type="ENTITY",
            resource_id=primary_id,
            case_id=primary.case_id,
            details={
                "merged_from": duplicate_id,
                "justification": justification,
                "relationships_moved": moved,
            },
        )
    )
    db.commit()

    from app.services.ingestion import rebuild_graph

    rebuild_graph(db)

    return {
        "status": "merged",
        "primary_id": primary_id,
        "merged_id": duplicate_id,
        "relationships_moved": moved,
        "aliases": merged_aliases,
        "message": (
            f"{duplicate.label} ({duplicate_id}) is now recorded as an alias of {primary.label}. "
            "The duplicate record is retained and the merge is logged with your justification, so "
            "it can be reviewed or reversed."
        ),
    }
