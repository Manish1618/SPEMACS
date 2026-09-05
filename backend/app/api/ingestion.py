"""Document upload, extraction and dataset loading."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import accessible_cases, get_current_user, require_case_access, require_role
from app.models.database import get_db
from app.models.entities import AuditLog, Document
from app.schemas.schemas import DocumentResponse
from app.services.evidence import calculate_sha256, register_evidence
from app.services.extraction import extract_entities, extract_text
from app.services.ingestion import seed_database_and_graph

router = APIRouter(prefix="/ingestion", tags=["Ingestion and Extraction"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.post("/upload")
async def upload_document(
    request: Request,
    case_id: str = Form(...),
    title: str = Form(...),
    file_type: str = Form("REPORT"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Store, hash and seal an uploaded document, then extract what it contains."""
    require_case_access(db, user, case_id)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )

    extraction = extract_text(content, file.filename or "", file.content_type or "")
    document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    evidence_id = f"EVID-{document_id.split('-')[1]}"

    # Store the original bytes under the document name, separately from the
    # evidence artifact, so the uploaded file itself is retained.
    documents_dir = settings.STORAGE_DIR / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{document_id}_{(file.filename or 'upload').replace('/', '_')}"
    (documents_dir / safe_name).write_bytes(content)

    document = Document(
        document_id=document_id,
        case_id=case_id,
        filename=file.filename or safe_name,
        title=title,
        file_type=file_type,
        storage_path=f"storage/documents/{safe_name}",
        sha256_hash=calculate_sha256(content),
        extracted_text=extraction.text,
        parsed_metadata={
            "evidence_id": evidence_id,
            "extraction_method": extraction.method,
            "extraction_ok": extraction.ok,
            "extraction_note": extraction.note,
            "content_type": file.content_type,
            "size_bytes": len(content),
        },
        uploaded_by=user.username,
        created_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.commit()

    evidence = register_evidence(
        db=db,
        evidence_id=evidence_id,
        case_id=case_id,
        title=title,
        evidence_type=file_type,
        content_bytes=content,
        document_id=document_id,
        performed_by=user.username,
        metadata={"original_filename": file.filename},
    )

    proposals = extract_entities(extraction.text) if extraction.ok else {
        "entities": [], "relationships": [], "events": [],
        "method": "none", "note": extraction.note,
    }

    db.add(
        AuditLog(
            username=user.username,
            action="UPLOAD_DOCUMENT",
            resource_type="DOCUMENT",
            resource_id=document_id,
            case_id=case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={
                "filename": file.filename,
                "sha256": document.sha256_hash,
                "extraction_ok": extraction.ok,
            },
        )
    )
    db.commit()

    return {
        "status": "stored",
        "document_id": document_id,
        "evidence_id": evidence.evidence_id,
        "sha256": document.sha256_hash,
        "sha256_hash": document.sha256_hash,
        "ledger_block": evidence.blockchain_block_num,
        "extraction": {
            "ok": extraction.ok,
            "method": extraction.method,
            "note": extraction.note,
            "characters": len(extraction.text),
        },
        "proposed": proposals,
        "message": (
            "The file has been stored, hashed with SHA-256 and anchored to the ledger. "
            + (
                "Extracted entities are proposals awaiting your confirmation."
                if extraction.ok
                else f"Its text could not be indexed: {extraction.note}"
            )
        ),
    }


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    return db.query(Document).filter(Document.case_id.in_(scope)).all()


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def document_detail(document_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    document = db.query(Document).filter(Document.document_id == document_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="No such document.")
    require_case_access(db, user, document.case_id)
    return document


@router.post("/reseed")
def reseed(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role("ADMIN")),
):
    """Reload the synthetic dataset. Idempotent: existing records are updated in place."""
    summary = seed_database_and_graph(db)
    db.add(
        AuditLog(
            username=user.username,
            action="RESEED_DATASET",
            resource_type="SYSTEM",
            ip_address=request.client.host if request.client else "unknown",
            details=summary,
        )
    )
    db.commit()
    return {"status": "loaded", **summary}
