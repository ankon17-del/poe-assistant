from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.integrations.tracking_source import TrackingRequest
from app.models.tracked_item import TrackedItem
from app.models.user import User
from app.services.leagues import LeagueService


@dataclass(frozen=True)
class AddTrackingResult:
    item: TrackedItem
    action: str


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
        target_currency: str = "ex",
        league_name: str | None = None,
        game: str | None = None,
        existing_item_id: int | None = None,
        create_new: bool = False,
    ) -> AddTrackingResult:
        resolved_game = game or self._infer_game_from_league_name(league_name or self.settings.default_league_name)
        league = await LeagueService(self.session).get_or_create(
            league_name or self.settings.default_league_name,
            realm=resolved_game,
        )
        normalized_name = item_name.strip()
        normalized_trade_url = trade_url.strip() if trade_url else None
        resolved_item_type = self._resolve_item_type(normalized_name, item_type)
        normalized_target_currency = target_currency.lower()

        existing = None
        action = "created"
        if existing_item_id is not None:
            existing = await self.session.scalar(
                select(TrackedItem).where(TrackedItem.id == existing_item_id, TrackedItem.user_id == user.id)
            )
        elif not create_new:
            similar_items = await self.find_similar_items(
                user=user,
                league_id=league.id,
                item_name=normalized_name,
                trade_url=normalized_trade_url,
            )
            if len(similar_items) == 1:
                existing = similar_items[0]

        if existing:
            existing.item_type = resolved_item_type
            existing.trade_url = normalized_trade_url
            existing.target_price = target_price
            existing.target_currency = normalized_target_currency
            existing.notify_enabled = True
            existing.is_active = True
            action = "updated"
            return AddTrackingResult(item=existing, action=action)

        tracked_item = TrackedItem(
            user_id=user.id,
            league_id=league.id,
            item_name=normalized_name,
            item_type=resolved_item_type,
            trade_url=normalized_trade_url,
            target_price=target_price,
            target_currency=normalized_target_currency,
        )
        self.session.add(tracked_item)
        await self.session.flush()
        return AddTrackingResult(item=tracked_item, action=action)

    async def find_similar_items(
        self,
        user: User,
        league_id: int,
        item_name: str,
        trade_url: str | None,
    ) -> list[TrackedItem]:
        statement = (
            select(TrackedItem)
            .where(
                TrackedItem.user_id == user.id,
                TrackedItem.league_id == league_id,
                TrackedItem.item_name == item_name,
                TrackedItem.trade_url.is_(trade_url) if trade_url is None else TrackedItem.trade_url == trade_url,
            )
            .options(selectinload(TrackedItem.league))
            .order_by(TrackedItem.is_active.desc(), TrackedItem.created_at.desc(), TrackedItem.id.desc())
        )
        result = await self.session.scalars(statement)
        return list(result)

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

    async def reactivate_item(self, user: User, tracked_item_id: int) -> bool:
        tracked_item = await self.session.scalar(
            select(TrackedItem).where(TrackedItem.id == tracked_item_id, TrackedItem.user_id == user.id)
        )
        if not tracked_item or not tracked_item.is_active:
            return False

        if tracked_item.target_price is None:
            return False

        if tracked_item.notify_enabled:
            return False

        tracked_item.notify_enabled = True
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
        game = tracked_item.league.realm if tracked_item.league else None

        return TrackingRequest(
            tracked_item_id=tracked_item.id,
            item_name=tracked_item.item_name,
            item_type=tracked_item.item_type,
            trade_url=tracked_item.trade_url,
            target_price=tracked_item.target_price,
            target_currency=tracked_item.target_currency,
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

    @staticmethod
    def _infer_game_from_league_name(league_name: str) -> str:
        return "poe2" if "poe2" in league_name.lower() else "poe1"
