from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SubscriptionType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    subscription_type: Mapped[SubscriptionType] = mapped_column(
        Enum(SubscriptionType, name="subscription_type"),
        default=SubscriptionType.free,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tracked_items = relationship("TrackedItem", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    sale_events = relationship("SaleEvent", back_populates="user")
    sales_stats = relationship("SalesStats", back_populates="user")
    integrations = relationship("Integration", back_populates="user")
    user_templates = relationship("UserTemplate", back_populates="user")
