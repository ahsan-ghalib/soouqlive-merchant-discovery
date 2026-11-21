"""Email blast + outbox for slow outreach.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_blasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("template", sa.String(length=64), nullable=False, server_default="vendor_outreach"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("delay_seconds", sa.Integer(), nullable=False, server_default="75"),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("total_queued", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_blasts_status", "email_blasts", ["status"])

    op.create_table(
        "email_outbox_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blast_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["blast_id"], ["email_blasts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["business_contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blast_id", "to_email", name="uq_email_outbox_blast_email"),
    )
    op.create_index("ix_email_outbox_items_blast_id", "email_outbox_items", ["blast_id"])
    op.create_index("ix_email_outbox_items_business_id", "email_outbox_items", ["business_id"])
    op.create_index("ix_email_outbox_items_to_email", "email_outbox_items", ["to_email"])
    op.create_index("ix_email_outbox_items_status", "email_outbox_items", ["status"])


def downgrade() -> None:
    op.drop_table("email_outbox_items")
    op.drop_table("email_blasts")
