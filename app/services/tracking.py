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
        normalized_name = item_name.strip()
        normalized_trade_url = trade_url.strip() if trade_url else None
        resolved_item_type = self._resolve_item_type(normalized_name, item_type)

        existing = await self.session.scalar(
            select(TrackedItem).where(
                TrackedItem.user_id == user.id,
                TrackedItem.league_id == league.id,
                TrackedItem.item_name == normalized_name,
                TrackedItem.trade_url.is_(normalized_trade_url) if normalized_trade_url is None else TrackedItem.trade_url == normalized_trade_url,
            )
        )
        if existing:
            existing.item_type = resolved_item_type
            existing.target_price = target_price
            existing.notify_enabled = True
            existing.is_active = True
            return existing

        tracked_item = TrackedItem(
            user_id=user.id,
            league_id=league.id,
            item_name=normalized_name,
            item_type=resolved_item_type,
            trade_url=normalized_trade_url,
            target_price=target_price,
        )
        self.session.add(tracked_item)
        await self.session.flush()
        return tracked_item

    async def list_items(self, user: User) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(TrackedItem.user_id == user.id, TrackedItem.is_active.is_(True))
            .options(selectinload(TrackedItem.league))
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
                TrackedItem.trade_url.is_not(None) | TrackedItem.target_price.is_not(None),
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
            item_type=tracked_item.item_type,
            trade_url=tracked_item.trade_url,
            target_price=tracked_item.target_price,
            league_name=league_name,
            game=game,
        )

    @staticmethod
    def _resolve_item_type(item_name: str, fallback_type: str) -> str:
        if fallback_type != "item":
            return fallback_type

        normalized = "".join(ch for ch in item_name.lower() if ch.isalnum())
        known_currency_keys = {
            "divineorb",
            "exaltedorb",
            "chaosorb",
            "regalorb",
            "orbofalchemy",
            "vaalorb",
            "orbofannulment",
            "orbofchance",
            "orbofaugmentation",
            "orboftransmutation",
            "orbofalteration",
        }
        return "currency" if normalized in known_currency_keys else fallback_type
