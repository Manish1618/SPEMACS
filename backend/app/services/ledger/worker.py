"""Background worker that drains the Fabric anchoring outbox.

Runs as an asyncio task inside the API process. That is the right size for this:
the work is a handful of HTTP calls on a cadence, and a separate queue runtime
would be more infrastructure than the job deserves.

It is deliberately dull. It wakes on an interval, delivers what is pending, and
goes back to sleep. Nothing here can fail a request, because nothing here runs
in a request.

The one caveat, same as the login rate limiter: with several uvicorn workers,
each process runs its own copy. Delivery stays correct because the chaincode
deduplicates on anchor_id, but two workers may briefly attempt the same row.
Run the drain in one process, or move to an external scheduler, before scaling
out.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.core.config import settings
from app.models.database import SessionLocal
from app.services.ledger import fabric, outbox

logger = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None
_stopping = asyncio.Event()


def _drain_blocking() -> dict:
    """One drain pass on its own session. Runs in a thread."""
    db = SessionLocal()
    try:
        return outbox.drain_once(db)
    finally:
        db.close()


async def _loop() -> None:
    interval = max(5, settings.FABRIC_DRAIN_INTERVAL_SECONDS)
    logger.info("Fabric anchor worker started (every %ss).", interval)

    while not _stopping.is_set():
        try:
            result = await asyncio.to_thread(_drain_blocking)
            if result.get("delivered"):
                logger.info(
                    "Anchored %s entr(ies); %s still pending.",
                    result["delivered"],
                    result.get("remaining", 0),
                )
            if result.get("failed"):
                logger.error(
                    "%s anchor(s) exhausted their retries and need attention.",
                    result["failed"],
                )
        except Exception:
            # A worker that dies stops anchoring silently, which is the one
            # outcome worth guarding against here.
            logger.exception("Anchor worker pass failed; continuing.")

        try:
            await asyncio.wait_for(_stopping.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue

    logger.info("Fabric anchor worker stopped.")


def start() -> None:
    """Start the worker, unless Fabric anchoring is switched off."""
    global _task

    if not fabric.enabled():
        logger.info(
            "Fabric anchoring disabled; integrity rests on the local ledger alone."
        )
        return

    if _task is not None and not _task.done():
        return

    _stopping.clear()
    _task = asyncio.create_task(_loop(), name="fabric-anchor-worker")


async def stop() -> None:
    """Ask the worker to finish its current pass and exit."""
    global _task
    if _task is None:
        return
    _stopping.set()
    try:
        await asyncio.wait_for(_task, timeout=10)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        _task.cancel()
    finally:
        _task = None


def running() -> bool:
    return _task is not None and not _task.done()
