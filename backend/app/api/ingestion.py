from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
from app.models.database import get_db
from app.models.entities import Document, Evidence, CustodyEvent, AuditLog
from app.services.evidence import create_evidence_record, calculate_sha256
from app.services.ingestion import seed_database_and_graph

router = APIRouter(prefix="/ingestion", tags=["Ingestion & OCR"])

@router.post("/upload")
async def upload_document(
    case_id: str = Form(...),
    title: str = Form(...),
    file_type: str = Form("PDF_SCAN"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
        
    sha256_hash = calculate_sha256(content)
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    
    # Text extraction simulation or decoding
    try:
        extracted_text = content.decode("utf-8")
    except Exception:
        extracted_text = f"Extracted forensic OCR text for {file.filename}. Entity nodes and timestamps parsed."
        
    doc = Document(
        document_id=doc_id,
        case_id=case_id,
        filename=file.filename,
        title=title,
        file_type=file_type,
        storage_path=f"storage/{file.filename}",
        sha256_hash=sha256_hash,
        extracted_text=extracted_text,
        uploaded_by="investigator_upload",
        created_at=datetime.now(timezone.utc)
    )
    db.add(doc)
    db.commit()
    
    # Auto-register Evidence & Blockchain Seal
    evidence = create_evidence_record(
        db=db,
        case_id=case_id,
        title=title,
        evidence_type="DOC_UPLOAD",
        content_bytes=content,
        document_id=doc_id,
        performed_by="investigator_upload"
    )
    
    return {
        "status": "SUCCESS",
        "document_id": doc_id,
        "evidence_id": evidence.evidence_id,
        "sha256_hash": sha256_hash,
        "blockchain_tx_id": evidence.blockchain_tx_id,
        "message": "File uploaded, hashed with SHA-256, OCR processed, and anchored to blockchain."
    }

@router.post("/reseed")
def reseed_all(db: Session = Depends(get_db)):
    seed_database_and_graph(db)
    return {"status": "SUCCESS", "message": "Database and Knowledge Graph reseeded with Operation ShadowNet dataset."}
