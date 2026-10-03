"""provider_keys: users' own LLM API keys (encrypted)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_keys",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("key_encrypted", sa.Text, nullable=False),
        sa.Column("last4", sa.String(4), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "provider", name="uq_provider_keys_owner_provider"),
    )
    op.create_index("ix_provider_keys_owner_id", "provider_keys", ["owner_id"])
    op.execute("ALTER TABLE provider_keys ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("provider_keys")
