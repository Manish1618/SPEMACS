"""Controlled public-source enrichment.

Only material already collected into the authorised public-source register is
served. Nothing here reaches a live external service, attempts to access private
accounts, or bypasses any control. Every record carries its source, reliability,
whether it derives from another report, and whether a human still needs to
confirm the identity match.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import AuditLog, Entity, OsintRecord
from app.services import retrieval
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/osint", tags=["Controlled OSINT Enrichment"])


@router.post("/expand")
def expand(
    case_id: str,
    request: Request,
    entity_id: Optional[str] = None,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_case_access(db, user, case_id)

    if not entity_id and not query:
        raise HTTPException(
            status_code=400, detail="Supply either an entity_id or a search term."
        )

    term = query
    if entity_id and not term:
        entity = db.query(Entity).filter(Entity.entity_id == entity_id).first()
        if entity is None:
            raise HTTPException(status_code=404, detail=f"No entity with id {entity_id}.")
        term = entity.label

    ctx = AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )
    result = retrieval.osint_lookup(db, ctx, query=term, entity_id=entity_id, case_id=case_id)

    db.add(
        AuditLog(
            username=user.username,
            action="OSINT_LOOKUP",
            resource_type="ENTITY",
            resource_id=entity_id,
            case_id=case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={"term": term, "records_returned": len(result.get("records", []))},
        )
    )
    db.commit()

    result["scope_note"] = (
        "Results are drawn from the authorised public-source register held for this case. No "
        "live external collection was performed and no private or access-controlled source was "
        "consulted."
    )
    return result


@router.get("/records")
def records(
    case_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    query = db.query(OsintRecord).filter(OsintRecord.case_id.in_(scope))
    if entity_id:
        query = query.filter(OsintRecord.entity_id == entity_id)

    rows = query.all()
    return {
        "records": [
            {
                "record_id": r.record_id,
                "case_id": r.case_id,
                "entity_id": r.entity_id,
                "source_name": r.source_name,
                "source_url": r.source_url,
                "source_type": r.source_type,
                "published_at": r.published_at,
                "retrieved_at": r.retrieved_at,
                "reliability": r.reliability,
                "confidence": r.confidence,
                "claims": r.claims or [],
                "content_hash": r.content_hash,
                "is_derivative": r.is_derivative,
                "derives_from": r.origin_record_id,
                "requires_human_verification": r.requires_human_verification,
                "evidence_id": r.evidence_id,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/source-independence")
def source_independence(
    case_id: str,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """How many genuinely independent sources sit behind the reports held.

    Outlets carrying the same original filing are one source. Counting mentions
    instead of origins is the mistake this exists to prevent.
    """
    require_case_access(db, user, case_id)

    query = db.query(OsintRecord).filter(OsintRecord.case_id == case_id)
    if entity_id:
        query = query.filter(OsintRecord.entity_id == entity_id)
    rows = query.all()

    if not rows:
        return {
            "case_id": case_id,
            "reports_held": 0,
            "likely_independent_sources": 0,
            "derivative_reports": 0,
            "groups": [],
            "note": "No public-source material is held for this scope.",
        }

    groups = {}
    for record in rows:
        origin = record.origin_record_id or record.record_id
        groups.setdefault(origin, []).append(record)

    lookup = {r.record_id: r for r in rows}
    return {
        "case_id": case_id,
        "reports_held": len(rows),
        "likely_independent_sources": len(groups),
        "derivative_reports": sum(1 for r in rows if r.is_derivative),
        "groups": [
            {
                "origin_record_id": origin,
                "origin_source": (
                    lookup[origin].source_name if origin in lookup else "not held"
                ),
                "origin_type": lookup[origin].source_type if origin in lookup else None,
                "carried_by": [
                    {"record_id": m.record_id, "source_name": m.source_name}
                    for m in members
                    if m.record_id != origin
                ],
                "total_reports": len(members),
            }
            for origin, members in sorted(groups.items())
        ],
        "interpretation": (
            f"{len(rows)} reports are held. They trace back to about {len(groups)} originating "
            "sources. Repetition across outlets is circulation, not corroboration, and should not "
            "raise confidence in the underlying claim."
        ),
    }
