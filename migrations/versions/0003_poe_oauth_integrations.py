"""poe oauth integrations

Revision ID: 0003_poe_oauth_integrations
Revises: 0002_sale_events
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_poe_oauth_integrations"
down_revision = "0002_sale_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE integration_type ADD VALUE IF NOT EXISTS 'poe_oauth'")
    op.add_column("integrations", sa.Column("access_token", sa.Text(), nullable=True))
    op.add_column("integrations", sa.Column("refresh_token", sa.Text(), nullable=True))
    op.add_column("integrations", sa.Column("scopes", sa.Text(), nullable=True))
    op.add_column("integrations", sa.Column("external_account_id", sa.String(length=128), nullable=True))
    op.add_column("integrations", sa.Column("external_account_name", sa.String(length=128), nullable=True))
    op.add_column("integrations", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("integrations", "expires_at")
    op.drop_column("integrations", "external_account_name")
    op.drop_column("integrations", "external_account_id")
    op.drop_column("integrations", "scopes")
    op.drop_column("integrations", "refresh_token")
    op.drop_column("integrations", "access_token")
