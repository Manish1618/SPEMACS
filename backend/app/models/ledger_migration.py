"""Move existing ledger blocks out of the attested database into their own store.

Runs once at startup and is idempotent. Blocks are *copied*, never moved: the
legacy `ledger_blocks` table in the main database is left exactly as it was, so
this can be run, inspected, and re-run without risking the only copy of a
custody record. Dropping the legacy table is a separate, deliberate step once
the operator has confirmed the new store verifies -- see drop_legacy_table().

Every block is copied byte-for-byte, including its sealed hashes. Nothing is
recomputed, because recomputing would make a corrupted chain look healthy: the
point of the copy is that the chain must still verify *afterwards* using the
hashes that were sealed at the time.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import inspect, text

from app.models.database import SessionLocal, engine
from app.models.ledger_store import (
    LedgerBlock,
    LedgerSessionLocal,
    is_separate_store,
    ledger_engine,
)

logger = logging.getLogger(__name__)

LEGACY_TABLE = "ledger_blocks"


def _legacy_rows() -> list:
    """Read the old table directly, without an ORM model bound to it.

    The model now points at the new store, so the legacy table is reached with
    plain SQL. That also means this keeps working after the model is gone.
    """
    if not inspect(engine).has_table(LEGACY_TABLE):
        return []

    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "SELECT block_number, previous_hash, payload, payload_hash, "
                "block_hash, sealed_by, timestamp "
                f"FROM {LEGACY_TABLE} ORDER BY block_number ASC"
            )
        )
        return list(result.mappings())
    finally:
        db.close()


def _coerce_payload(value: Any) -> Dict[str, Any]:
    """SQLite hands back a JSON string where PostgreSQL hands back a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, (str, bytes)):
        import json

        return json.loads(value)
    return {}


def migrate_if_needed() -> Dict[str, Any]:
    """Copy legacy blocks into the ledger store. Safe to call on every startup."""
    if not is_separate_store():
        return {
            "ran": False,
            "reason": "LEDGER_DATABASE_URL matches DATABASE_URL; nothing to separate.",
            "copied": 0,
        }

    legacy = _legacy_rows()
    if not legacy:
        return {"ran": False, "reason": "No legacy ledger table or no rows.", "copied": 0}

    ledger_db = LedgerSessionLocal()
    try:
        existing = {
            number
            for (number,) in ledger_db.query(LedgerBlock.block_number).all()
        }
        missing = [row for row in legacy if row["block_number"] not in existing]

        if not missing:
            return {
                "ran": False,
                "reason": f"All {len(legacy)} legacy blocks are already in the ledger store.",
                "copied": 0,
            }

        for row in missing:
            ledger_db.add(
                LedgerBlock(
                    block_number=row["block_number"],
                    previous_hash=row["previous_hash"],
                    payload=_coerce_payload(row["payload"]),
                    payload_hash=row["payload_hash"],
                    block_hash=row["block_hash"],
                    sealed_by=row["sealed_by"],
                    timestamp=row["timestamp"],
                )
            )
        ledger_db.commit()

        logger.warning(
            "Copied %s ledger block(s) out of the attested database into the "
            "independent ledger store. The legacy table was left in place; drop it "
            "once you have confirmed the chain verifies.",
            len(missing),
        )
        return {
            "ran": True,
            "reason": "Copied legacy blocks into the independent store.",
            "copied": len(missing),
        }
    except Exception:
        ledger_db.rollback()
        raise
    finally:
        ledger_db.close()


def drop_legacy_table() -> Dict[str, Any]:
    """Remove the old table from the attested database. Deliberate, never automatic.

    Refuses unless every legacy block is present in the new store and the new
    chain verifies, so this cannot be the step that loses a custody record.
    """
    from app.services.ledger import local

    if not is_separate_store():
        return {"dropped": False, "reason": "No separate store configured."}

    legacy = _legacy_rows()
    if not legacy:
        return {"dropped": False, "reason": "Legacy table is already absent or empty."}

    ledger_db = LedgerSessionLocal()
    try:
        existing = {
            number for (number,) in ledger_db.query(LedgerBlock.block_number).all()
        }
    finally:
        ledger_db.close()

    missing = [r["block_number"] for r in legacy if r["block_number"] not in existing]
    if missing:
        return {
            "dropped": False,
            "reason": (
                f"{len(missing)} legacy block(s) are not in the new store "
                f"(first: {missing[0]}). Run migrate_if_needed() first."
            ),
        }

    chain = local.verify_chain()
    if not chain["chain_valid"]:
        return {
            "dropped": False,
            "reason": f"New store does not verify: {chain['message']}",
        }

    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE {LEGACY_TABLE}"))

    logger.warning(
        "Dropped the legacy %s table from the evidence database. The integrity "
        "ledger now exists only in its own store.",
        LEGACY_TABLE,
    )
    return {
        "dropped": True,
        "reason": f"Verified {chain['block_count']} blocks in the new store, then dropped the legacy table.",
    }
