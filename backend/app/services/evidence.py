"""Evidence registration and integrity verification.

Two defects in the previous implementation are corrected here:

1. Evidence IDs were random UUIDs, so the stable IDs referenced everywhere else
   (EVID-CDR-01 and friends) resolved to nothing and every citation was a dead
   link. Callers now supply the evidence_id, and re-registering the same id
   updates in place instead of inserting a duplicate.

2. Evidence content was never stored, so "verification" rehashed the same
   in-memory string it had just hashed and could never fail honestly. Content is
   now written to the storage directory and re-read from disk on verification,
   which makes tamper detection a real check against a real artifact.
"""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import CustodyEvent, Evidence
from app.services import ledger


def calculate_sha256(content: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(content)
    return digest.hexdigest()


def _artifact_path(evidence_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", evidence_id)
    return settings.STORAGE_DIR / "evidence" / f"{safe}.bin"


def write_artifact(evidence_id: str, content: bytes) -> Path:
    path = _artifact_path(evidence_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def read_artifact(evidence_id: str) -> Optional[bytes]:
    path = _artifact_path(evidence_id)
    if not path.exists():
        return None
    return path.read_bytes()


def register_evidence(
    db: Session,
    evidence_id: str,
    case_id: str,
    title: str,
    evidence_type: str,
    content_bytes: bytes,
    document_id: Optional[str] = None,
    performed_by: str = "system",
    metadata: Optional[Dict[str, Any]] = None,
) -> Evidence:
    """Register (or re-register) an evidence artifact under a caller-chosen id."""
    file_hash = calculate_sha256(content_bytes)
    write_artifact(evidence_id, content_bytes)
    now = datetime.now(timezone.utc)

    block = ledger.append_block(
        db,
        payload={
            "action": "EVIDENCE_SEALED",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "title": title,
            "sha256": file_hash,
            "custodian": performed_by,
            "sealed_at": now.isoformat(),
        },
        sealed_by=performed_by,
    )

    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if evidence is None:
        evidence = Evidence(evidence_id=evidence_id, created_at=now)
        db.add(evidence)

    evidence.case_id = case_id
    evidence.document_id = document_id
    evidence.title = title
    evidence.evidence_type = evidence_type
    evidence.sha256_hash = file_hash
    evidence.integrity_status = "VERIFIED"
    evidence.blockchain_tx_id = block.block_hash
    evidence.blockchain_block_num = block.block_number
    evidence.blockchain_timestamp = now
    evidence.metadata_payload = metadata or {}

    already_sealed = (
        db.query(CustodyEvent)
        .filter(
            CustodyEvent.evidence_id == evidence_id,
            CustodyEvent.action == "SEAL_AND_REGISTRATION",
        )
        .first()
    )
    if already_sealed is None:
        db.add(
            CustodyEvent(
                evidence_id=evidence_id,
                action="SEAL_AND_REGISTRATION",
                performed_by=performed_by,
                sha256_at_event=file_hash,
                tamper_detected=False,
                details={
                    "note": "Artifact stored, SHA-256 sealed and anchored to the permissioned ledger.",
                    "ledger_block": block.block_number,
                    "block_hash": block.block_hash,
                },
                created_at=now,
            )
        )

    db.commit()
    db.refresh(evidence)
    return evidence


def record_custody_event(
    db: Session,
    evidence_id: str,
    action: str,
    performed_by: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "127.0.0.1",
) -> CustodyEvent:
    """Append a custody action and anchor it to the ledger."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise ValueError(f"Evidence {evidence_id} not found")

    now = datetime.now(timezone.utc)
    block = ledger.append_block(
        db,
        payload={
            "action": action,
            "evidence_id": evidence_id,
            "case_id": evidence.case_id,
            "sha256": evidence.sha256_hash,
            "actor": performed_by,
            "occurred_at": now.isoformat(),
            "details": details or {},
        },
        sealed_by=performed_by,
    )

    event = CustodyEvent(
        evidence_id=evidence_id,
        action=action,
        performed_by=performed_by,
        ip_address=ip_address,
        sha256_at_event=evidence.sha256_hash,
        tamper_detected=False,
        details={**(details or {}), "ledger_block": block.block_number},
        created_at=now,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def verify_evidence_integrity(
    db: Session,
    evidence_id: str,
    performed_by: str = "investigator_audit",
) -> Dict[str, Any]:
    """Rehash the artifact on disk and compare it to the sealed hash and the ledger."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise ValueError(f"Evidence {evidence_id} not found")

    stored_hash = evidence.sha256_hash
    anchors = ledger.anchors_for(db, evidence_id)
    seal_anchor = next(
        (b for b in anchors if b.payload.get("action") == "EVIDENCE_SEALED"), None
    )
    ledger_hash = seal_anchor.payload.get("sha256") if seal_anchor else None

    current_bytes = read_artifact(evidence_id)
    artifact_present = current_bytes is not None
    recomputed_hash = calculate_sha256(current_bytes) if artifact_present else None

    chain_state = ledger.verify_chain(db)

    if not artifact_present:
        status, is_valid = "UNVERIFIED", False
        message = (
            "Stored artifact is missing from the evidence store. The sealed hash and ledger "
            "anchor remain intact, but the artifact itself cannot be re-verified."
        )
    elif recomputed_hash != stored_hash:
        status, is_valid = "TAMPER_DETECTED", False
        message = (
            "INTEGRITY FAILURE: the artifact on disk no longer hashes to the value sealed at "
            "registration. The evidence has been modified since it was registered."
        )
    elif ledger_hash is not None and ledger_hash != stored_hash:
        status, is_valid = "TAMPER_DETECTED", False
        message = (
            "INTEGRITY FAILURE: the hash on the evidence record does not match the hash "
            "anchored in the permissioned ledger."
        )
    elif not chain_state["chain_valid"]:
        status, is_valid = "TAMPER_DETECTED", False
        message = f"INTEGRITY FAILURE: {chain_state['message']}"
    else:
        status, is_valid = "VERIFIED", True
        message = (
            "Evidence integrity confirmed. The artifact rehashes to the sealed SHA-256 value, "
            "which matches the ledger anchor, and the ledger chain is unbroken. This attests "
            "that the record is unaltered, not that its content is truthful."
        )

    evidence.integrity_status = status
    now = datetime.now(timezone.utc)

    block = ledger.append_block(
        db,
        payload={
            "action": "INTEGRITY_AUDIT",
            "evidence_id": evidence_id,
            "case_id": evidence.case_id,
            "sha256": recomputed_hash or "",
            "result": status,
            "actor": performed_by,
            "occurred_at": now.isoformat(),
        },
        sealed_by=performed_by,
    )

    db.add(
        CustodyEvent(
            evidence_id=evidence_id,
            action="INTEGRITY_AUDIT_CHECK",
            performed_by=performed_by,
            sha256_at_event=recomputed_hash or stored_hash,
            tamper_detected=not is_valid,
            details={
                "stored_hash": stored_hash,
                "recalculated_hash": recomputed_hash,
                "ledger_hash": ledger_hash,
                "chain_valid": chain_state["chain_valid"],
                "ledger_block": block.block_number,
            },
            created_at=now,
        )
    )
    db.commit()

    return {
        "evidence_id": evidence_id,
        "title": evidence.title,
        "stored_hash": stored_hash,
        "recalculated_hash": recomputed_hash or "",
        "blockchain_hash": ledger_hash,
        "blockchain_tx_id": evidence.blockchain_tx_id,
        "integrity_status": status,
        "is_valid": is_valid,
        "chain_valid": chain_state["chain_valid"],
        "ledger_block_count": chain_state["block_count"],
        "verified_at": now,
        "message": message,
    }


def create_evidence_record(
    db: Session,
    case_id: str,
    title: str,
    evidence_type: str,
    content_bytes: bytes,
    evidence_id: Optional[str] = None,
    document_id: Optional[str] = None,
    performed_by: str = "investigator_system",
    metadata: Optional[Dict[str, Any]] = None,
) -> Evidence:
    """Backwards-compatible entry point. Derives a stable id when none is given."""
    if evidence_id is None:
        evidence_id = "EVID-" + calculate_sha256(
            f"{case_id}|{title}|{evidence_type}".encode("utf-8")
        )[:10].upper()
    return register_evidence(
        db=db,
        evidence_id=evidence_id,
        case_id=case_id,
        title=title,
        evidence_type=evidence_type,
        content_bytes=content_bytes,
        document_id=document_id,
        performed_by=performed_by,
        metadata=metadata,
    )
