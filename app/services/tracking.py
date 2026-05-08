from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.integrations.tracking_source import TrackingRequest
from app.models.tracked_item import TrackedItem
from app.models.user import User
from app.services.leagues import LeagueService


class TrackingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def add_item(
        self,
        user: User,
        item_name: str,
        item_type: str = "item",
        trade_url: str | None = None,
        target_price: Decimal | None = None,
        league_name: str | None = None,
    ) -> TrackedItem:
        league = await LeagueService(self.session).get_or_create(league_name or self.settings.default_league_name)
        tracked_item = TrackedItem(
            user_id=user.id,
            league_id=league.id,
            item_name=item_name.strip(),
            item_type=item_type,
            trade_url=trade_url,
            target_price=target_price,
        )
        self.session.add(tracked_item)
        await self.session.flush()
        return tracked_item

    async def list_items(self, user: User) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(TrackedItem.user_id == user.id, TrackedItem.is_active.is_(True))
            .order_by(TrackedItem.created_at.desc())
        )
        return list(result)

    async def remove_item(self, user: User, tracked_item_id: int) -> bool:
        tracked_item = await self.session.scalar(
            select(TrackedItem).where(TrackedItem.id == tracked_item_id, TrackedItem.user_id == user.id)
        )
        if not tracked_item:
            return False

        tracked_item.is_active = False
        return True

    async def list_items_for_polling(self) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(
                TrackedItem.is_active.is_(True),
                TrackedItem.notify_enabled.is_(True),
                TrackedItem.trade_url.is_not(None),
            )
            .options(selectinload(TrackedItem.user), selectinload(TrackedItem.league))
            .order_by(TrackedItem.id.asc())
        )
        return list(result)

    @staticmethod
    def build_tracking_request(tracked_item: TrackedItem) -> TrackingRequest:
        league_name = tracked_item.league.name if tracked_item.league else None
        game = None
        if league_name:
            game = "poe2" if "poe2" in league_name.lower() else "poe1"

        return TrackingRequest(
            tracked_item_id=tracked_item.id,
            item_name=tracked_item.item_name,
            trade_url=tracked_item.trade_url,
            league_name=league_name,
            game=game,
        )
