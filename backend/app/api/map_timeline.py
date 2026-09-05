"""Map, timeline and replay endpoints.

Events were previously a Python list literal in this module. They are read from
the event store now, so filters are real queries and uploaded data appears here
without a code change.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import Entity, Event
from app.schemas.schemas import MapEventFeature, TimelineEvent

router = APIRouter(prefix="/workspace", tags=["Map, Timeline and Replay"])


def _query_events(
    db: Session,
    allowed: List[str],
    case_id: Optional[str],
    entity_id: Optional[str],
    event_types: Optional[List[str]],
    start: Optional[datetime],
    end: Optional[datetime],
    min_confidence: Optional[float],
) -> List[Event]:
    scope = [case_id] if case_id else allowed
    scope = [c for c in scope if c in allowed]
    if not scope:
        return []

    query = db.query(Event).filter(Event.case_id.in_(scope))
    if start:
        query = query.filter(Event.timestamp >= start)
    if end:
        query = query.filter(Event.timestamp <= end)
    if event_types:
        query = query.filter(Event.event_type.in_([t.upper() for t in event_types]))
    if min_confidence is not None:
        query = query.filter(Event.confidence >= min_confidence)

    rows = query.order_by(Event.timestamp.asc()).all()
    if entity_id:
        rows = [r for r in rows if entity_id in (r.related_entities or [])]
    return rows


def _parse(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Not a valid ISO 8601 timestamp: {value}")
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


@router.get("/map-events", response_model=List[MapEventFeature])
def map_events(
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    event_types: Optional[List[str]] = Query(None),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_confidence: Optional[float] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    rows = _query_events(
        db, allowed, case_id, entity_id, event_types,
        _parse(start_date), _parse(end_date), min_confidence,
    )
    return [
        MapEventFeature(
            event_id=e.event_id,
            case_id=e.case_id,
            title=e.title,
            event_type=e.event_type,
            latitude=e.latitude,
            longitude=e.longitude,
            location_name=e.location_name or "",
            timestamp=e.timestamp,
            related_entities=e.related_entities or [],
            evidence_id=e.evidence_id,
            confidence=e.confidence or 1.0,
        )
        for e in rows
        if e.latitude is not None and e.longitude is not None
    ]


@router.get("/timeline", response_model=List[TimelineEvent])
def timeline(
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    event_types: Optional[List[str]] = Query(None),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    rows = _query_events(
        db, allowed, case_id, entity_id, event_types,
        _parse(start_date), _parse(end_date), None,
    )
    return [
        TimelineEvent(
            id=e.event_id,
            case_id=e.case_id,
            title=e.title,
            event_type=e.event_type,
            start_time=e.timestamp,
            location_name=e.location_name,
            latitude=e.latitude,
            longitude=e.longitude,
            related_entities=e.related_entities or [],
            evidence_id=e.evidence_id,
            summary=e.summary or "",
            confidence=e.confidence or 1.0,
        )
        for e in rows
    ]


@router.get("/time-bounds")
def time_bounds(
    case_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Extent of the recorded activity, for the time slider's range."""
    require_case_access(db, user, case_id)
    rows = db.query(Event).filter(Event.case_id == case_id).order_by(Event.timestamp.asc()).all()
    if not rows:
        return {"case_id": case_id, "first": None, "last": None, "event_count": 0}
    return {
        "case_id": case_id,
        "first": rows[0].timestamp,
        "last": rows[-1].timestamp,
        "event_count": len(rows),
    }


@router.get("/replay")
def replay(
    case_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Chronological reconstruction of the case.

    Each frame carries the entities that had appeared by that point and the
    relationships recorded by then, so the graph, map and timeline can be replayed
    together as the investigation unfolds.
    """
    require_case_access(db, user, case_id)

    from app.models.entities import Relationship

    events = _query_events(
        db, accessible_cases(db, user), case_id, None, None,
        _parse(start_date), _parse(end_date), None,
    )
    if not events:
        return {"case_id": case_id, "frames": [], "note": "No events recorded for this case."}

    relationships = (
        db.query(Relationship)
        .filter(Relationship.case_id == case_id)
        .order_by(Relationship.valid_from.asc())
        .all()
    )
    labels = {
        e.entity_id: e.label
        for e in db.query(Entity).filter(Entity.case_id.in_(accessible_cases(db, user))).all()
    }

    frames = []
    seen_entities: set = set()
    for index, event in enumerate(events):
        newly = [
            eid for eid in (event.related_entities or []) if eid not in seen_entities
        ]
        seen_entities.update(event.related_entities or [])

        known_relationships = [
            r.rel_id
            for r in relationships
            if r.valid_from is not None and r.valid_from <= event.timestamp
        ]

        frames.append(
            {
                "frame": index,
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "title": event.title,
                "event_type": event.event_type,
                "summary": event.summary,
                "location_name": event.location_name,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "evidence_id": event.evidence_id,
                "entities_present": sorted(seen_entities),
                "entities_new_this_frame": newly,
                "new_entity_labels": [labels.get(e, e) for e in newly],
                "relationship_count": len(known_relationships),
                "related_entities": event.related_entities or [],
            }
        )

    return {
        "case_id": case_id,
        "frame_count": len(frames),
        "first": frames[0]["timestamp"],
        "last": frames[-1]["timestamp"],
        "frames": frames,
    }


@router.get("/network-at")
def network_at(
    case_id: str,
    at: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """The network as the records stood at a point in time.

    Only relationships already recorded by that moment are included, so moving the
    time control shows the network as it was then rather than the network as it is
    now filtered by date.
    """
    require_case_access(db, user, case_id)

    from app.models.entities import Relationship

    cutoff = _parse(at)
    if cutoff is None:
        raise HTTPException(status_code=400, detail="Parameter 'at' is required.")

    relationships = [
        r
        for r in db.query(Relationship).filter(Relationship.case_id == case_id).all()
        if r.valid_from is not None and r.valid_from <= cutoff
    ]
    active_ids = {r.source_id for r in relationships} | {r.target_id for r in relationships}
    entities = (
        db.query(Entity).filter(Entity.entity_id.in_(active_ids)).all() if active_ids else []
    )

    return {
        "case_id": case_id,
        "as_of": cutoff,
        "nodes": [
            {
                "id": e.entity_id,
                "label": e.label,
                "entity_type": e.entity_type,
                "properties": e.properties or {},
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
                "confidence": r.confidence,
                "evidence_ids": r.evidence_ids or [],
                "first_recorded": r.valid_from,
            }
            for r in relationships
        ],
        "stats": {"total_nodes": len(entities), "total_edges": len(relationships)},
    }
