from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.schemas.schemas import AIInvestigateRequest, AIInvestigateResponse
from app.services.ai_investigator import ai_investigator
from app.services.retrieval import AccessContext
from app.models.entities import AuditLog


def _context(db: Session, user, case_id: str) -> AccessContext:
    """The caller's real authorisation, so answers cannot reach unreadable cases."""
    return AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=case_id,
    )

router = APIRouter(prefix="/ai", tags=["Universal AI Investigator"])

@router.post("/investigate", response_model=AIInvestigateResponse)
def investigate_query(
    req: AIInvestigateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_case_access(db, user, req.case_id)

    # Record query in audit log. The detail level is logged too, so a reviewer can
    # tell whether an answer was a focused reply or a full record-set disclosure.
    audit = AuditLog(
        username=user.username,
        action="AI_INVESTIGATOR_QUERY",
        resource_type="CASE",
        resource_id=req.case_id,
        case_id=req.case_id,
        details={"query": req.query, "detail_level": req.detail_level}
    )
    db.add(audit)
    db.commit()

    response = ai_investigator.investigate(
        db=db,
        case_id=req.case_id,
        query=req.query,
        history=req.history,
        detail_level=req.detail_level,
        ctx=_context(db, user, req.case_id),
    )
    return response

@router.get("/hypotheses")
def get_hypotheses(case_id: str = "CASE-2024-8812"):
    return ai_investigator.generate_hypotheses(case_id)

@router.get("/full-brief")
def get_full_brief(
    case_id: str = "CASE-2024-8812",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """The complete case dossier without asking a question first.

    Same payload the chat renders in full-detail mode, so the brief can also be
    pulled directly for export or a second view.
    """
    require_case_access(db, user, case_id)
    brief = ai_investigator.full_brief(db=db, case_id=case_id)
    db.add(
        AuditLog(
            username=user.username,
            action="AI_FULL_BRIEF",
            resource_type="CASE",
            resource_id=case_id,
            case_id=case_id,
            details={"sections": brief["stats"]["sections"]},
        )
    )
    db.commit()
    return brief

@router.get("/entity-dossier")
def get_entity_dossier(
    entity_id: str,
    case_id: str = "CASE-2024-8812",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Everything on file about one subject: profile, links, activity, evidence, OSINT."""
    require_case_access(db, user, case_id)
    dossier = ai_investigator.entity_dossier(db=db, case_id=case_id, entity_id=entity_id)
    if dossier is None:
        raise HTTPException(status_code=404, detail=f"No entity {entity_id} in case {case_id}")
    return dossier
