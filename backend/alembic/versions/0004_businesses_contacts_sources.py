"""Businesses, lead sources and business contacts.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("business_name_ar", sa.String(255), nullable=True),
        sa.Column("normalized_name", sa.String(255), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("district", sa.String(150), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column(
            "business_status",
            sa.String(30),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "lead_status",
            sa.String(30),
            nullable=False,
            server_default="new",
        ),
        sa.Column(
            "qualification_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("qualification_reason", postgresql.JSONB(), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["business_categories.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_businesses_category_id", "businesses", ["category_id"])
    op.create_index("ix_businesses_location_id", "businesses", ["location_id"])
    op.create_index("ix_businesses_lead_status", "businesses", ["lead_status"])
    op.create_index("ix_businesses_qualification_score", "businesses", ["qualification_score"])
    op.create_index("ix_businesses_normalized_name", "businesses", ["normalized_name"])
    op.create_index("ix_businesses_assigned_to", "businesses", ["assigned_to"])
    op.create_index("ix_businesses_created_at", "businesses", ["created_at"])

    op.create_table(
        "lead_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("collection_method", sa.String(50), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("permitted_purposes", postgresql.JSONB(), nullable=True),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["data_providers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_lead_sources_business_id", "lead_sources", ["business_id"])
    op.create_index("ix_lead_sources_provider_id", "lead_sources", ["provider_id"])

    op.create_table(
        "business_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_type", sa.String(30), nullable=False),
        sa.Column("contact_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verification_method", sa.String(50), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["lead_sources.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_business_contacts_business_id", "business_contacts", ["business_id"])
    op.create_index(
        "ix_business_contacts_normalized_value",
        "business_contacts",
        ["normalized_value"],
    )


def downgrade() -> None:
    op.drop_table("business_contacts")
    op.drop_table("lead_sources")
    op.drop_table("businesses")
