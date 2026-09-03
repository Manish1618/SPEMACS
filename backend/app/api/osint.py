from fastapi import APIRouter
from typing import List, Dict, Any
from app.schemas.schemas import OSINTEvaluationRequest, OSINTExtractedRecord
from app.services.osint import perform_osint_expansion

router = APIRouter(prefix="/osint", tags=["Controlled OSINT Engine"])

@router.post("/expand", response_model=List[OSINTExtractedRecord])
def expand_entity_osint(req: OSINTEvaluationRequest):
    return perform_osint_expansion(
        entity_name=req.entity_name,
        entity_type=req.entity_type,
        case_id=req.case_id
    )
