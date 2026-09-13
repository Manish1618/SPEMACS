"""Transactional outbox carrying local ledger blocks to Fabric chaincode.

The problem this solves: a LedgerBlock row and a chaincode transaction cannot be
committed atomically -- they are two systems with no shared transaction. Writing
to Fabric inline would produce the two failure modes that corrupt an evidence
store:

  * Fabric commits, Postgres rolls back  -> an anchor with no evidence behind it
  * Postgres commits, Fabric times out   -> evidence whose anchor silently never
                                            happened, and no record that it owed one

So nothing writes to Fabric inline. enqueue() writes the *intent* to anchor in
the same transaction as the block, and drain_once() delivers it afterwards.
Delivery is idempotent on anchor_id, so a retry that turns out to have already
landed is a success rather than a duplicate anchor.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import LedgerAnchor
from app.services.ledger import fabric

logger = logging.getLogger(__name__)


def _naive_utc_now() -> datetime:
    """Match the naive-UTC convention every DateTime column in this app uses."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def compute_anchor_id(block_number: int, payload: Dict[str, Any]) -> str:
    """Deterministic idempotency key.

    Derived from the block number and the canonical payload, so the same logical
    anchor always produces the same id no matter how many times the worker
    retries it, and two different anchors never collide.
    """
    canonical = json.dumps(
        {"block_number": block_number, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enqueue(db: Session, block_number: int, payload: Dict[str, Any]) -> Optional[LedgerAnchor]:
    """Queue one anchor for delivery. Caller commits, in its own transaction.

    Returns None when Fabric anchoring is disabled -- there is no value in
    accumulating a queue nobody will ever drain.
    """
    if not fabric.enabled():
        return None

    anchor_id = compute_anchor_id(block_number, payload)

    existing = (
        db.query(LedgerAnchor).filter(LedgerAnchor.anchor_id == anchor_id).first()
    )
    if existing is not None:
        return existing

    anchor = LedgerAnchor(
        anchor_id=anchor_id,
        block_number=block_number,
        evidence_id=payload.get("evidence_id"),
        case_id=payload.get("case_id"),
        action=payload.get("action") or "UNKNOWN",
        payload=payload,
        status="PENDING",
        attempts=0,
        fabric_channel=settings.FABRIC_CHANNEL,
        fabric_chaincode=settings.FABRIC_CHAINCODE,
    )
    db.add(anchor)
    db.flush()
    return anchor


def pending(db: Session, limit: Optional[int] = None) -> List[LedgerAnchor]:
    query = (
        db.query(LedgerAnchor)
        .filter(LedgerAnchor.status == "PENDING")
        .order_by(LedgerAnchor.block_number.asc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def drain_once(db: Session, limit: Optional[int] = None) -> Dict[str, Any]:
    """Deliver one batch of pending anchors. Commits its own work.

    Safe to call repeatedly and safe to call concurrently with evidence writes.
    Never raises: a delivery failure increments attempts and leaves the row
    PENDING for the next pass.
    """
    if not fabric.enabled():
        return {
            "enabled": False,
            "delivered": 0,
            "failed": 0,
            "remaining": 0,
            "detail": "Fabric anchoring is disabled.",
        }

    batch = pending(db, limit or settings.FABRIC_DRAIN_BATCH_SIZE)
    if not batch:
        return {
            "enabled": True,
            "delivered": 0,
            "failed": 0,
            "remaining": 0,
            "detail": "Nothing pending.",
        }

    delivered = 0
    failed = 0

    for anchor in batch:
        result = fabric.submit_anchor(anchor.anchor_id, anchor.action, anchor.payload)
        anchor.attempts = (anchor.attempts or 0) + 1

        if result.ok:
            anchor.status = "ANCHORED"
            anchor.fabric_tx_id = result.tx_id
            anchor.anchored_at = _naive_utc_now()
            anchor.last_error = None
            delivered += 1
            if result.duplicate:
                logger.info(
                    "Anchor %s was already on the ledger; outbox row reconciled.",
                    anchor.anchor_id[:12],
                )
        else:
            anchor.last_error = (result.error or "unknown error")[:2000]
            if anchor.attempts >= settings.FABRIC_MAX_ATTEMPTS:
                # Give up delivering, but keep the row. A FAILED anchor is a
                # visible, auditable gap -- never a silently dropped one.
                anchor.status = "FAILED"
                failed += 1
                logger.error(
                    "Anchor %s FAILED after %s attempts: %s",
                    anchor.anchor_id[:12],
                    anchor.attempts,
                    anchor.last_error,
                )
            else:
                logger.warning(
                    "Anchor %s attempt %s failed: %s",
                    anchor.anchor_id[:12],
                    anchor.attempts,
                    anchor.last_error,
                )
                # Stop the batch on a transport failure: if the gateway is down,
                # the rest will fail identically and only burn attempts.
                db.commit()
                return {
                    "enabled": True,
                    "delivered": delivered,
                    "failed": failed,
                    "remaining": len(pending(db)),
                    "detail": f"Halted early: {anchor.last_error}",
                }

    db.commit()
    return {
        "enabled": True,
        "delivered": delivered,
        "failed": failed,
        "remaining": len(pending(db)),
        "detail": f"Delivered {delivered} anchor(s).",
    }


def summary(db: Session) -> Dict[str, Any]:
    """Outbox health, for the ledger verification endpoint."""
    if not fabric.enabled():
        return {
            "enabled": False,
            "pending": 0,
            "anchored": 0,
            "failed": 0,
            "detail": "Fabric anchoring is disabled. The local ledger stands alone.",
        }

    counts = {"PENDING": 0, "ANCHORED": 0, "FAILED": 0}
    for status_value, count in (
        db.query(LedgerAnchor.status, func.count(LedgerAnchor.id))
        .group_by(LedgerAnchor.status)
        .all()
    ):
        counts[status_value] = count

    detail = f"{counts['ANCHORED']} anchored, {counts['PENDING']} pending"
    if counts["FAILED"]:
        detail += f", {counts['FAILED']} FAILED and needing attention"
    return {
        "enabled": True,
        "pending": counts["PENDING"],
        "anchored": counts["ANCHORED"],
        "failed": counts["FAILED"],
        "detail": detail + ".",
    }
