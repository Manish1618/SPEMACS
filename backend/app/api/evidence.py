"""Evidence, chain of custody and ledger integrity endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import (
    accessible_cases,
    get_current_user,
    require_admin,
    require_case_access,
    require_role,
)
from app.models.database import get_db
from app.models.entities import AuditLog, CustodyEvent, Evidence, LedgerAnchor
from app.schemas.schemas import (
    EvidenceResponse,
    IntegrityVerificationResult,
    LedgerBlockOut,
)
from app.services import ledger
from app.services.evidence import (
    read_artifact,
    record_custody_event,
    verify_evidence_integrity,
    write_artifact,
)

router = APIRouter(prefix="/evidence", tags=["Evidence, Custody and Integrity"])


def _load(db: Session, user, evidence_id: str) -> Evidence:
    item = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"No evidence with id {evidence_id}.")
    require_case_access(db, user, item.case_id)
    return item


@router.get("", response_model=List[EvidenceResponse])
def list_evidence(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    return (
        db.query(Evidence)
        .filter(Evidence.case_id.in_(scope))
        .order_by(Evidence.created_at, Evidence.evidence_id)
        .all()
    )


@router.get("/ledger", response_model=List[LedgerBlockOut])
def ledger_blocks(limit: int = 100, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Read from the ledger's own store, not from `db` -- the whole point of the
    # separation is that this data is not reachable through the evidence session.
    return ledger.recent_blocks(min(limit, 500))


@router.get("/ledger/verify")
def verify_ledger(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Walk the whole chain and report the first break, if any."""
    return ledger.verify_chain(db)


