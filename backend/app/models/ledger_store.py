"""The integrity ledger's own store -- separate from the database it attests.

Why this file exists at all. Until now `LedgerBlock` was declared on the same
SQLAlchemy `Base` as `Evidence`, which meant the proof that evidence had not
been altered lived inside the database holding the evidence. One connection
could edit an artifact's record and rewrite the chain that attests it, in a
single transaction, and verification would pass. The hash chain was real; it
just had nothing independent to anchor to.

ADR-0001 D2 required a ledger "whose storage is independent of the PostgreSQL
database it attests". This is that separation: a distinct engine, a distinct
connection, and -- where the operator applies the grants below -- distinct
credentials that can only INSERT.

Two consequences worth stating plainly, because they are trade-offs rather than
free wins:

1. **Atomicity with the evidence row is gone.** Two databases cannot commit
   together. `append_block` therefore writes and commits the ledger entry
   *before* the caller commits its evidence row. If the caller then fails, the
   ledger holds a block for evidence that was never registered -- an orphan.
   That is the safe direction to fail: the ledger over-records rather than
   under-records, and `verify_chain` reports orphans. The reverse ordering would
   allow evidence to exist with no anchor at all, which is the failure mode this
   whole subsystem exists to prevent.

2. **Append-only is enforced by the database, not by this code.** The guard
   below stops the ORM issuing an UPDATE or DELETE, which catches programming
   mistakes. It does not stop anyone holding the credential from doing it in
   psql, so it is a seatbelt, not the lock. The lock is the grant:

       -- as a superuser, once, against the ledger database
       CREATE USER spemacs_ledger_writer WITH PASSWORD '...';
       GRANT CONNECT ON DATABASE spemacs_ledger TO spemacs_ledger_writer;
       GRANT USAGE ON SCHEMA public TO spemacs_ledger_writer;
       GRANT SELECT, INSERT ON ledger_blocks TO spemacs_ledger_writer;
       REVOKE UPDATE, DELETE, TRUNCATE ON ledger_blocks FROM spemacs_ledger_writer;

   Then point LEDGER_DATABASE_URL at that user. The application credential for
   the main database must NOT be the same one, or the separation is cosmetic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# A base of its own. Sharing `entities.Base` is exactly what put the ledger
# inside the attested database, so these metadata must not be merged.
LedgerBase = declarative_base()


def _utc_now_naive() -> datetime:
    """Naive UTC, matching the convention every other DateTime column uses."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


ledger_engine = create_engine(
    settings.LEDGER_DATABASE_URL,
    connect_args=(
        {"check_same_thread": False} if "sqlite" in settings.LEDGER_DATABASE_URL else {}
    ),
)

LedgerSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ledger_engine)


class LedgerBlock(LedgerBase):
    """One append-only integrity record, hash-chained to its predecessor.

    block_hash = SHA256(block_number | previous_hash | payload_hash)

    Altering any historical record changes that block's payload_hash, which
    changes its block_hash, which breaks the previous_hash link of every block
    after it. That is the property worth having, and it only means something
    while this table lives somewhere the attested data's writer cannot reach.
    """

    __tablename__ = "ledger_blocks"

    block_number = Column(Integer, primary_key=True, autoincrement=False)
    previous_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    block_hash = Column(String(64), nullable=False, index=True)
    sealed_by = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=_utc_now_naive)


class LedgerIsAppendOnly(RuntimeError):
    """Raised when code tries to modify or remove a sealed block."""


@event.listens_for(LedgerSessionLocal, "before_flush")
def _forbid_mutation(session, flush_context, instances) -> None:
    """Refuse any UPDATE or DELETE of a sealed block.

    A seatbelt against our own mistakes, not a security control -- see the
    module docstring. The real protection is the absence of the grant.
    """
    for obj in session.dirty:
        if isinstance(obj, LedgerBlock) and session.is_modified(obj):
            raise LedgerIsAppendOnly(
                f"Ledger block {obj.block_number} cannot be modified. The integrity "
                "ledger is append-only; correct a bad record by appending a new "
                "block that supersedes it."
            )
    for obj in session.deleted:
        if isinstance(obj, LedgerBlock):
            raise LedgerIsAppendOnly(
                f"Ledger block {obj.block_number} cannot be deleted. The integrity "
                "ledger is append-only."
            )


def get_ledger_db():
    """FastAPI dependency yielding a ledger session."""
    db = LedgerSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_ledger_store() -> None:
    """Create the ledger table if it is absent.

    Deliberately not Alembic. This store holds exactly one table whose shape is
    fixed by the hash-chain definition -- changing a column would invalidate
    every block_hash already sealed, so there is no migration path to manage.
    If the schema ever must change, the honest move is a new chain that anchors
    the old one's head, not an ALTER.
    """
    LedgerBase.metadata.create_all(bind=ledger_engine)


def is_separate_store() -> bool:
    """True when the ledger genuinely lives somewhere else.

    Compares the configured URLs. Identical URLs mean the separation is not in
    effect and the old weakness is still present, which callers should surface
    rather than quietly assume away.
    """
    return settings.LEDGER_DATABASE_URL != settings.DATABASE_URL


def store_description() -> str:
    """A human-readable note on where the ledger lives, for status endpoints."""
    if not is_separate_store():
        return (
            "The ledger shares a database with the evidence it attests, so a single "
            "writer can alter both together. Set LEDGER_DATABASE_URL to a separate "
            "store to close this."
        )
    backend = settings.LEDGER_DATABASE_URL.split("://", 1)[0]
    return (
        f"The ledger is held in a separate {backend} store from the evidence database, "
        "so altering an evidence record does not grant the ability to rewrite its anchor."
    )
