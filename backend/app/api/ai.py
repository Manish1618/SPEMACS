from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.schemas.schemas import AIInvestigateRequest, AIInvestigateResponse
from app.services.ai_investigator import ai_investigator
from app.models.entities import AuditLog

router = APIRouter(prefix="/ai", tags=["Universal AI Investigator"])

@router.post("/investigate", response_model=AIInvestigateResponse)
def investigate_query(req: AIInvestigateRequest, db: Session = Depends(get_db)):
    # Record query in audit log
    audit = AuditLog(
        username="investigator",
        action="AI_INVESTIGATOR_QUERY",
        resource_type="CASE",
        resource_id=req.case_id,
        case_id=req.case_id,
        details={"query": req.query}
    )
    db.add(audit)
    db.commit()
    
    response = ai_investigator.investigate(
        db=db,
        case_id=req.case_id,
        query=req.query,
        history=req.history
    )
    return response

@router.get("/hypotheses")
def get_hypotheses(case_id: str = "CASE-2024-8812"):
    return ai_investigator.generate_hypotheses(case_id)
