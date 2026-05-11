"""add template target currencies

Revision ID: 0005_template_target_currencies
Revises: 0004_tracking_realms_and_units
Create Date: 2026-05-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_template_target_currencies"
down_revision = "0004_tracking_realms_and_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "template_items",
        sa.Column("default_target_currency", sa.String(length=16), nullable=False, server_default="ex"),
    )


def downgrade() -> None:
    op.drop_column("template_items", "default_target_currency")
