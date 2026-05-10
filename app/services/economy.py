from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.integrations.currency_market_source import CurrencyMarketSource, ExchangeRateSnapshotDTO
from app.integrations.tracking_source import TrackingRequest
from app.models.tracked_item import TrackedItem
from app.models.user import User


@dataclass(frozen=True)
class CurrencyWatcherSummary:
    tracked_item_id: int
    item_name: str
    target_price: Decimal
    target_currency: str


@dataclass(frozen=True)
class LeagueEconomySummary:
    game: str
    league_name: str
    exchange_snapshot: ExchangeRateSnapshotDTO | None
    active_watchers: list[CurrencyWatcherSummary]


class EconomyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.currency_market_source = CurrencyMarketSource()

    async def get_user_economy_summary(self, user: User) -> list[LeagueEconomySummary]:
        currency_items = await self._list_active_currency_watchers(user)
        grouped: dict[tuple[str, str], list[TrackedItem]] = {}
        for item in currency_items:
            if not item.league:
                continue
            grouped.setdefault((item.league.realm, item.league.name), []).append(item)

        if not grouped:
            fallback_game = "poe2" if "poe2" in self.settings.default_league_name.lower() else "poe1"
            grouped[(fallback_game, self.settings.default_league_name)] = []

        summaries: list[LeagueEconomySummary] = []
        for (game, league_name), items in sorted(grouped.items(), key=lambda entry: (entry[0][0], entry[0][1])):
            exchange_snapshot = await self.currency_market_source.get_exchange_snapshot(league_name=league_name, game=game)
            if exchange_snapshot is None:
                exchange_snapshot = await self._build_snapshot_from_currency_prices(league_name=league_name, game=game)
            summaries.append(
                LeagueEconomySummary(
                    game=game,
                    league_name=league_name,
                    exchange_snapshot=exchange_snapshot,
                    active_watchers=[
                        CurrencyWatcherSummary(
                            tracked_item_id=item.id,
                            item_name=item.item_name,
                            target_price=Decimal(item.target_price),
                            target_currency=item.target_currency,
                        )
                        for item in items
                    ],
                )
            )

        return summaries

    async def _build_snapshot_from_currency_prices(
        self,
        *,
        league_name: str,
        game: str,
    ) -> ExchangeRateSnapshotDTO | None:
        divine_snapshot = await self.currency_market_source.get_price(
            TrackingRequest(
                tracked_item_id=0,
                item_name="Divine Orb",
                item_type="currency",
                trade_url=None,
                target_price=None,
                target_currency="chaos",
                league_name=league_name,
                game=game,
            )
        )
        exalted_snapshot = await self.currency_market_source.get_price(
            TrackingRequest(
                tracked_item_id=0,
                item_name="Exalted Orb",
                item_type="currency",
                trade_url=None,
                target_price=None,
                target_currency="chaos",
                league_name=league_name,
                game=game,
            )
        )

        rates = {"chaos": Decimal("1")}
        source = None
        if exalted_snapshot and "chaos" in exalted_snapshot.quote_values:
            rates["ex"] = exalted_snapshot.quote_values["chaos"]
            source = exalted_snapshot.source
        if divine_snapshot and "chaos" in divine_snapshot.quote_values:
            rates["div"] = divine_snapshot.quote_values["chaos"]
            source = divine_snapshot.source

        if len(rates) == 1:
            return None

        return ExchangeRateSnapshotDTO(
            league_name=league_name,
            game=game,
            source=source or "price-snapshot",
            rates=rates,
            observed_at=datetime.now(UTC),
        )

    async def _list_active_currency_watchers(self, user: User) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(
                TrackedItem.user_id == user.id,
                TrackedItem.is_active.is_(True),
                TrackedItem.notify_enabled.is_(True),
                TrackedItem.item_type == "currency",
                TrackedItem.target_price.is_not(None),
                TrackedItem.trade_url.is_(None),
            )
            .options(selectinload(TrackedItem.league))
            .order_by(TrackedItem.league_id.asc(), TrackedItem.created_at.desc())
        )
        return list(result)
