from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class League(Base):
    __tablename__ = "leagues"
    __table_args__ = (UniqueConstraint("name", "realm", name="uq_leagues_name_realm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    realm: Mapped[str] = mapped_column(String(16), default="poe2", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tracked_items = relationship("TrackedItem", back_populates="league")
    sales_stats = relationship("SalesStats", back_populates="league")
