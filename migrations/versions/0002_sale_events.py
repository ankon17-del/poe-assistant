"""sale events

Revision ID: 0002_sale_events
Revises: 0001_initial_schema
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_sale_events"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sale_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tracked_item_id", sa.Integer(), sa.ForeignKey("tracked_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("price_text", sa.String(length=255), nullable=False),
        sa.Column("price_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("price_currency", sa.String(length=32), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("sold_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tracked_item_id", "external_id", name="uq_sale_events_tracked_external"),
    )
    op.create_index("ix_sale_events_tracked_item_id", "sale_events", ["tracked_item_id"], unique=False)
    op.create_index("ix_sale_events_user_id", "sale_events", ["user_id"], unique=False)
    op.create_index("ix_sale_events_league_id", "sale_events", ["league_id"], unique=False)
    op.create_index("ix_sale_events_item_name", "sale_events", ["item_name"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sale_events_item_name", table_name="sale_events")
    op.drop_index("ix_sale_events_league_id", table_name="sale_events")
    op.drop_index("ix_sale_events_user_id", table_name="sale_events")
    op.drop_index("ix_sale_events_tracked_item_id", table_name="sale_events")
    op.drop_table("sale_events")
