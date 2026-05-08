from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TrackedItem(Base):
    __tablename__ = "tracked_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(255), index=True)
    item_type: Mapped[str] = mapped_column(String(64), default="item")
    trade_url: Mapped[str | None] = mapped_column(Text)
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="tracked_items")
    league = relationship("League", back_populates="tracked_items")
    sale_events = relationship("SaleEvent", back_populates="tracked_item")
