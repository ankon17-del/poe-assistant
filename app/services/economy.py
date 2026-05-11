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
from app.services.leagues import LeagueService


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
    paused_watchers: list[CurrencyWatcherSummary]


@dataclass(frozen=True)
class TopWatchedCurrencySummary:
    item_name: str
    active_watchers: int
    paused_watchers: int

    @property
    def total_watchers(self) -> int:
        return self.active_watchers + self.paused_watchers


@dataclass(frozen=True)
class EconomyOverviewSummary:
    total_active_currency_alerts: int
    total_paused_currency_alerts: int
    top_watched_currencies: list[TopWatchedCurrencySummary]
    nearest_alerts: list["NearestCurrencyAlertSummary"]
    market_movements: list["MarketMovementSummary"]


@dataclass(frozen=True)
class NearestCurrencyAlertSummary:
    tracked_item_id: int
    item_name: str
    game: str
    league_name: str
    current_value: Decimal
    target_price: Decimal
    target_currency: str
    progress_ratio: Decimal


@dataclass(frozen=True)
class MarketMovementSummary:
    game: str
    league_name: str
    currency_code: str
    current_value: Decimal
    previous_value: Decimal
    delta_value: Decimal
    delta_ratio: Decimal


class EconomyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.currency_market_source = CurrencyMarketSource()

    async def get_user_economy_summary(self, user: User) -> list[LeagueEconomySummary]:
        currency_items = await self._list_active_currency_watchers(user)
        paused_currency_items = await self._list_paused_currency_watchers(user)
        grouped: dict[tuple[str, str], list[TrackedItem]] = {}
        paused_grouped: dict[tuple[str, str], list[TrackedItem]] = {}
        for item in currency_items:
            if not item.league:
                continue
            grouped.setdefault((item.league.realm, item.league.name), []).append(item)
        for item in paused_currency_items:
            if not item.league:
                continue
            paused_grouped.setdefault((item.league.realm, item.league.name), []).append(item)

        for realm, league_name in await self._baseline_league_pairs():
            grouped.setdefault((realm, league_name), [])
            paused_grouped.setdefault((realm, league_name), [])

        summaries: list[LeagueEconomySummary] = []
        all_keys = sorted(set(grouped.keys()) | set(paused_grouped.keys()), key=lambda entry: (entry[0], entry[1]))
        for game, league_name in all_keys:
            items = grouped.get((game, league_name), [])
            paused_items = paused_grouped.get((game, league_name), [])
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
                    paused_watchers=[
                        CurrencyWatcherSummary(
                            tracked_item_id=item.id,
                            item_name=item.item_name,
                            target_price=Decimal(item.target_price),
                            target_currency=item.target_currency,
                        )
                        for item in paused_items
                    ],
                )
            )

        return summaries

    async def get_user_economy_dashboard(
        self,
        user: User,
    ) -> tuple[list[LeagueEconomySummary], EconomyOverviewSummary]:
        summaries = await self.get_user_economy_summary(user)
        active_items = await self._list_active_currency_watchers(user)
        paused_items = await self._list_paused_currency_watchers(user)

        counters: dict[str, dict[str, int]] = {}
        for item in active_items:
            entry = counters.setdefault(item.item_name, {"active": 0, "paused": 0})
            entry["active"] += 1
        for item in paused_items:
            entry = counters.setdefault(item.item_name, {"active": 0, "paused": 0})
            entry["paused"] += 1

        top_watched = [
            TopWatchedCurrencySummary(
                item_name=item_name,
                active_watchers=counts["active"],
                paused_watchers=counts["paused"],
            )
            for item_name, counts in sorted(
                counters.items(),
                key=lambda item: (-(item[1]["active"] + item[1]["paused"]), -item[1]["active"], item[0].lower()),
            )[:5]
        ]

        overview = EconomyOverviewSummary(
            total_active_currency_alerts=len(active_items),
            total_paused_currency_alerts=len(paused_items),
            top_watched_currencies=top_watched,
            nearest_alerts=self._build_nearest_alerts(summaries),
            market_movements=self._build_market_movements(summaries),
        )
        return summaries, overview

    def _build_nearest_alerts(self, summaries: list[LeagueEconomySummary]) -> list[NearestCurrencyAlertSummary]:
        nearest: list[NearestCurrencyAlertSummary] = []
        for summary in summaries:
            snapshot = summary.exchange_snapshot
            if snapshot is None:
                continue

            for watcher in summary.active_watchers:
                current_value = self._resolve_currency_value(
                    item_name=watcher.item_name,
                    target_currency=watcher.target_currency,
                    rates=snapshot.rates,
                )
                if current_value is None or watcher.target_price <= 0:
                    continue

                progress_ratio = current_value / watcher.target_price
                nearest.append(
                    NearestCurrencyAlertSummary(
                        tracked_item_id=watcher.tracked_item_id,
                        item_name=watcher.item_name,
                        game=summary.game,
                        league_name=summary.league_name,
                        current_value=current_value,
                        target_price=watcher.target_price,
                        target_currency=watcher.target_currency,
                        progress_ratio=progress_ratio,
                    )
                )

        nearest.sort(key=lambda item: (item.progress_ratio, item.current_value), reverse=True)
        return nearest[:5]

    def _build_market_movements(self, summaries: list[LeagueEconomySummary]) -> list[MarketMovementSummary]:
        movements: list[MarketMovementSummary] = []
        for summary in summaries:
            current_snapshot = summary.exchange_snapshot
            if current_snapshot is None:
                continue

            previous_snapshot = self.currency_market_source.get_previous_exchange_snapshot(
                league_name=summary.league_name,
                game=summary.game,
            )
            if previous_snapshot is None:
                continue

            for currency_code in ("div", "ex"):
                current_value = current_snapshot.rates.get(currency_code)
                previous_value = previous_snapshot.rates.get(currency_code)
                if current_value in {None, Decimal("0")} or previous_value in {None, Decimal("0")}:
                    continue

                delta_value = current_value - previous_value
                delta_ratio = delta_value / previous_value
                movements.append(
                    MarketMovementSummary(
                        game=summary.game,
                        league_name=summary.league_name,
                        currency_code=currency_code,
                        current_value=current_value,
                        previous_value=previous_value,
                        delta_value=delta_value,
                        delta_ratio=delta_ratio,
                    )
                )

        movements.sort(key=lambda item: abs(item.delta_ratio), reverse=True)
        return movements[:6]

    @staticmethod
    def _resolve_currency_value(
        *,
        item_name: str,
        target_currency: str,
        rates: dict[str, Decimal],
    ) -> Decimal | None:
        normalized_name = item_name.strip().lower()
        normalized_currency = target_currency.strip().lower()

        chaos_value: Decimal | None = None
        if normalized_name == "chaos orb":
            chaos_value = Decimal("1")
        elif normalized_name == "exalted orb":
            chaos_value = rates.get("ex")
        elif normalized_name == "divine orb":
            chaos_value = rates.get("div")
        else:
            return None

        if chaos_value is None:
            return None

        if normalized_currency == "chaos":
            return chaos_value
        if normalized_currency == "ex":
            ex_rate = rates.get("ex")
            if ex_rate in {None, Decimal("0")}:
                return None
            return chaos_value / ex_rate
        if normalized_currency == "div":
            div_rate = rates.get("div")
            if div_rate in {None, Decimal("0")}:
                return None
            return chaos_value / div_rate
        return None

    async def _baseline_league_pairs(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        league_service = LeagueService(self.session)
        for realm in ("poe1", "poe2"):
            options = await league_service.list_selection_options(realm)
            if options:
                pairs.append((realm, options[0].name))
                continue

            defaults = LeagueService.DEFAULT_LEAGUES.get(realm, [])
            if defaults:
                pairs.append((realm, defaults[0]))

        default_game = "poe2" if "poe2" in self.settings.default_league_name.lower() else "poe1"
        default_pair = (default_game, self.settings.default_league_name)
        if default_pair not in pairs:
            pairs.append(default_pair)

        return pairs

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

    async def _list_paused_currency_watchers(self, user: User) -> list[TrackedItem]:
        result = await self.session.scalars(
            select(TrackedItem)
            .where(
                TrackedItem.user_id == user.id,
                TrackedItem.is_active.is_(True),
                TrackedItem.notify_enabled.is_(False),
                TrackedItem.item_type == "currency",
                TrackedItem.target_price.is_not(None),
                TrackedItem.trade_url.is_(None),
            )
            .options(selectinload(TrackedItem.league))
            .order_by(TrackedItem.league_id.asc(), TrackedItem.created_at.desc())
        )
        return list(result)
