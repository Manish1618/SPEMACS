"""Add ledger_anchors: the Fabric anchoring outbox.

Revision ID: a1f4c7d2e803
Revises: 60c8a336b3b9
Create Date: 2026-09-13

A row here is the committed intent to anchor a local ledger block to chaincode.
It is written in the same transaction as the block, so the two cannot disagree
about what was supposed to happen; delivery to Fabric is separate and may lag.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4c7d2e803"
down_revision: Union[str, Sequence[str], None] = "60c8a336b3b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledger_anchors",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("anchor_id", sa.String(length=64), nullable=False),
        sa.Column("block_number", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.String(length=64), nullable=True),
        sa.Column("case_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("fabric_tx_id", sa.String(length=128), nullable=True),
        sa.Column("fabric_channel", sa.String(length=64), nullable=True),
        sa.Column("fabric_chaincode", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("anchored_at", sa.DateTime(), nullable=True),
    )
    # anchor_id is the idempotency key the chaincode dedupes on; a duplicate
    # here would mean two outbox rows racing for the same chaincode write.
    op.create_index(
        "ix_ledger_anchors_anchor_id", "ledger_anchors", ["anchor_id"], unique=True
    )
    op.create_index("ix_ledger_anchors_block_number", "ledger_anchors", ["block_number"])
    op.create_index("ix_ledger_anchors_evidence_id", "ledger_anchors", ["evidence_id"])
    op.create_index("ix_ledger_anchors_case_id", "ledger_anchors", ["case_id"])
    op.create_index("ix_ledger_anchors_status", "ledger_anchors", ["status"])
    op.create_index("ix_ledger_anchors_fabric_tx_id", "ledger_anchors", ["fabric_tx_id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_anchors_fabric_tx_id", table_name="ledger_anchors")
    op.drop_index("ix_ledger_anchors_status", table_name="ledger_anchors")
    op.drop_index("ix_ledger_anchors_case_id", table_name="ledger_anchors")
    op.drop_index("ix_ledger_anchors_evidence_id", table_name="ledger_anchors")
    op.drop_index("ix_ledger_anchors_block_number", table_name="ledger_anchors")
    op.drop_index("ix_ledger_anchors_anchor_id", table_name="ledger_anchors")
    op.drop_table("ledger_anchors")
