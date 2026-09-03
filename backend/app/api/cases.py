from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.models.database import get_db
from app.models.entities import Case, Document, Evidence, AuditLog
from app.schemas.schemas import CaseResponse, CaseCreate

router = APIRouter(prefix="/cases", tags=["Case Management"])

@router.get("", response_model=List[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).all()
    results = []
    for c in cases:
        c_res = CaseResponse.model_validate(c)
        c_res.document_count = db.query(Document).filter(Document.case_id == c.case_id).count()
        c_res.evidence_count = db.query(Evidence).filter(Evidence.case_id == c.case_id).count()
        results.append(c_res)
    return results

@router.get("/{case_id}", response_model=CaseResponse)
def get_case_by_id(case_id: str, db: Session = Depends(get_db)):
    c = db.query(Case).filter(Case.case_id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    c_res = CaseResponse.model_validate(c)
    c_res.document_count = db.query(Document).filter(Document.case_id == c.case_id).count()
    c_res.evidence_count = db.query(Evidence).filter(Evidence.case_id == c.case_id).count()
    return c_res

@router.post("", response_model=CaseResponse)
def create_case(req: CaseCreate, db: Session = Depends(get_db)):
    existing = db.query(Case).filter(Case.case_id == req.case_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Case ID already exists")
        
    c = Case(
        case_id=req.case_id,
        title=req.title,
        description=req.description,
        classification=req.classification or "RESTRICTED",
        lead_investigator=req.lead_investigator,
        assigned_team=[req.lead_investigator]
    )
    db.add(c)
    
    audit = AuditLog(
        username=req.lead_investigator,
        action="CREATE_CASE",
        resource_type="CASE",
        resource_id=req.case_id,
        case_id=req.case_id,
        details={"title": req.title}
    )
    db.add(audit)
    db.commit()
    db.refresh(c)
    return c
