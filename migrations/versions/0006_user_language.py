"""add user language

Revision ID: 0006_user_language
Revises: 0005_template_target_currencies
Create Date: 2026-05-13 21:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_user_language"
down_revision = "0005_template_target_currencies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "language")
