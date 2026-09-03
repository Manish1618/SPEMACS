from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.models.database import get_db
from app.models.entities import Evidence, CustodyEvent, BlockchainRecord, Document
from app.schemas.schemas import EvidenceResponse, IntegrityVerificationResult
from app.services.evidence import verify_evidence_integrity, calculate_sha256

router = APIRouter(prefix="/evidence", tags=["Evidence & Integrity Engine"])

# Global tamper simulation dict for demo
tampered_mock_cache: Dict[str, bytes] = {}

@router.get("", response_model=List[EvidenceResponse])
def list_evidence(case_id: str = None, db: Session = Depends(get_db)):
    q = db.query(Evidence)
    if case_id:
        q = q.filter(Evidence.case_id == case_id)
    return q.all()

@router.get("/{evidence_id}", response_model=EvidenceResponse)
def get_evidence_detail(evidence_id: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence artifact not found")
    return ev

@router.post("/{evidence_id}/verify", response_model=IntegrityVerificationResult)
def verify_integrity(evidence_id: str, performed_by: str = "investigator_audit", db: Session = Depends(get_db)):
    try:
        tampered_bytes = tampered_mock_cache.get(evidence_id)
        result = verify_evidence_integrity(
            db=db,
            evidence_id=evidence_id,
            current_content_bytes=tampered_bytes,
            performed_by=performed_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{evidence_id}/simulate-tamper")
def simulate_tamper(evidence_id: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
        
    # Introduce 1-byte alteration into the artifact
    corrupted_bytes = f"{ev.title}_TAMPERED_MODIFIED_BYTE_PAYLOAD_0xFF".encode("utf-8")
    tampered_mock_cache[evidence_id] = corrupted_bytes
    
    # Run verification to demonstrate detection
    result = verify_evidence_integrity(
        db=db,
        evidence_id=evidence_id,
        current_content_bytes=corrupted_bytes,
        performed_by="tamper_demonstration_agent"
    )
    
    return {
        "status": "TAMPER_SIMULATED",
        "message": "Injected 1-byte alteration into evidence artifact. Integrity check immediately failed as expected.",
        "verification_result": result
    }

@router.post("/{evidence_id}/restore-clean")
def restore_clean(evidence_id: str, db: Session = Depends(get_db)):
    if evidence_id in tampered_mock_cache:
        del tampered_mock_cache[evidence_id]
        
    result = verify_evidence_integrity(
        db=db,
        evidence_id=evidence_id,
        current_content_bytes=None,
        performed_by="investigator_restore"
    )
    return {
        "status": "RESTORED",
        "message": "Restored original authenticated artifact. Cryptographic SHA-256 integrity restored.",
        "verification_result": result
    }
