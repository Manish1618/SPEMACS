"""Cross-Case Intelligence endpoints.

Every route resolves the caller's authorised case list first and passes it to the
engine as the outer boundary of the search. A case the caller cannot open is
never read and never named.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import AuditLog
from app.services.cross_case import NOT_A_FINDING, cross_case_engine
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/cross-case", tags=["Cross-Case Intelligence"])


def _context(db: Session, user, case_id: Optional[str] = None) -> AccessContext:
    return AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )


@router.get("/analyse")
def analyse(
    request: Request,
    case_id: str = Query(..., description="The active investigation to compare outward from."),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    basis: Optional[List[str]] = Query(
        None, description="Restrict to particular detection bases, e.g. SHARED_ENTITY."
    ),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Relationships between this investigation and every other one in scope."""
    require_case_access(db, user, case_id)
    ctx = _context(db, user, case_id)

    result = cross_case_engine.analyse(
        db, ctx, case_id, min_confidence=min_confidence, bases=basis
    )

    # Cross-case retrieval widens what one investigator can see, so the run is
    # logged with its scope and what it surfaced.
    db.add(
        AuditLog(
            username=user.username,
            action="CROSS_CASE_ANALYSIS",
            resource_type="CASE",
            resource_id=case_id,
            case_id=case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={
                "cases_in_scope": result.get("authorisation", {}).get("cases_in_scope", []),
                "link_count": result.get("summary", {}).get("link_count", 0),
                "related_cases": [c["case_id"] for c in result.get("related_cases", [])],
                "by_basis": result.get("summary", {}).get("by_basis", {}),
                "min_confidence": min_confidence,
            },
        )
    )
    db.commit()
    return result


@router.get("/link/{link_id}")
def link_detail(
    link_id: str,
    case_id: str = Query(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """One link in full, for opening in the synchronized graph, map and timeline."""
    require_case_access(db, user, case_id)
    ctx = _context(db, user, case_id)

    result = cross_case_engine.analyse(db, ctx, case_id)
    for link in result.get("links", []):
        if link["link_id"] == link_id:
            return link
    raise HTTPException(
        status_code=404,
        detail=(
            f"No cross-case link {link_id} is currently detected for {case_id} within your "
            "authorised scope."
        ),
    )


@router.get("/bases")
def detection_bases():
    """What the engine looks for, and how far each signal can be trusted."""
    return {
        "bases": [
            {
                "basis": "CROSS_CASE_RELATIONSHIP",
                "label": "Recorded relationship spanning two files",
                "strength": "Direct. Rests on a relationship row and its cited evidence.",
            },
            {
                "basis": "SHARED_ENTITY",
                "label": "Same entity record in both files",
                "strength": "Direct. One record referenced by two investigations.",
            },
            {
                "basis": "SHARED_ARTIFACT",
                "label": "One evidence artifact cited by both files",
                "strength": "Direct documentary overlap.",
            },
            {
                "basis": "IDENTIFIER_MATCH",
                "label": "Same issued identifier on records in both files",
                "strength": "Strong but not conclusive; identifiers are mis-keyed and reused.",
            },
            {
                "basis": "ALIAS_MATCH",
                "label": "Matching name or alias across files",
                "strength": "Weak. A name collision until verified against an identifier.",
            },
            {
                "basis": "MULTI_HOP_PATH",
                "label": "Network path between files",
                "strength": "Indirect. Describes record structure, not acquaintance.",
            },
            {
                "basis": "SHARED_LOCATION",
                "label": "Same place recorded in both files",
                "strength": "Very weak. Public places serve unconnected people.",
            },
            {
                "basis": "TEMPORAL_PATTERN",
                "label": "Activity in both files inside one window",
                "strength": "Very weak. Correlation only; window size is an analytical choice.",
            },
        ],
        "caveat": NOT_A_FINDING,
        "note": (
            "No basis, at any confidence, supports an inference of criminality. A cross-case "
            "link identifies records worth reading together."
        ),
    }
