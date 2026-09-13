"""Integration test: local ledger -> outbox -> chaincode.

Exercises the whole anchoring path without Docker, WSL or a Fabric network, by
running against the chaincode's dev server (fabric/chaincode/spemacs-ledger,
`npm run dev`), which executes the real contract class against an in-memory
stub. What this proves is that the contract logic and the backend integration
agree; distributed trust is what the real network adds on top, and this test
says nothing about it.

Run the dev server first:

    cd fabric/chaincode/spemacs-ledger && npm run dev

Then:

    cd backend && python test_fabric_integration.py

The test uses a throwaway SQLite database, so it never touches your real store.
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

# Settings are read at import time, so the environment has to be set up first.
_TMP_DB = Path(tempfile.gettempdir()) / f"spemacs_fabric_test_{uuid.uuid4().hex[:8]}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["FABRIC_ENABLED"] = "true"
os.environ["FABRIC_GATEWAY_URL"] = os.environ.get("FABRIC_GATEWAY_URL", "http://127.0.0.1:7090")
os.environ["DEMO_MODE"] = "true"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.database import Base, SessionLocal, engine  # noqa: E402
from app.models.entities import LedgerAnchor  # noqa: E402
from app.services import ledger  # noqa: E402

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def gateway_reachable() -> bool:
    status = ledger.fabric.status()
    return status.reachable


def main() -> int:
    Base.metadata.create_all(bind=engine)

    print("\nFabric anchoring integration")
    print("=" * 68)

    status = ledger.fabric.status()
    if not status.reachable:
        print(f"\n  Gateway not reachable at {os.environ['FABRIC_GATEWAY_URL']}")
        print(f"  {status.detail}")
        print("\n  Start it with:")
        print("    cd fabric/chaincode/spemacs-ledger && npm run dev")
        print("\n  (or point FABRIC_GATEWAY_URL at the real gateway)")
        return 2

    print(f"\n  Gateway: {status.detail}")
    print(f"  Channel: {status.channel}  Chaincode: {status.chaincode}  MSP: {status.msp_id}\n")

    db = SessionLocal()
    evidence_id = f"EVID-TEST-{uuid.uuid4().hex[:6].upper()}"
    case_id = "CASE-2024-8812"
    digest = "e" * 64

    # --- 1. append_block enqueues alongside the local block ---------------
    print("Sealing evidence")
    block = ledger.append_block(
        db,
        payload={
            "action": "EVIDENCE_SEALED",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "title": "Integration test artifact",
            "sha256": digest,
            "custodian": "test.runner",
            "sealed_at": "2026-09-13T10:00:00Z",
        },
        sealed_by="test.runner",
    )
    db.commit()

    anchors = db.query(LedgerAnchor).filter(LedgerAnchor.evidence_id == evidence_id).all()
    check("local block written", block.block_hash is not None)
    check("outbox row created in the same transaction", len(anchors) == 1)
    check("outbox row starts PENDING", anchors and anchors[0].status == "PENDING")
    check("nothing sent to chaincode inline", anchors and anchors[0].fabric_tx_id is None)

    # --- 2. the drain worker delivers it ----------------------------------
    print("\nDraining the outbox")
    result = ledger.outbox.drain_once(db)
    check("drain reports one delivered", result["delivered"] == 1, str(result))

    db.expire_all()
    anchor = db.query(LedgerAnchor).filter(LedgerAnchor.evidence_id == evidence_id).first()
    check("outbox row now ANCHORED", anchor.status == "ANCHORED", anchor.status)
    check("transaction id recorded", bool(anchor.fabric_tx_id), str(anchor.fabric_tx_id))
    check("anchored_at stamped", anchor.anchored_at is not None)

    # --- 3. the chaincode holds the digest --------------------------------
    print("\nVerifying against the chaincode")
    verification = ledger.verify_against_fabric(evidence_id, digest)
    check("chaincode confirms the digest", verification.get("match") is True, str(verification))

    tampered = ledger.verify_against_fabric(evidence_id, "f" * 64)
    check("a wrong digest is rejected", tampered.get("match") is False, str(tampered))
    check(
        "rejection reports the anchored value",
        tampered.get("anchored_sha256") == digest,
        str(tampered.get("anchored_sha256")),
    )

    # --- 4. custody event adds a version ----------------------------------
    print("\nRecording a custody transfer")
    ledger.append_block(
        db,
        payload={
            "action": "TRANSFER",
            "evidence_id": evidence_id,
            "case_id": case_id,
            "sha256": digest,
            "actor": "test.runner",
            "occurred_at": "2026-09-13T11:00:00Z",
            "details": {"to_custodian": "forensics.lab"},
        },
        sealed_by="test.runner",
    )
    db.commit()
    ledger.outbox.drain_once(db)

    history = ledger.anchor_history(evidence_id)
    check("chaincode history holds both versions", len(history) == 2, f"{len(history)} version(s)")

    # --- 5. redelivering is safe ------------------------------------------
    print("\nRe-delivering an already-anchored entry")
    first = db.query(LedgerAnchor).filter(LedgerAnchor.evidence_id == evidence_id).first()
    replay = ledger.fabric.submit_anchor(first.anchor_id, first.action, first.payload)
    check("replay succeeds rather than erroring", replay.ok, str(replay.error))
    check("replay is reported as a duplicate", replay.duplicate is True)

    history_after = ledger.anchor_history(evidence_id)
    check(
        "replay wrote no extra version",
        len(history_after) == len(history),
        f"{len(history_after)} vs {len(history)}",
    )

    # --- 6. outbox summary is honest --------------------------------------
    print("\nLedger status")
    summary = ledger.outbox.summary(db)
    check("summary counts the anchored entries", summary["anchored"] == 2, str(summary))
    check("nothing left pending", summary["pending"] == 0, str(summary))
    check("nothing failed", summary["failed"] == 0, str(summary))

    chain = ledger.verify_chain(db)
    check("local chain still verifies", chain["chain_valid"] is True, chain.get("message", ""))
    check("verify_chain reports Fabric alongside", chain["fabric"]["enabled"] is True)
    check("Fabric reported reachable", chain["fabric"]["reachable"] is True)

    db.close()

    print("\n" + "=" * 68)
    print(f"  {PASSED} passed, {FAILED} failed")
    print("=" * 68 + "\n")
    return 1 if FAILED else 0


if __name__ == "__main__":
    code = 2
    try:
        code = main()
    finally:
        try:
            engine.dispose()
            if _TMP_DB.exists():
                _TMP_DB.unlink()
        except OSError:
            pass
    sys.exit(code)
