"""Hypothesis register and the counter-evidence assessment.

A hypothesis is assessed by gathering what supports it and what cuts against it
from the same records, and reporting both. The system does not decide which is
right; it lays out the material and names what is still unknown.
"""

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import AuditLog, Entity, Hypothesis
from app.schemas.schemas import HypothesisCreate, HypothesisOut, HypothesisStatusUpdate
from app.services import retrieval
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/hypotheses", tags=["Hypotheses and Counter-Evidence"])

VALID_STATUSES = {"OPEN", "UNDER_REVIEW", "SUPPORTED", "DISPUTED", "DISMISSED", "RESOLVED"}


def _context(db: Session, user, case_id: Optional[str] = None) -> AccessContext:
    return AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )


@router.get("", response_model=List[HypothesisOut])
def list_hypotheses(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    return db.query(Hypothesis).filter(Hypothesis.case_id.in_(scope)).all()


@router.post("", response_model=HypothesisOut)
def create_hypothesis(
    payload: HypothesisCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_case_access(db, user, payload.case_id)
    hypothesis = Hypothesis(
        hypothesis_id=f"HYP-{uuid.uuid4().hex[:8].upper()}",
        case_id=payload.case_id,
        title=payload.title,
        statement=payload.statement,
        status="OPEN",
        created_by=user.username,
    )
    db.add(hypothesis)
    db.add(
        AuditLog(
            username=user.username,
            action="CREATE_HYPOTHESIS",
            resource_type="HYPOTHESIS",
            resource_id=hypothesis.hypothesis_id,
            case_id=payload.case_id,
            details={"title": payload.title},
        )
    )
    db.commit()
    db.refresh(hypothesis)
    return hypothesis


@router.patch("/{hypothesis_id}", response_model=HypothesisOut)
def update_status(
    hypothesis_id: str,
    payload: HypothesisStatusUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    hypothesis = db.query(Hypothesis).filter(Hypothesis.hypothesis_id == hypothesis_id).first()
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="No such hypothesis.")
    require_case_access(db, user, hypothesis.case_id)

    status = payload.status.upper()
    if status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.",
        )

    previous = hypothesis.status
    hypothesis.status = status
    if payload.notes:
        hypothesis.notes = payload.notes

    db.add(
        AuditLog(
            username=user.username,
            action="UPDATE_HYPOTHESIS_STATUS",
            resource_type="HYPOTHESIS",
            resource_id=hypothesis_id,
            case_id=hypothesis.case_id,
            details={"from": previous, "to": status, "notes": payload.notes},
        )
    )
    db.commit()
    db.refresh(hypothesis)
    return hypothesis


@router.get("/{hypothesis_id}/assessment")
def assess(hypothesis_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Gather supporting material, contradicting material and open unknowns.

    The status is not changed by this call. Weighing the two sides is the
    investigator's decision, and it stays that way.
    """
    hypothesis = db.query(Hypothesis).filter(Hypothesis.hypothesis_id == hypothesis_id).first()
    if hypothesis is None:
        raise HTTPException(status_code=404, detail="No such hypothesis.")
    require_case_access(db, user, hypothesis.case_id)

    ctx = _context(db, user, hypothesis.case_id)
    case_id = hypothesis.case_id

    # Which entities the statement is about, resolved against the register rather
    # than assumed.
    entities = db.query(Entity).filter(Entity.case_id == case_id).all()
    text = f"{hypothesis.title} {hypothesis.statement}"
    subjects = [
        e for e in entities
        if e.label in text or any(alias and alias in text for alias in (e.aliases or []))
    ]
    subject_ids = [e.entity_id for e in subjects]

    supporting = []
    if subject_ids:
        events = retrieval.find_events(db, ctx, entity_ids=subject_ids, case_id=case_id)
        for event in events.get("records", [])[:20]:
            supporting.append(
                {
                    "kind": "record",
                    "reference": event["event_id"],
                    "evidence_id": event.get("evidence_id"),
                    "summary": f"{event['title']} ({event['timestamp'][:16].replace('T', ' ')})",
                    "detail": event.get("summary", ""),
                }
            )

    # Passages in the documents that speak to the statement's own terms.
    terms = [w for w in re.findall(r"[A-Za-z]{5,}", hypothesis.statement)][:8]
    if terms:
        passages = retrieval.search_documents(db, ctx, query=" ".join(terms), case_id=case_id)
        for passage in passages.get("records", [])[:5]:
            supporting.append(
                {
                    "kind": "document passage",
                    "reference": passage["document_id"],
                    "evidence_id": passage.get("evidence_id"),
                    "summary": passage["title"],
                    "detail": passage["passage"][:400],
                }
            )

    contradicting = retrieval.find_contradictions(
        db, ctx, case_id=case_id, **({"entity_ids": subject_ids} if subject_ids else {})
    )
    counter = [
        {
            "kind": item["contradiction_type"],
            "reference": (item.get("asserted_source") or {}).get("document_id"),
            "evidence_id": (item.get("asserted_source") or {}).get("evidence_id"),
            "summary": item["asserted"],
            "detail": item["assessment"],
            "alternative_explanations": item.get("alternative_explanations", []),
        }
        for item in contradicting.get("records", [])
    ]

    summary = retrieval.summarise_case(db, ctx, case_id=case_id)
    unknowns = (summary.get("records") or [{}])[0].get("known_gaps", [])

    return {
        "hypothesis_id": hypothesis_id,
        "title": hypothesis.title,
        "statement": hypothesis.statement,
        "status": hypothesis.status,
        "subjects": [{"entity_id": e.entity_id, "label": e.label} for e in subjects],
        "supporting_evidence": supporting,
        "counter_evidence": counter,
        "unknowns": unknowns,
        "counts": {
            "supporting": len(supporting),
            "contradicting": len(counter),
            "unknowns": len(unknowns),
        },
        "assessment_note": (
            "Supporting and contradicting material are listed as found. The counts are not a "
            "score: a single contradicting record may outweigh many supporting ones, and material "
            "that has not been collected appears on neither side. The status of this hypothesis "
            "is changed only by an investigator."
        ),
    }
