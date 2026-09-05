"""Permissioned append-only integrity ledger.

Replaces the previous placeholder, which minted a random hex string per evidence
item and called it a transaction hash -- nothing was chained, so nothing could be
verified. Here each block commits to its predecessor:

    block_hash = SHA256(block_number | previous_hash | payload_hash)

Altering any historical record changes that block's payload_hash, which changes
its block_hash, which breaks the previous_hash link of every block after it.
That is the property that makes the ledger worth having.

Scope note (spec section 23): the ledger proves the recorded hash history has not
changed. It does not attest that the underlying evidence is truthful.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.entities import LedgerBlock

GENESIS_PREVIOUS_HASH = "0" * 64


def _canonical(payload: Dict[str, Any]) -> str:
    """Stable serialization -- key order must not affect the hash."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def compute_block_hash(block_number: int, previous_hash: str, payload_hash: str) -> str:
    preimage = f"{block_number}|{previous_hash}|{payload_hash}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def get_head(db: Session) -> Optional[LedgerBlock]:
    return db.query(LedgerBlock).order_by(LedgerBlock.block_number.desc()).first()


def append_block(db: Session, payload: Dict[str, Any], sealed_by: str) -> LedgerBlock:
    """Append one custody/integrity record. Caller commits."""
    head = get_head(db)
    block_number = (head.block_number + 1) if head else 0
    previous_hash = head.block_hash if head else GENESIS_PREVIOUS_HASH

    payload_hash = hash_payload(payload)
    block = LedgerBlock(
        block_number=block_number,
        previous_hash=previous_hash,
        payload=payload,
        payload_hash=payload_hash,
        block_hash=compute_block_hash(block_number, previous_hash, payload_hash),
        sealed_by=sealed_by,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(block)
    db.flush()
    return block


def verify_chain(db: Session) -> Dict[str, Any]:
    """Walk the whole chain and report the first break, if any."""
    blocks: List[LedgerBlock] = (
        db.query(LedgerBlock).order_by(LedgerBlock.block_number.asc()).all()
    )
    if not blocks:
        return {
            "chain_valid": True,
            "block_count": 0,
            "head_hash": None,
            "broken_at_block": None,
            "message": "Ledger is empty. No integrity records to verify.",
        }

    expected_previous = GENESIS_PREVIOUS_HASH
    for block in blocks:
        if block.previous_hash != expected_previous:
            return {
                "chain_valid": False,
                "block_count": len(blocks),
                "head_hash": blocks[-1].block_hash,
                "broken_at_block": block.block_number,
                "message": (
                    f"Chain link broken at block {block.block_number}: recorded previous_hash "
                    f"does not match the hash of block {block.block_number - 1}."
                ),
            }

        if hash_payload(block.payload) != block.payload_hash:
            return {
                "chain_valid": False,
                "block_count": len(blocks),
                "head_hash": blocks[-1].block_hash,
                "broken_at_block": block.block_number,
                "message": (
                    f"Payload of block {block.block_number} has been modified since sealing: "
                    "recomputed payload hash does not match the sealed payload hash."
                ),
            }

        recomputed = compute_block_hash(
            block.block_number, block.previous_hash, block.payload_hash
        )
        if recomputed != block.block_hash:
            return {
                "chain_valid": False,
                "block_count": len(blocks),
                "head_hash": blocks[-1].block_hash,
                "broken_at_block": block.block_number,
                "message": f"Block {block.block_number} hash does not match its own contents.",
            }

        expected_previous = block.block_hash

    return {
        "chain_valid": True,
        "block_count": len(blocks),
        "head_hash": blocks[-1].block_hash,
        "broken_at_block": None,
        "message": (
            f"All {len(blocks)} ledger blocks verified. Each block correctly commits to its "
            "predecessor. Note: this attests that the recorded hash history is unaltered, "
            "not that the underlying evidence is truthful."
        ),
    }


def find_anchor(db: Session, evidence_id: str) -> Optional[LedgerBlock]:
    """Most recent block anchoring the given evidence item."""
    return (
        db.query(LedgerBlock)
        .filter(LedgerBlock.payload["evidence_id"].as_string() == evidence_id)
        .order_by(LedgerBlock.block_number.desc())
        .first()
    )


def anchors_for(db: Session, evidence_id: str) -> List[LedgerBlock]:
    return (
        db.query(LedgerBlock)
        .filter(LedgerBlock.payload["evidence_id"].as_string() == evidence_id)
        .order_by(LedgerBlock.block_number.asc())
        .all()
    )
