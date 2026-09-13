"""Is chaincode actually working? Checks every layer and says which one is not.

    python check_fabric.py

Works against the stub dev server or a real Fabric network -- it does not care
which, and it tells you which one answered. It performs a real round trip:
writes a throwaway anchor, reads it back, verifies the digest, and confirms a
replay is treated as a duplicate rather than a second record.

The throwaway anchor is written under evidence id SPEMACS-HEALTHCHECK. On a real
ledger that write is permanent -- it is a ledger, after all -- so the id is
deliberately obvious and carries a note saying what it is.

Exit codes: 0 all good, 1 something is wrong, 2 could not even start.
"""

import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import settings  # noqa: E402
from app.models.database import SessionLocal  # noqa: E402
from app.services import ledger  # noqa: E402

GREEN = "  [ok]   "
RED = "  [FAIL] "
INFO = "         "

problems = []


def ok(msg):
    print(GREEN + msg)


def fail(msg, fix=""):
    print(RED + msg)
    problems.append((msg, fix))


def info(msg):
    print(INFO + msg)


def main() -> int:
    print()
    print("Chaincode health check")
    print("=" * 70)

    # --- 1. configuration -------------------------------------------------
    print("\n1. Configuration")
    if not settings.FABRIC_ENABLED:
        fail(
            "FABRIC_ENABLED is false -- the chaincode path is switched off.",
            "Set FABRIC_ENABLED=true in backend/.env, or start the API with:\n"
            '           $env:FABRIC_ENABLED="true"; python -m uvicorn app.main:app --port 8000',
        )
        info("Everything below is skipped: nothing will reach chaincode.")
        return report()
    ok(f"FABRIC_ENABLED is true")
    info(f"gateway   {settings.FABRIC_GATEWAY_URL}")
    info(f"channel   {settings.FABRIC_CHANNEL}")
    info(f"chaincode {settings.FABRIC_CHAINCODE}")
    if not settings.FABRIC_GATEWAY_TOKEN:
        info("no FABRIC_GATEWAY_TOKEN set (fine on loopback, set one before exposing it)")

    # --- 2. gateway -------------------------------------------------------
    print("\n2. Gateway")
    status = ledger.fabric.status()
    if not status.reachable:
        fail(
            f"Gateway is not reachable: {status.detail}",
            "Start one of:\n"
            "           stub  -> cd fabric/chaincode/spemacs-ledger && npm run dev\n"
            "           real  -> source fabric/scripts/env.sh && node fabric/gateway/server.js",
        )
        return report()

    is_stub = (status.channel or "").lower() == "stub" or "STUB" in (status.detail or "")
    if is_stub:
        ok("Gateway reachable -- STUB ledger")
        info("This is the in-memory dev server. It runs the real contract code,")
        info("but there is no consensus and no second organisation. It proves")
        info("the logic works. It proves nothing about tamper resistance.")
    else:
        ok(f"Gateway reachable -- real network, MSP {status.msp_id}")
        info(f"channel {status.channel}, chaincode {status.chaincode}")

    # --- 3. outbox --------------------------------------------------------
    print("\n3. Delivery queue")
    db = SessionLocal()
    try:
        summary = ledger.outbox.summary(db)
        if summary["failed"]:
            fail(
                f"{summary['failed']} anchor(s) gave up after repeated failures.",
                "Inspect them:  SELECT evidence_id, last_error FROM ledger_anchors "
                "WHERE status='FAILED';",
            )
        if summary["pending"]:
            info(f"{summary['pending']} pending -- the worker delivers every "
                 f"{settings.FABRIC_DRAIN_INTERVAL_SECONDS}s, or POST /evidence/ledger/drain")
        ok(f"{summary['anchored']} anchored, {summary['pending']} pending, "
           f"{summary['failed']} failed")

        # --- 4. round trip ------------------------------------------------
        print("\n4. Round trip")
        marker = uuid.uuid4().hex[:8]
        evidence_id = "SPEMACS-HEALTHCHECK"
        digest = uuid.uuid5(uuid.NAMESPACE_DNS, marker).hex * 2  # 64 hex chars
        payload = {
            "action": "EVIDENCE_SEALED",
            "evidence_id": evidence_id,
            "case_id": "HEALTHCHECK",
            "title": f"Health check {marker} - not real evidence",
            "sha256": digest,
            "custodian": "check_fabric.py",
            "sealed_at": "2026-01-01T00:00:00Z",
            "note": "Written by check_fabric.py to prove the ledger is reachable.",
        }
        anchor_id = ledger.outbox.compute_anchor_id(-1, payload)

        write = ledger.fabric.submit_anchor(anchor_id, "EVIDENCE_SEALED", payload)
        if not write.ok:
            fail(f"Could not write to chaincode: {write.error}")
            return report()
        ok(f"wrote an anchor  (tx {str(write.tx_id)[:24]})")

        check = ledger.verify_against_fabric(evidence_id, digest)
        if not check.get("checked"):
            fail(f"Could not read back: {check.get('detail')}")
        elif not check.get("match"):
            fail(
                "Chaincode returned a different digest than the one just written.",
                "That should be impossible; inspect the chaincode deployment.",
            )
        else:
            ok("read it back and the digest matches")

        replay = ledger.fabric.submit_anchor(anchor_id, "EVIDENCE_SEALED", payload)
        if not replay.ok:
            fail(f"Replaying the same anchor failed: {replay.error}")
        elif not replay.duplicate:
            fail(
                "A replayed anchor was accepted as new -- idempotency is broken.",
                "Outbox retries would create duplicate ledger records.",
            )
        else:
            ok("replaying it is recognised as a duplicate, not written twice")

        history = ledger.anchor_history(evidence_id)
        if history:
            ok(f"version history readable ({len(history)} version(s))")
        else:
            fail("History came back empty; GetHistoryForKey may not be working.")

        # --- 5. local chain still sound ------------------------------------
        print("\n5. Local chain")
        chain = ledger.verify_chain(db)
        if chain["chain_valid"]:
            ok(f"{chain['block_count']} blocks, unbroken")
        else:
            fail(f"Local chain is broken: {chain['message']}")
    finally:
        db.close()

    return report()


def report() -> int:
    print("\n" + "=" * 70)
    if not problems:
        print("  Chaincode is working.")
        print("=" * 70 + "\n")
        return 0
    print(f"  {len(problems)} problem(s):\n")
    for msg, fix in problems:
        print(f"  - {msg}")
        if fix:
            print(f"    fix: {fix}")
    print("=" * 70 + "\n")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
