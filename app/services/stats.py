from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.sale_event import SaleEvent
from app.models.sales_stats import SalesStats
from app.models.tracked_item import TrackedItem
from app.models.user import User
from app.services.leagues import LeagueService


@dataclass(frozen=True)
class StatsSummary:
    total_sales: int
    total_currency: Decimal
    daily_sales: int
    daily_currency: Decimal
    active_trackers: int
    active_currency_alerts: int
    active_trade_url_watchers: int
    active_item_watchers: int
    poe1_trackers: int
    poe2_trackers: int


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
        tracked_items = await self._list_active_tracked_items(user)

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
            active_trackers=len(tracked_items),
            active_currency_alerts=sum(
                1
                for item in tracked_items
                if item.item_type == "currency" and item.target_price is not None and item.notify_enabled
            ),
            active_trade_url_watchers=sum(1 for item in tracked_items if item.trade_url),
            active_item_watchers=sum(1 for item in tracked_items if item.item_type == "item" and not item.trade_url),
            poe1_trackers=sum(1 for item in tracked_items if item.league and item.league.realm == "poe1"),
            poe2_trackers=sum(1 for item in tracked_items if item.league and item.league.realm == "poe2"),
        )

    async def _list_active_tracked_items(self, user: User) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(
                TrackedItem.user_id == user.id,
                TrackedItem.is_active.is_(True),
            )
            .options(selectinload(TrackedItem.league))
            .order_by(TrackedItem.id.asc())
        )
        return list(result)
