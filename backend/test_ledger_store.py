"""The integrity ledger must not live in the database it attests.

This guards the property, not the plumbing. The weakness it exists to prevent:
if one credential can edit an evidence record and rewrite the chain proving it
unaltered, verification passes on tampered evidence and the ledger is decorative.

Run:  python test_ledger_store.py

Uses throwaway SQLite files for both stores, so it never touches real data.
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path

_TMP = Path(tempfile.gettempdir())
_MAIN = _TMP / f"spemacs_main_{uuid.uuid4().hex[:8]}.db"
_LEDGER = _TMP / f"spemacs_ledger_{uuid.uuid4().hex[:8]}.db"

os.environ["DATABASE_URL"] = f"sqlite:///{_MAIN}"
os.environ["LEDGER_DATABASE_URL"] = f"sqlite:///{_LEDGER}"
os.environ["DEMO_MODE"] = "true"
os.environ["FABRIC_ENABLED"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.models.database import Base, SessionLocal, engine  # noqa: E402
from app.models.ledger_store import (  # noqa: E402
    LedgerBlock,
    LedgerIsAppendOnly,
    LedgerSessionLocal,
    init_ledger_store,
    is_separate_store,
    ledger_engine,
)
from app.services.ledger import local  # noqa: E402

PASSED = 0
FAILED = 0


def check(label, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))


def main() -> int:
    Base.metadata.create_all(bind=engine)
    init_ledger_store()

    print("\nIntegrity ledger store separation")
    print("=" * 68)

    # --- the separation itself -------------------------------------------
    print("\nThe stores are distinct")
    check("ledger URL differs from the evidence database", is_separate_store())
    check(
        "ledger table is absent from the evidence database",
        not inspect(engine).has_table("ledger_blocks"),
        "ledger_blocks should not exist in the attested database",
    )
    check(
        "ledger table exists in its own store",
        inspect(ledger_engine).has_table("ledger_blocks"),
    )
    check(
        "the evidence session cannot even see the ledger",
        "ledger_blocks" not in inspect(engine).get_table_names(),
    )

    # --- appending still behaves ------------------------------------------
    print("\nAppending")
    evidence_id = f"EVID-SEP-{uuid.uuid4().hex[:6].upper()}"
    digest = "a" * 64
    b0 = local.append_block(
        None,
        payload={
            "action": "EVIDENCE_SEALED",
            "evidence_id": evidence_id,
            "case_id": "CASE-SEP",
            "sha256": digest,
        },
        sealed_by="test",
    )
    check("a block can be appended", b0 is not None)
    check("its attributes survive the session closing", bool(b0.block_hash))

    b1 = local.append_block(
        None,
        payload={"action": "TRANSFER", "evidence_id": evidence_id, "sha256": digest},
        sealed_by="test",
    )
    check("block numbers advance", b1.block_number == b0.block_number + 1)
    check("each block links to its predecessor", b1.previous_hash == b0.block_hash)

    chain = local.verify_chain()
    check("the chain verifies", chain["chain_valid"] is True, chain.get("message", ""))
    check("verification reports the store is independent",
          chain["storage"]["independent_store"] is True)

    # --- append-only -------------------------------------------------------
    print("\nAppend-only")
    db = LedgerSessionLocal()
    try:
        block = db.query(LedgerBlock).first()
        block.payload = {"tampered": True}
        db.flush()
        check("an UPDATE through the ORM is refused", False, "the update succeeded")
    except LedgerIsAppendOnly:
        check("an UPDATE through the ORM is refused", True)
    finally:
        db.rollback()
        db.close()

    db = LedgerSessionLocal()
    try:
        db.delete(db.query(LedgerBlock).first())
        db.flush()
        check("a DELETE through the ORM is refused", False, "the delete succeeded")
    except LedgerIsAppendOnly:
        check("a DELETE through the ORM is refused", True)
    finally:
        db.rollback()
        db.close()

    # --- what the separation actually buys ---------------------------------
    print("\nThe property this exists for")
    # Someone with the evidence database can tamper freely there...
    main_db = SessionLocal()
    try:
        tables = inspect(engine).get_table_names()
        check(
            "full access to the evidence database grants no access to the ledger",
            "ledger_blocks" not in tables,
            f"tables reachable: {len(tables)}",
        )
    finally:
        main_db.close()

    # ...and a tamper inside the ledger store is still caught by the chain.
    ledger_db = LedgerSessionLocal()
    try:
        ledger_db.execute(
            text("UPDATE ledger_blocks SET payload_hash='deadbeef' WHERE block_number=:n"),
            {"n": b1.block_number},
        )
        ledger_db.commit()
    finally:
        ledger_db.close()

    broken = local.verify_chain()
    check(
        "raw SQL tampering inside the ledger store is still detected",
        broken["chain_valid"] is False,
        "chain reported valid after a payload_hash was altered",
    )
    check(
        "the break is reported at the right block",
        broken["broken_at_block"] == b1.block_number,
        str(broken.get("broken_at_block")),
    )

    print("\n" + "=" * 68)
    print(f"  {PASSED} passed, {FAILED} failed")
    print("=" * 68 + "\n")
    return 1 if FAILED else 0


if __name__ == "__main__":
    code = 2
    try:
        code = main()
    finally:
        engine.dispose()
        ledger_engine.dispose()
        for path in (_MAIN, _LEDGER):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
    sys.exit(code)
