"""add league realms and tracking threshold units

Revision ID: 0004_tracking_realms_and_units
Revises: 0003_poe_oauth_integrations
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_tracking_realms_and_units"
down_revision = "0003_poe_oauth_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leagues",
        sa.Column("realm", sa.String(length=16), nullable=False, server_default="poe2"),
    )
    op.create_index("ix_leagues_realm", "leagues", ["realm"], unique=False)
    op.drop_index("ix_leagues_name", table_name="leagues")
    op.create_index("ix_leagues_name", "leagues", ["name"], unique=False)
    op.create_unique_constraint("uq_leagues_name_realm", "leagues", ["name", "realm"])

    op.add_column(
        "tracked_items",
        sa.Column("target_currency", sa.String(length=16), nullable=False, server_default="ex"),
    )


def downgrade() -> None:
    op.drop_column("tracked_items", "target_currency")

    op.drop_constraint("uq_leagues_name_realm", "leagues", type_="unique")
    op.drop_index("ix_leagues_name", table_name="leagues")
    op.create_index("ix_leagues_name", "leagues", ["name"], unique=True)
    op.drop_index("ix_leagues_realm", table_name="leagues")
    op.drop_column("leagues", "realm")
