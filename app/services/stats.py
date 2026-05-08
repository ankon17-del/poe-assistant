from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.sale_event import SaleEvent
from app.models.sales_stats import SalesStats
from app.models.user import User
from app.services.leagues import LeagueService


@dataclass(frozen=True)
class StatsSummary:
    total_sales: int
    total_currency: Decimal
    daily_sales: int
    daily_currency: Decimal


class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_user_stats(self, user: User, league_name: str | None = None) -> SalesStats:
        league = await LeagueService(self.session).get_or_create(league_name or self.settings.default_league_name)
        return await self.get_or_create_stats(user_id=user.id, league_id=league.id)

    async def get_or_create_stats(self, user_id: int, league_id: int) -> SalesStats:
        stats = await self.session.scalar(
            select(SalesStats).where(SalesStats.user_id == user_id, SalesStats.league_id == league_id)
        )
        if stats:
            return stats

        stats = SalesStats(user_id=user_id, league_id=league_id)
        self.session.add(stats)
        await self.session.flush()
        return stats

    async def register_sale(self, user: User, league_id: int, amount: Decimal | None) -> SalesStats:
        stats = await self.get_or_create_stats(user_id=user.id, league_id=league_id)
        stats.total_sales += 1
        stats.total_currency = Decimal(stats.total_currency or 0) + Decimal(amount or 0)
        return stats

    async def get_summary(self, user: User, league_name: str | None = None) -> StatsSummary:
        stats = await self.get_user_stats(user=user, league_name=league_name)
        league_id = stats.league_id
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        daily_sales = await self.session.scalar(
            select(func.count(SaleEvent.id)).where(
                SaleEvent.user_id == user.id,
                SaleEvent.league_id == league_id,
                SaleEvent.detected_at >= day_start,
            )
        )
        daily_currency = await self.session.scalar(
            select(func.coalesce(func.sum(SaleEvent.price_amount), 0)).where(
                SaleEvent.user_id == user.id,
                SaleEvent.league_id == league_id,
                SaleEvent.detected_at >= day_start,
            )
        )

        return StatsSummary(
            total_sales=stats.total_sales,
            total_currency=Decimal(stats.total_currency or 0),
            daily_sales=daily_sales or 0,
            daily_currency=Decimal(daily_currency or 0),
        )
