"""Performance indexes and constraints.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-17
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fuzzy business-name matching via trigram
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_businesses_normalized_name_trgm "
        "ON businesses USING gin (normalized_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_businesses_business_name_trgm "
        "ON businesses USING gin (business_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_businesses_business_name_ar_trgm "
        "ON businesses USING gin (business_name_ar gin_trgm_ops)"
    )

    # Useful composite indexes for lead filters
    op.create_index(
        "ix_businesses_location_category",
        "businesses",
        ["location_id", "category_id"],
    )
    op.create_index(
        "ix_businesses_lead_score",
        "businesses",
        ["lead_status", "qualification_score"],
    )
    op.create_index(
        "ix_discovery_jobs_status_created",
        "discovery_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_consent_purpose_channel",
        "consent_records",
        ["purpose", "channel", "consent_status"],
    )
    op.create_index(
        "ix_suppression_lookup",
        "suppression_records",
        ["contact_value_hash", "channel", "contact_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_suppression_lookup", table_name="suppression_records")
    op.drop_index("ix_consent_purpose_channel", table_name="consent_records")
    op.drop_index("ix_discovery_jobs_status_created", table_name="discovery_jobs")
    op.drop_index("ix_businesses_lead_score", table_name="businesses")
    op.drop_index("ix_businesses_location_category", table_name="businesses")
    op.execute("DROP INDEX IF EXISTS ix_businesses_business_name_ar_trgm")
    op.execute("DROP INDEX IF EXISTS ix_businesses_business_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_businesses_normalized_name_trgm")
