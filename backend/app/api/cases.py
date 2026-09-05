"""Case management and the investigator dashboard."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import (
    AuditLog,
    Case,
    Document,
    Entity,
    Event,
    Evidence,
    Hypothesis,
    OsintRecord,
)
from app.schemas.schemas import CaseCreate, CaseResponse
from app.services import ledger, retrieval
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/cases", tags=["Case Management"])


def _with_counts(db: Session, case: Case) -> CaseResponse:
    response = CaseResponse.model_validate(case)
    response.document_count = db.query(Document).filter(Document.case_id == case.case_id).count()
    response.evidence_count = db.query(Evidence).filter(Evidence.case_id == case.case_id).count()
    return response


@router.get("", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Only the cases this user is authorised to open."""
    allowed = accessible_cases(db, user)
    cases = db.query(Case).filter(Case.case_id.in_(allowed)).all()
    return [_with_counts(db, c) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    require_case_access(db, user, case_id)
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="No such case.")
    return _with_counts(db, case)


@router.post("", response_model=CaseResponse)
def create_case(
    payload: CaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if db.query(Case).filter(Case.case_id == payload.case_id).first():
        raise HTTPException(status_code=409, detail="That case id already exists.")

    case = Case(
        case_id=payload.case_id,
        title=payload.title,
        description=payload.description,
        classification=payload.classification or "RESTRICTED",
        lead_investigator=user.username,
        assigned_team=[user.username],
    )
    db.add(case)
    db.add(
        AuditLog(
            username=user.username,
            action="CREATE_CASE",
            resource_type="CASE",
            resource_id=payload.case_id,
            case_id=payload.case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={"title": payload.title},
        )
    )
    db.commit()
    db.refresh(case)
    return _with_counts(db, case)


@router.get("/{case_id}/dashboard")
def dashboard(case_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Everything the investigator dashboard needs, computed from the case records."""
    require_case_access(db, user, case_id)
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        raise HTTPException(status_code=404, detail="No such case.")

    ctx = AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )

    summary = (retrieval.summarise_case(db, ctx, case_id=case_id).get("records") or [{}])[0]
    anomalies = retrieval.detect_anomalies(db, ctx, case_id=case_id).get("records", [])
    contradictions = retrieval.find_contradictions(db, ctx, case_id=case_id).get("records", [])
    analytics = retrieval.graph_analytics(db, ctx, case_id=case_id)
    cross_case = [
        r for r in retrieval.find_cross_case_entities(db, ctx).get("records", [])
        if case_id in r["cases"]
    ]
    duplicates = retrieval.find_resolution_candidates(db, ctx, case_id=case_id).get("records", [])

    evidence = db.query(Evidence).filter(Evidence.case_id == case_id).all()
    failing = [e for e in evidence if e.integrity_status != "VERIFIED"]

    hypotheses = db.query(Hypothesis).filter(Hypothesis.case_id == case_id).all()
    recent = (
        db.query(Event)
        .filter(Event.case_id == case_id)
        .order_by(Event.timestamp.desc())
        .limit(10)
        .all()
    )

    return {
        "case": _with_counts(db, case),
        "summary": summary,
        "counts": {
            "entities": db.query(Entity).filter(Entity.case_id == case_id).count(),
            "events": db.query(Event).filter(Event.case_id == case_id).count(),
            "documents": db.query(Document).filter(Document.case_id == case_id).count(),
            "evidence": len(evidence),
            "osint_records": db.query(OsintRecord).filter(OsintRecord.case_id == case_id).count(),
            "anomalies": len(anomalies),
            "contradictions": len(contradictions),
            "cross_case_entities": len(cross_case),
            "duplicate_candidates": len(duplicates),
            "open_hypotheses": sum(1 for h in hypotheses if h.status in ("OPEN", "UNDER_REVIEW")),
        },
        "integrity": {
            "evidence_total": len(evidence),
            "integrity_failures": len(failing),
            "failing_evidence": [
                {"evidence_id": e.evidence_id, "title": e.title, "status": e.integrity_status}
                for e in failing
            ],
            "ledger": ledger.verify_chain(db),
        },
        "anomalies": anomalies[:6],
        "contradictions": contradictions[:6],
        "cross_case_entities": cross_case,
        "duplicate_candidates": duplicates[:4],
        "structurally_central": analytics.get("records", [])[:6],
        "analytics_caveat": analytics.get("caveat", ""),
        "hypotheses": [
            {
                "hypothesis_id": h.hypothesis_id,
                "title": h.title,
                "status": h.status,
            }
            for h in hypotheses
        ],
        "recent_events": [
            {
                "event_id": e.event_id,
                "title": e.title,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "location_name": e.location_name,
                "evidence_id": e.evidence_id,
            }
            for e in recent
        ],
    }
