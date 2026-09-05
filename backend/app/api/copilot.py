"""Copilot endpoints.

/copilot/query is the single entry point for investigator questions. It accepts
any question in free text; there is no menu of supported forms.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.security import accessible_cases, get_current_user, require_case_access
from app.models.database import get_db
from app.models.entities import AuditLog
from app.schemas.schemas import CopilotQueryRequest, CopilotResponse
from app.services import retrieval
from app.services.planner import copilot, sessions
from app.services.retrieval import AccessContext

router = APIRouter(prefix="/copilot", tags=["Investigation Copilot"])


@router.post("/query", response_model=CopilotResponse)
def query(
    payload: CopilotQueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    require_case_access(db, user, payload.case_id)

    ctx = AccessContext(
        username=user.username,
        role=user.role,
        allowed_cases=accessible_cases(db, user),
        active_case_id=payload.case_id,
    )

    result = copilot.answer(
        db=db,
        ctx=ctx,
        question=payload.question,
        case_id=payload.case_id,
        conversation_id=payload.conversation_id or f"{user.username}:{payload.case_id}",
    )

    # The plan is recorded, not just the question, so a reviewer can see which
    # sources an answer was built from.
    db.add(
        AuditLog(
            username=user.username,
            action="COPILOT_QUERY",
            resource_type="CASE",
            resource_id=payload.case_id,
            case_id=payload.case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={
                "question": payload.question,
                "planner": result.get("planner"),
                "confidence": result.get("confidence"),
                "tools_called": [step["tool"] for step in result.get("query_plan", [])],
                "citations": [c.get("evidence_id") for c in result.get("citations", [])],
            },
        )
    )
    db.commit()

    return result


@router.post("/reset")
def reset_conversation(
    conversation_id: str,
    user=Depends(get_current_user),
):
    """Forget the carried context so the next question starts clean."""
    sessions.reset(conversation_id)
    return {"status": "reset", "conversation_id": conversation_id}


@router.get("/tools")
def list_tools(user=Depends(get_current_user)):
    """The planner's action space, for transparency about what the Copilot can reach."""
    return {
        "tools": [
            {
                "name": spec.name,
                "description": spec.description,
                "parameters": sorted(spec.parameters.get("properties", {})),
            }
            for spec in retrieval.TOOLS.values()
        ],
        "note": (
            "The Copilot selects from these per question. Questions are not matched against a "
            "fixed list of supported forms."
        ),
    }
