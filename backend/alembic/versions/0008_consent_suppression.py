"""Consent and suppression records.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("consent_status", sa.String(30), nullable=False),
        sa.Column("consent_method", sa.String(50), nullable=False),
        sa.Column("consent_evidence", postgresql.JSONB(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # No unrestricted cascading deletes for consent audit records
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["business_contacts.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_consent_records_business_id", "consent_records", ["business_id"])
    op.create_index("ix_consent_records_contact_id", "consent_records", ["contact_id"])

    op.create_table(
        "suppression_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contact_value_hash", sa.String(255), nullable=False),
        sa.Column("contact_type", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_suppression_records_contact_value_hash",
        "suppression_records",
        ["contact_value_hash"],
    )


def downgrade() -> None:
    op.drop_table("suppression_records")
    op.drop_table("consent_records")
