"""Integrity ledger -- one public surface over two backends.

    local.py    synchronous hash chain, always on, in the caller's transaction
    fabric.py   Hyperledger Fabric chaincode, optional, asynchronous
    outbox.py   the bridge between them

Why both, rather than Fabric replacing the local chain:

  * An evidence write must never fail because a distributed ledger is
    unreachable. The local chain commits with the evidence row and answers
    immediately; Fabric anchoring happens after, and its absence is recorded
    rather than fatal.
  * The local chain is what verify_chain() walks, so tamper detection keeps
    working with Fabric switched off -- which is how the app runs by default.
  * Fabric is what makes the attestation independent of the database it
    attests, and puts it beyond any single organisation's unilateral control.
    That is the property the local chain cannot provide on its own, and the only
    reason the chaincode exists.

Every function here keeps the signature it had when this module was a single
file, so callers in app/api and app/services are unchanged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.entities import LedgerBlock
from app.services.ledger import fabric, outbox, worker
from app.services.ledger.local import (
    GENESIS_PREVIOUS_HASH,
    anchors_for,
    compute_block_hash,
    find_anchor,
    get_head,
    hash_payload,
)
from app.services.ledger.local import append_block as _append_local
from app.services.ledger.local import verify_chain as _verify_local

__all__ = [
    "GENESIS_PREVIOUS_HASH",
    "anchors_for",
    "append_block",
    "compute_block_hash",
    "fabric",
    "find_anchor",
    "get_head",
    "hash_payload",
    "outbox",
    "worker",
    "verify_chain",
    "fabric_status",
]


def append_block(db: Session, payload: Dict[str, Any], sealed_by: str) -> LedgerBlock:
    """Append one custody/integrity record. Caller commits.

    The local block and its Fabric outbox entry are created in the caller's
    transaction, so they commit or roll back together. Actual delivery to
    chaincode happens later, in the drain worker.
    """
    block = _append_local(db, payload=payload, sealed_by=sealed_by)
    outbox.enqueue(db, block_number=block.block_number, payload=payload)
    return block


def verify_chain(db: Session) -> Dict[str, Any]:
    """Walk the local chain, and report Fabric's view alongside it.

    The verdict in `chain_valid` is the local chain's, unchanged -- Fabric being
    down or disabled never turns a valid chain into an invalid one. What Fabric
    adds is a second, independent opinion, reported separately so a reader can
    see which guarantee is speaking.
    """
    result = _verify_local(db)
    result["fabric"] = fabric_status(db)
    return result


def fabric_status(db: Optional[Session] = None) -> Dict[str, Any]:
    """Gateway reachability plus outbox health, in one object."""
    if not fabric.enabled():
        return {
            "enabled": False,
            "reachable": False,
            "detail": (
                "Fabric anchoring is disabled. Integrity rests on the local "
                "hash-chained ledger alone, which is stored in the same database "
                "it attests."
            ),
        }

    gateway = fabric.status()
    payload: Dict[str, Any] = {
        "enabled": True,
        "reachable": gateway.reachable,
        "detail": gateway.detail,
        "channel": gateway.channel,
        "chaincode": gateway.chaincode,
        "msp_id": gateway.msp_id,
    }
    if db is not None:
        payload["outbox"] = outbox.summary(db)
    return payload


def anchor_history(evidence_id: str) -> List[Dict[str, Any]]:
    """Chaincode's own version history for one evidence key."""
    return fabric.get_anchor_history(evidence_id)


def verify_against_fabric(evidence_id: str, sha256: str) -> Dict[str, Any]:
    """Independent confirmation that chaincode holds this digest."""
    return fabric.verify_anchor(evidence_id, sha256)