@router.get("/ledger/anchoring")
def anchoring_status(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Chaincode reachability and outbox health.

    Separate from /ledger/verify so a caller can ask "is the distributed anchor
    working?" without walking the whole local chain.
    """
    return ledger.fabric_status(db)


@router.post("/ledger/drain")
def drain_anchors(db: Session = Depends(get_db), user=Depends(require_admin)):
    """Deliver queued anchors now, rather than waiting for the worker.

    The background worker does this on a cadence; this exists so an operator can
    force a pass after the network comes back, and so a demo does not have to
    wait out the interval.
    """
    return ledger.outbox.drain_once(db)


@router.get("/{evidence_id}/fabric-anchor")
def fabric_anchor(evidence_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """What the chaincode holds for this evidence item, independently of our database.

    This is the point of the whole exercise: the answer comes from a ledger the
    SPEMACS database cannot write to directly, so it is a second opinion rather
    than an echo.
    """
    item = _load(db, user, evidence_id)
    status = ledger.fabric_status(db)

    if not status.get("enabled"):
        return {
            "evidence_id": evidence_id,
            "enabled": False,
            "detail": status.get("detail"),
            "anchor": None,
            "history": [],
        }

    anchor = ledger.fabric.get_anchor(evidence_id)
    history = ledger.anchor_history(evidence_id)
    verification = ledger.verify_against_fabric(evidence_id, item.sha256_hash or "")

    pending_rows = (
        db.query(LedgerAnchor)
        .filter(
            LedgerAnchor.evidence_id == evidence_id,
            LedgerAnchor.status != "ANCHORED",
        )
        .count()
    )

    return {
        "evidence_id": evidence_id,
        "enabled": True,
        "reachable": status.get("reachable"),
        "channel": status.get("channel"),
        "chaincode": status.get("chaincode"),
        "anchor": anchor,
        "history": history,
        "verification": verification,
        "unanchored_entries": pending_rows,
        "detail": (
            "Anchor read from chaincode, which is a separate store from the "
            "database holding this evidence record."
            if anchor
            else "No anchor on the ledger yet for this item."
        ),
    }


@router.get("/{evidence_id}", response_model=EvidenceResponse)
def evidence_detail(evidence_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return _load(db, user, evidence_id)


@router.get("/{evidence_id}/content")
def evidence_content(evidence_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """The stored artifact as text, so a citation can be opened and read."""
    item = _load(db, user, evidence_id)
    payload = read_artifact(evidence_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="The stored artifact is missing.")

    record_custody_event(db, evidence_id, "VIEW", user.username, {"via": "evidence content"})
    try:
        text = payload.decode("utf-8")
        binary = False
    except UnicodeDecodeError:
        text = ""
        binary = True

    return {
        "evidence_id": evidence_id,
        "title": item.title,
        "evidence_type": item.evidence_type,
        "sha256": item.sha256_hash,
        "size_bytes": len(payload),
        "is_binary": binary,
        "content": text,
    }


@router.get("/{evidence_id}/custody")
def custody_chain(evidence_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = _load(db, user, evidence_id)
    events = (
        db.query(CustodyEvent)
        .filter(CustodyEvent.evidence_id == evidence_id)
        .order_by(CustodyEvent.created_at.asc())
        .all()
    )
    anchors = ledger.anchors_for(db, evidence_id)
    return {
        "evidence_id": evidence_id,
        "title": item.title,
        "sealed_sha256": item.sha256_hash,
        "integrity_status": item.integrity_status,
        "custody_events": [
            {
                "event_id": e.event_id,
                "action": e.action,
                "performed_by": e.performed_by,
                "ip_address": e.ip_address,
                "sha256_at_event": e.sha256_at_event,
                "tamper_detected": e.tamper_detected,
                "details": e.details,
                "created_at": e.created_at,
            }
            for e in events
        ],
        "ledger_anchors": [
            {
                "block_number": b.block_number,
                "block_hash": b.block_hash,
                "previous_hash": b.previous_hash,
                "action": b.payload.get("action"),
                "sealed_by": b.sealed_by,
                "timestamp": b.timestamp,
            }
            for b in anchors
        ],
    }


@router.post("/{evidence_id}/verify", response_model=IntegrityVerificationResult)
def verify(evidence_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _load(db, user, evidence_id)
    try:
        return verify_evidence_integrity(db, evidence_id, performed_by=user.username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/verify-all")
def verify_all(
    case_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    allowed = accessible_cases(db, user)
    scope = [case_id] if case_id and case_id in allowed else allowed
    items = (
        db.query(Evidence)
        .filter(Evidence.case_id.in_(scope))
        .order_by(Evidence.created_at, Evidence.evidence_id)
        .all()
    )

    results = [
        verify_evidence_integrity(db, item.evidence_id, performed_by=user.username)
        for item in items
    ]
    failures = [r for r in results if not r["is_valid"]]
    return {
        "checked": len(results),
        "verified": len(results) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "ledger": ledger.verify_chain(db),
        "results": results,
    }


@router.post("/{evidence_id}/transfer-custody")
def transfer_custody(
    evidence_id: str,
    to_custodian: str,
    reason: str = "",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    _load(db, user, evidence_id)
    event = record_custody_event(
        db,
        evidence_id,
        "CUSTODY_TRANSFER",
        user.username,
        {"to_custodian": to_custodian, "reason": reason},
    )
    return {
        "status": "recorded",
        "evidence_id": evidence_id,
        "event_id": event.event_id,
        "message": f"Custody transfer to {to_custodian} recorded and anchored to the ledger.",
    }


@router.post("/{evidence_id}/simulate-tamper")
def simulate_tamper(
    evidence_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_role("ADMIN", "LEAD_INVESTIGATOR")),
):
    """Alter the stored artifact so integrity detection can be demonstrated."""
    item = _load(db, user, evidence_id)
    original = read_artifact(evidence_id)
    if original is None:
        raise HTTPException(status_code=404, detail="The stored artifact is missing.")

    backup = write_artifact(f"{evidence_id}.original", original)
    write_artifact(evidence_id, original.replace(b"USD 250,000", b"USD 950,000", 1) + b"\nTAMPERED_BYTE_RECORD")

    db.add(
        AuditLog(
            username=user.username,
            action="SIMULATE_TAMPER",
            resource_type="EVIDENCE",
            resource_id=evidence_id,
            case_id=item.case_id,
            ip_address=request.client.host if request.client else "unknown",
            details={"purpose": "integrity demonstration", "backup": str(backup.name)},
        )
    )
    db.commit()

    result = verify_evidence_integrity(db, evidence_id, performed_by=user.username)
    return {
        "status": "artifact_modified",
        "message": (
            "The stored artifact was altered on disk. The integrity check below re-read and "
            "rehashed the file, and the mismatch is real."
        ),
        "verification_result": result,
    }


@router.post("/{evidence_id}/restore")
@router.post("/{evidence_id}/restore-clean")
def restore(
    evidence_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role("ADMIN", "LEAD_INVESTIGATOR")),
):
    item = _load(db, user, evidence_id)
    original = read_artifact(f"{evidence_id}.original")
    if original is None:
        raise HTTPException(
            status_code=404, detail="No pre-modification copy is held for this artifact."
        )
    write_artifact(evidence_id, original)

    db.add(
        AuditLog(
            username=user.username,
            action="RESTORE_ARTIFACT",
            resource_type="EVIDENCE",
            resource_id=evidence_id,
            case_id=item.case_id,
            details={"purpose": "restore after integrity demonstration"},
        )
    )
    db.commit()

    return {
        "status": "restored",
        "verification_result": verify_evidence_integrity(
            db, evidence_id, performed_by=user.username
        ),
    }
