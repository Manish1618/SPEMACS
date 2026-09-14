"""Local append-only integrity ledger -- the synchronous backend.

This is one of two ledger backends. It is always active: every anchor lands here
first, and it is what verify_chain() walks. The Fabric backend
(app/services/ledger/fabric.py) attests the same records independently and
asynchronously, via the outbox in app/services/ledger/outbox.py.

Each block commits to its predecessor:

    block_hash = SHA256(block_number | previous_hash | payload_hash)

Altering any historical record changes that block's payload_hash, which changes
its block_hash, which breaks the previous_hash link of every block after it.

**Where the blocks live matters as much as the chaining.** They are held in a
store of their own (app/models/ledger_store.py), not in the database they
attest, because a chain that a single credential can rewrite alongside the
evidence proves nothing. The functions here therefore take the *main* session
for compatibility with their callers, but ignore it and open a ledger session
of their own.

Scope note (spec section 23): the ledger proves the recorded hash history has
not changed. It does not attest that the underlying evidence is truthful.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.ledger_store import (
    LedgerBlock,
    LedgerSessionLocal,
    is_separate_store,
    store_description,
)

GENESIS_PREVIOUS_HASH = "0" * 64


def _canonical(payload: Dict[str, Any]) -> str:
    """Stable serialization -- key order must not affect the hash."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def compute_block_hash(block_number: int, previous_hash: str, payload_hash: str) -> str:
    preimage = f"{block_number}|{previous_hash}|{payload_hash}"
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def get_head(db: Optional[Session] = None) -> Optional[LedgerBlock]:
    """Highest block in the ledger store. `db` is ignored."""
    ledger_db = LedgerSessionLocal()
    try:
        return (
            ledger_db.query(LedgerBlock)
            .order_by(LedgerBlock.block_number.desc())
            .first()
        )
    finally:
        ledger_db.close()


def append_block(
    db: Optional[Session], payload: Dict[str, Any], sealed_by: str
) -> LedgerBlock:
    """Append one custody/integrity record and commit it to the ledger store.

    Committed immediately, in its own transaction, before the caller commits its
    evidence row. The two stores cannot commit together, so the ordering is the
    design: if the caller subsequently fails, the ledger holds a block for
    evidence that was never registered, which verify_chain reports as an orphan.
    Failing the other way round would let evidence exist with no anchor at all,
    which is the case this subsystem exists to prevent.

    `db` is accepted and ignored, so the seven call sites in app/api and
    app/services did not have to change when the store moved.
    """
    ledger_db = LedgerSessionLocal()
    try:
        head = (
            ledger_db.query(LedgerBlock)
            .order_by(LedgerBlock.block_number.desc())
            .first()
        )
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
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        ledger_db.add(block)
        ledger_db.commit()
        ledger_db.refresh(block)

        # Detach so the caller can read attributes after this session closes.
        ledger_db.expunge(block)
        return block
    except Exception:
        ledger_db.rollback()
        raise
    finally:
        ledger_db.close()


def verify_chain(db: Optional[Session] = None) -> Dict[str, Any]:
    """Walk the whole chain and report the first break, if any. `db` is ignored."""
    ledger_db = LedgerSessionLocal()
    try:
        blocks: List[LedgerBlock] = (
            ledger_db.query(LedgerBlock).order_by(LedgerBlock.block_number.asc()).all()
        )

        separation = {
            "independent_store": is_separate_store(),
            "detail": store_description(),
        }

        if not blocks:
            return {
                "chain_valid": True,
                "block_count": 0,
                "head_hash": None,
                "broken_at_block": None,
                "storage": separation,
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
                    "storage": separation,
                    "message": (
                        f"Chain link broken at block {block.block_number}: recorded "
                        f"previous_hash does not match the hash of block "
                        f"{block.block_number - 1}."
                    ),
                }

            if hash_payload(block.payload) != block.payload_hash:
                return {
                    "chain_valid": False,
                    "block_count": len(blocks),
                    "head_hash": blocks[-1].block_hash,
                    "broken_at_block": block.block_number,
                    "storage": separation,
                    "message": (
                        f"Payload of block {block.block_number} has been modified "
                        "since sealing: recomputed payload hash does not match the "
                        "sealed payload hash."
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
                    "storage": separation,
                    "message": (
                        f"Block {block.block_number} hash does not match its own contents."
                    ),
                }

            expected_previous = block.block_hash

        message = (
            f"All {len(blocks)} ledger blocks verified. Each block correctly commits "
            "to its predecessor. "
        )
        message += (
            "The ledger is stored separately from the evidence database, so this is "
            "an independent check rather than a record vouching for itself. "
            if is_separate_store()
            else "NOTE: the ledger currently shares a database with the evidence it "
            "attests, so a single writer could have altered both together. "
        )
        message += (
            "This attests that the recorded hash history is unaltered, not that the "
            "underlying evidence is truthful."
        )

        return {
            "chain_valid": True,
            "block_count": len(blocks),
            "head_hash": blocks[-1].block_hash,
            "broken_at_block": None,
            "storage": separation,
            "message": message,
        }
    finally:
        ledger_db.close()


def recent_blocks(limit: int = 100) -> List[LedgerBlock]:
    """Newest blocks first, for the ledger listing endpoint."""
    ledger_db = LedgerSessionLocal()
    try:
        blocks = (
            ledger_db.query(LedgerBlock)
            .order_by(LedgerBlock.block_number.desc())
            .limit(limit)
            .all()
        )
        for block in blocks:
            ledger_db.expunge(block)
        return blocks
    finally:
        ledger_db.close()


def find_anchor(db: Optional[Session], evidence_id: str) -> Optional[LedgerBlock]:
    """Most recent block anchoring the given evidence item. `db` is ignored."""
    ledger_db = LedgerSessionLocal()
    try:
        block = (
            ledger_db.query(LedgerBlock)
            .filter(LedgerBlock.payload["evidence_id"].as_string() == evidence_id)
            .order_by(LedgerBlock.block_number.desc())
            .first()
        )
        if block is not None:
            ledger_db.expunge(block)
        return block
    finally:
        ledger_db.close()


def anchors_for(db: Optional[Session], evidence_id: str) -> List[LedgerBlock]:
    """Every block anchoring the given evidence item. `db` is ignored."""
    ledger_db = LedgerSessionLocal()
    try:
        blocks = (
            ledger_db.query(LedgerBlock)
            .filter(LedgerBlock.payload["evidence_id"].as_string() == evidence_id)
            .order_by(LedgerBlock.block_number.asc())
            .all()
        )
        for block in blocks:
            ledger_db.expunge(block)
        return blocks
    finally:
        ledger_db.close()
