"""Discovery jobs.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("country_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("search_keyword", sa.String(255), nullable=False),
        sa.Column("search_keyword_ar", sa.String(255), nullable=True),
        sa.Column("search_parameters", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("total_expected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["business_categories.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["data_providers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"])
    op.create_index("ix_discovery_jobs_location_id", "discovery_jobs", ["location_id"])
    op.create_index("ix_discovery_jobs_category_id", "discovery_jobs", ["category_id"])
    op.create_index("ix_discovery_jobs_provider_id", "discovery_jobs", ["provider_id"])


def downgrade() -> None:
    op.drop_table("discovery_jobs")
