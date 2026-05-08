from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SaleEvent(Base):
    __tablename__ = "sale_events"
    __table_args__ = (UniqueConstraint("tracked_item_id", "external_id", name="uq_sale_events_tracked_external"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tracked_item_id: Mapped[int] = mapped_column(ForeignKey("tracked_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    item_name: Mapped[str] = mapped_column(String(255), index=True)
    price_text: Mapped[str] = mapped_column(String(255))
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    price_currency: Mapped[str | None] = mapped_column(String(32))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tracked_item = relationship("TrackedItem", back_populates="sale_events")
    user = relationship("User", back_populates="sale_events")
    league = relationship("League")
