from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SalesStats(Base):
    __tablename__ = "sales_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id"), index=True)
    total_sales: Mapped[int] = mapped_column(default=0)
    total_currency: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="sales_stats")
    league = relationship("League", back_populates="sales_stats")

