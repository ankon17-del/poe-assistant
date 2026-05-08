"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    subscription_type = sa.Enum("free", "pro", name="subscription_type")
    notification_type = sa.Enum("sale", "price_alert", "system", name="notification_type")
    integration_type = sa.Enum("poe_trade", "poe_ninja", "funpay", name="integration_type")

    subscription_type.create(op.get_bind(), checkfirst=True)
    notification_type.create(op.get_bind(), checkfirst=True)
    integration_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("subscription_type", subscription_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "leagues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leagues_name", "leagues", ["name"], unique=True)

    op.create_table(
        "template_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_template_groups_category", "template_groups", ["category"], unique=False)
    op.create_index("ix_template_groups_name", "template_groups", ["name"], unique=True)

    op.create_table(
        "tracked_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("trade_url", sa.Text(), nullable=True),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("notify_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tracked_items_item_name", "tracked_items", ["item_name"], unique=False)
    op.create_index("ix_tracked_items_league_id", "tracked_items", ["league_id"], unique=False)
    op.create_index("ix_tracked_items_user_id", "tracked_items", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_type", notification_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)

    op.create_table(
        "sales_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id"), nullable=False),
        sa.Column("total_sales", sa.Integer(), nullable=False),
        sa.Column("total_currency", sa.Numeric(14, 2), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sales_stats_league_id", "sales_stats", ["league_id"], unique=False)
    op.create_index("ix_sales_stats_user_id", "sales_stats", ["user_id"], unique=False)

    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("integration_type", integration_type, nullable=False),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_integrations_user_id", "integrations", ["user_id"], unique=False)

    op.create_table(
        "template_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_group_id", sa.Integer(), sa.ForeignKey("template_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("item_type", sa.String(length=64), nullable=False),
        sa.Column("default_threshold", sa.Numeric(12, 2), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
    )
    op.create_index("ix_template_items_item_name", "template_items", ["item_name"], unique=False)
    op.create_index("ix_template_items_template_group_id", "template_items", ["template_group_id"], unique=False)

    op.create_table(
        "user_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_group_id", sa.Integer(), sa.ForeignKey("template_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_user_templates_template_group_id", "user_templates", ["template_group_id"], unique=False)
    op.create_index("ix_user_templates_user_id", "user_templates", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_templates_user_id", table_name="user_templates")
    op.drop_index("ix_user_templates_template_group_id", table_name="user_templates")
    op.drop_table("user_templates")
    op.drop_index("ix_template_items_template_group_id", table_name="template_items")
    op.drop_index("ix_template_items_item_name", table_name="template_items")
    op.drop_table("template_items")
    op.drop_index("ix_integrations_user_id", table_name="integrations")
    op.drop_table("integrations")
    op.drop_index("ix_sales_stats_user_id", table_name="sales_stats")
    op.drop_index("ix_sales_stats_league_id", table_name="sales_stats")
    op.drop_table("sales_stats")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_tracked_items_user_id", table_name="tracked_items")
    op.drop_index("ix_tracked_items_league_id", table_name="tracked_items")
    op.drop_index("ix_tracked_items_item_name", table_name="tracked_items")
    op.drop_table("tracked_items")
    op.drop_index("ix_template_groups_name", table_name="template_groups")
    op.drop_index("ix_template_groups_category", table_name="template_groups")
    op.drop_table("template_groups")
    op.drop_index("ix_leagues_name", table_name="leagues")
    op.drop_table("leagues")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")

    sa.Enum(name="integration_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="notification_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="subscription_type").drop(op.get_bind(), checkfirst=True)

