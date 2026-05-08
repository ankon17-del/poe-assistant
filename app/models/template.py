from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TemplateGroup(Base):
    __tablename__ = "template_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items = relationship("TemplateItem", back_populates="template_group", cascade="all, delete-orphan")
    user_templates = relationship("UserTemplate", back_populates="template_group")


class TemplateItem(Base):
    __tablename__ = "template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_group_id: Mapped[int] = mapped_column(ForeignKey("template_groups.id", ondelete="CASCADE"), index=True)
    item_name: Mapped[str] = mapped_column(String(255), index=True)
    item_type: Mapped[str] = mapped_column(String(64), default="item")
    default_threshold: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    priority: Mapped[int] = mapped_column(default=100)

    template_group = relationship("TemplateGroup", back_populates="items")


class UserTemplate(Base):
    __tablename__ = "user_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    template_group_id: Mapped[int] = mapped_column(ForeignKey("template_groups.id", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="user_templates")
    template_group = relationship("TemplateGroup", back_populates="user_templates")

