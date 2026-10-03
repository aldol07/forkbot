"""file storage, page/section-aware chunks, conversations + messages, RLS lock-down

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ("users", "bots", "documents", "chunks", "conversations", "messages", "alembic_version")


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_type", sa.String(100)))
    op.add_column("documents", sa.Column("sha256", sa.String(64)))
    op.add_column("documents", sa.Column("storage_key", sa.String(500)))
    op.add_column("documents", sa.Column("n_pages", sa.Integer, nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("n_images", sa.Integer, nullable=False, server_default="0"))
    op.create_index("ix_documents_bot_sha256", "documents", ["bot_id", "sha256"])

    op.add_column("chunks", sa.Column("kind", sa.String(10), nullable=False, server_default="text"))
    op.add_column("chunks", sa.Column("page", sa.Integer))
    op.add_column("chunks", sa.Column("section", sa.String(300)))
    op.add_column("chunks", sa.Column("image_key", sa.String(500)))

    op.create_table(
        "conversations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("bot_id", pg.UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("visitor_id", sa.String(64)),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_bot_id", "conversations", ["bot_id"])
    op.create_index("ix_conversations_owner_id", "conversations", ["owner_id"])
    op.create_index("ix_conversations_bot_last", "conversations", ["bot_id", "last_message_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bot_id", pg.UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("rewritten_query", sa.Text),
        sa.Column("sources", pg.JSONB, nullable=False, server_default="[]"),
        sa.Column("provider", sa.String(20)),
        sa.Column("model", sa.String(100)),
        sa.Column("first_token_ms", sa.Integer),
        sa.Column("total_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_bot_id", "messages", ["bot_id"])
    op.create_index("ix_messages_owner_id", "messages", ["owner_id"])

    # RLS on with no policies = deny-all for API roles (Supabase anon/authenticated via PostgREST).
    # The app connects as the table owner, which bypasses RLS, so nothing changes for the API.
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY")
    op.drop_table("messages")
    op.drop_table("conversations")
    for c in ("image_key", "section", "page", "kind"):
        op.drop_column("chunks", c)
    op.drop_index("ix_documents_bot_sha256", "documents")
    for c in ("n_images", "n_pages", "storage_key", "sha256", "content_type"):
        op.drop_column("documents", c)
