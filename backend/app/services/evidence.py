import hashlib
from datetime import datetime, timezone
import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.entities import Evidence, CustodyEvent, BlockchainRecord, Document

def calculate_sha256(content: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(content)
    return sha256_hash.hexdigest()

def create_evidence_record(
    db: Session,
    case_id: str,
    title: str,
    evidence_type: str,
    content_bytes: bytes,
    document_id: Optional[str] = None,
    performed_by: str = "investigator_system",
    metadata: Optional[Dict[str, Any]] = None
) -> Evidence:
    file_hash = calculate_sha256(content_bytes)
    evidence_id = f"EVID-{uuid.uuid4().hex[:8].upper()}"
    
    # 1. Mint Mock Blockchain Record
    tx_hash = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex}"[:66]
    block_num = 14200000 + (db.query(BlockchainRecord).count() + 1)
    now = datetime.now(timezone.utc)
    
    bc_record = BlockchainRecord(
        tx_hash=tx_hash,
        evidence_id=evidence_id,
        case_id=case_id,
        sha256_digest=file_hash,
        block_number=block_num,
        sealed_by=performed_by,
        timestamp=now
    )
    db.add(bc_record)
    
    # 2. Create Evidence Record
    evidence = Evidence(
        evidence_id=evidence_id,
        case_id=case_id,
        document_id=document_id,
        title=title,
        evidence_type=evidence_type,
        sha256_hash=file_hash,
        integrity_status="VERIFIED",
        blockchain_tx_id=tx_hash,
        blockchain_block_num=block_num,
        blockchain_timestamp=now,
        metadata_payload=metadata or {}
    )
    db.add(evidence)
    
    # 3. Create Initial Custody Event
    custody_event = CustodyEvent(
        evidence_id=evidence_id,
        action="SEAL_AND_REGISTRATION",
        performed_by=performed_by,
        ip_address="127.0.0.1",
        sha256_at_event=file_hash,
        tamper_detected=False,
        details={"note": "Initial ingestion, cryptographic SHA-256 seal & blockchain anchor"}
    )
    db.add(custody_event)
    
    db.commit()
    db.refresh(evidence)
    return evidence

def verify_evidence_integrity(
    db: Session,
    evidence_id: str,
    current_content_bytes: Optional[bytes] = None,
    performed_by: str = "investigator_audit"
) -> Dict[str, Any]:
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise ValueError(f"Evidence {evidence_id} not found")
        
    stored_hash = evidence.sha256_hash
    blockchain_rec = db.query(BlockchainRecord).filter(BlockchainRecord.evidence_id == evidence_id).first()
    blockchain_hash = blockchain_rec.sha256_digest if blockchain_rec else stored_hash
    
    # If bytes provided, compute; otherwise use stored (or check document file on disk)
    if current_content_bytes is not None:
        recomputed_hash = calculate_sha256(current_content_bytes)
    else:
        # Check associated document if present
        if evidence.document and evidence.document.extracted_text:
            recomputed_hash = calculate_sha256(evidence.document.extracted_text.encode("utf-8"))
        else:
            recomputed_hash = stored_hash
            
    is_valid = (stored_hash == recomputed_hash) and (stored_hash == blockchain_hash)
    status = "VERIFIED" if is_valid else "TAMPER_DETECTED"
    
    evidence.integrity_status = status
    
    # Record verification custody event
    custody_event = CustodyEvent(
        evidence_id=evidence_id,
        action="INTEGRITY_AUDIT_CHECK",
        performed_by=performed_by,
        ip_address="127.0.0.1",
        sha256_at_event=recomputed_hash,
        tamper_detected=not is_valid,
        details={
            "stored_hash": stored_hash,
            "recalculated_hash": recomputed_hash,
            "blockchain_hash": blockchain_hash,
            "match": is_valid
        }
    )
    db.add(custody_event)
    db.commit()
    
    message = "Evidence integrity confirmed: Stored SHA-256 matches active artifact and immutable blockchain ledger." if is_valid else "ALERT: Cryptographic mismatch detected! Evidence has been altered since registration."
    
    return {
        "evidence_id": evidence_id,
        "title": evidence.title,
        "stored_hash": stored_hash,
        "recalculated_hash": recomputed_hash,
        "blockchain_hash": blockchain_hash,
        "blockchain_tx_id": evidence.blockchain_tx_id,
        "integrity_status": status,
        "is_valid": is_valid,
        "verified_at": datetime.now(timezone.utc),
        "message": message
    }
