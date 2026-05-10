from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
import re
from typing import Any

import httpx
import logging

from app.integrations.tracking_source import TrackingRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceSnapshotDTO:
    item_name: str
    market_value: Decimal
    unit: str
    quote_values: dict[str, Decimal]
    league_name: str | None
    source: str
    observed_at: datetime
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class ExchangeRateSnapshotDTO:
    league_name: str | None
    game: str | None
    source: str
    rates: dict[str, Decimal]
    observed_at: datetime


class CurrencyMarketSource:
    poe_ninja_base_url = "https://poe.ninja"
    poe_watch_base_url = "https://api.poe.watch"
    orbwatch_base_url = "https://orbwatch.trade"
    poe2_dev_currency_url = "https://www.poe2.dev/calculators/currency"

    async def get_exchange_rates(self, league_name: str, game: str | None) -> dict[str, Decimal] | None:
        snapshot = await self.get_exchange_snapshot(league_name=league_name, game=game)
        return snapshot.rates if snapshot else None

    async def get_exchange_snapshot(
        self,
        league_name: str,
        game: str | None,
    ) -> ExchangeRateSnapshotDTO | None:
        if not league_name:
            return None

        if game == "poe2":
            return await self._get_poe2_exchange_snapshot(league_name)

        return await self._get_poe1_exchange_snapshot(league_name)

    async def get_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        if request.item_type != "currency" or not request.league_name:
            return None

        if request.game == "poe2":
            return await self._get_poe2_currency_price(request)

        return await self._get_poe1_currency_price(request)

    async def _get_poe2_currency_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        live_snapshot = await self._get_poe2_currency_price_from_orbwatch(request)
        if live_snapshot is not None:
            return live_snapshot

        return await self._get_poe2_currency_price_from_poe2_dev(request)

    async def _get_poe2_currency_price_from_orbwatch(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        try:
            async with httpx.AsyncClient(base_url=self.orbwatch_base_url, timeout=30.0) as client:
                response = await client.get(
                    "/api/currency/market-data",
                    params={"mode": "buy", "realm": request.league_name},
                    headers={"Referer": "https://orbwatch.trade/"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed to fetch POE2 currency market data for %s", request.league_name)
            return None

        currencies = payload.get("data", {}).get("currencies", [])
        if not isinstance(currencies, list) or not currencies:
            return None

        target_entry = self._find_currency_entry(currencies, request.item_name)
        if not target_entry:
            return None

        exalted_entry = self._find_currency_entry(currencies, "Exalted Orb") or self._find_currency_entry(
            currencies, "exalted"
        )
        market_value = self._extract_orbwatch_equivalent(target_entry, exalted_entry)
        if market_value is None:
            return None

        return PriceSnapshotDTO(
            item_name=request.item_name,
            market_value=market_value,
            unit="ex",
            quote_values=self._build_quote_values_from_orbwatch(currencies, target_entry, market_value),
            league_name=request.league_name,
            source="orbwatch.trade",
            observed_at=datetime.now(UTC),
            raw_payload=target_entry,
        )

    async def _get_poe2_currency_price_from_poe2_dev(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.poe2_dev_currency_url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError:
            logger.exception("Failed to fetch POE2 fallback currency data for %s", request.league_name)
            return None

        values_by_name = self._extract_poe2_dev_chaos_values(html)
        if not values_by_name:
            return None

        target_chaos = self._find_named_value(values_by_name, request.item_name)
        exalted_chaos = self._find_named_value(values_by_name, "Exalted Orb")
        if target_chaos is None or exalted_chaos in {None, Decimal("0")}:
            return None

        market_value = target_chaos / exalted_chaos
        divine_chaos = self._find_named_value(values_by_name, "Divine Orb")
        return PriceSnapshotDTO(
            item_name=request.item_name,
            market_value=market_value,
            unit="ex",
            quote_values=self._build_quote_values_from_chaos(
                target_chaos=target_chaos,
                exalted_chaos=exalted_chaos,
                divine_chaos=divine_chaos,
            ),
            league_name=request.league_name,
            source="poe2.dev",
            observed_at=datetime.now(UTC),
            raw_payload={
                "item_name": request.item_name,
                "chaos_value": str(target_chaos),
                "exalted_chaos_value": str(exalted_chaos),
            },
        )

    async def _get_poe1_currency_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        try:
            payload = await self._fetch_poe1_currency_overview(request.league_name)
        except (httpx.HTTPError, ValueError):
            logger.warning("Primary POE1 currency source unavailable for %s, trying poe.watch", request.league_name)
            return await self._get_poe1_currency_price_from_poe_watch(request)

        lines = payload.get("lines", [])
        if not isinstance(lines, list) or not lines:
            logger.warning(
                "Primary POE1 currency source returned no lines for %s, trying poe.watch",
                request.league_name,
            )
            return await self._get_poe1_currency_price_from_poe_watch(request)

        target_entry = self._find_currency_entry(lines, request.item_name)
        if not target_entry:
            logger.warning(
                "Primary POE1 currency source could not match %s in %s, trying poe.watch",
                request.item_name,
                request.league_name,
            )
            return await self._get_poe1_currency_price_from_poe_watch(request)

        market_value = self._extract_decimal(target_entry.get("chaosEquivalent"))
        if market_value is None:
            logger.warning(
                "Primary POE1 currency source returned no chaosEquivalent for %s in %s, trying poe.watch",
                request.item_name,
                request.league_name,
            )
            return await self._get_poe1_currency_price_from_poe_watch(request)

        divine_entry = self._find_currency_entry(lines, "Divine Orb")
        exalted_entry = self._find_currency_entry(lines, "Exalted Orb")
        divine_chaos = self._extract_decimal(divine_entry.get("chaosEquivalent")) if divine_entry else None
        exalted_chaos = self._extract_decimal(exalted_entry.get("chaosEquivalent")) if exalted_entry else None

        return PriceSnapshotDTO(
            item_name=request.item_name,
            market_value=market_value,
            unit="chaos",
            quote_values=self._build_quote_values_from_chaos(
                target_chaos=market_value,
                exalted_chaos=exalted_chaos,
                divine_chaos=divine_chaos,
            ),
            league_name=request.league_name,
            source="poe.ninja",
            observed_at=datetime.now(UTC),
            raw_payload=target_entry,
        )

    async def _get_poe1_exchange_snapshot(self, league_name: str) -> ExchangeRateSnapshotDTO | None:
        try:
            payload = await self._fetch_poe1_currency_overview(league_name)
        except (httpx.HTTPError, ValueError):
            logger.warning("Primary POE1 exchange rates unavailable for %s, trying poe.watch", league_name)
            return await self._get_poe1_exchange_snapshot_from_poe_watch(league_name)

        lines = payload.get("lines", [])
        if not isinstance(lines, list) or not lines:
            logger.warning(
                "Primary POE1 exchange source returned no lines for %s, trying poe.watch",
                league_name,
            )
            return await self._get_poe1_exchange_snapshot_from_poe_watch(league_name)

        divine_entry = self._find_currency_entry(lines, "Divine Orb")
        exalted_entry = self._find_currency_entry(lines, "Exalted Orb")
        divine_chaos = self._extract_decimal(divine_entry.get("chaosEquivalent")) if divine_entry else None
        exalted_chaos = self._extract_decimal(exalted_entry.get("chaosEquivalent")) if exalted_entry else None

        rates = {"chaos": Decimal("1")}
        if exalted_chaos not in {None, Decimal("0")}:
            rates["ex"] = exalted_chaos
        if divine_chaos not in {None, Decimal("0")}:
            rates["div"] = divine_chaos
        if len(rates) == 1:
            logger.warning(
                "Primary POE1 exchange source returned no divine/exalted rates for %s, trying poe.watch",
                league_name,
            )
            return await self._get_poe1_exchange_snapshot_from_poe_watch(league_name)
        return ExchangeRateSnapshotDTO(
            league_name=league_name,
            game="poe1",
            source="poe.ninja",
            rates=rates,
            observed_at=datetime.now(UTC),
        )

    async def _get_poe1_currency_price_from_poe_watch(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        try:
            lines = await self._fetch_poe_watch_currency_lines(request.league_name, [request.item_name, "Divine Orb", "Exalted Orb"])
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed to fetch POE1 currency fallback data from poe.watch for %s", request.league_name)
            return None

        target_entry = lines.get(request.item_name.lower())
        if not target_entry:
            return None

        market_value = self._extract_decimal(target_entry.get("mean")) or self._extract_decimal(target_entry.get("median"))
        if market_value is None:
            return None

        divine_entry = lines.get("divine orb")
        exalted_entry = lines.get("exalted orb")
        divine_chaos = None
        exalted_chaos = None
        if divine_entry:
            divine_chaos = self._extract_decimal(divine_entry.get("mean")) or self._extract_decimal(divine_entry.get("median"))
        if exalted_entry:
            exalted_chaos = self._extract_decimal(exalted_entry.get("mean")) or self._extract_decimal(exalted_entry.get("median"))

        return PriceSnapshotDTO(
            item_name=request.item_name,
            market_value=market_value,
            unit="chaos",
            quote_values=self._build_quote_values_from_chaos(
                target_chaos=market_value,
                exalted_chaos=exalted_chaos,
                divine_chaos=divine_chaos,
            ),
            league_name=request.league_name,
            source="poe.watch",
            observed_at=datetime.now(UTC),
            raw_payload=target_entry,
        )

    async def _get_poe1_exchange_snapshot_from_poe_watch(self, league_name: str) -> ExchangeRateSnapshotDTO | None:
        try:
            lines = await self._fetch_poe_watch_currency_lines(league_name, ["Divine Orb", "Exalted Orb"])
        except (httpx.HTTPError, ValueError):
            logger.warning("POE1 exchange rate fallback unavailable for %s", league_name)
            return None

        divine_entry = lines.get("divine orb")
        exalted_entry = lines.get("exalted orb")
        divine_chaos = None
        exalted_chaos = None
        if divine_entry:
            divine_chaos = self._extract_decimal(divine_entry.get("mean")) or self._extract_decimal(divine_entry.get("median"))
        if exalted_entry:
            exalted_chaos = self._extract_decimal(exalted_entry.get("mean")) or self._extract_decimal(exalted_entry.get("median"))

        rates = {"chaos": Decimal("1")}
        if exalted_chaos not in {None, Decimal("0")}:
            rates["ex"] = exalted_chaos
        if divine_chaos not in {None, Decimal("0")}:
            rates["div"] = divine_chaos
        if len(rates) == 1:
            return None

        return ExchangeRateSnapshotDTO(
            league_name=league_name,
            game="poe1",
            source="poe.watch",
            rates=rates,
            observed_at=datetime.now(UTC),
        )

    async def _fetch_poe1_currency_overview(self, league_name: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.poe_ninja_base_url, timeout=30.0) as client:
            candidate_params = [
                {"league": league_name, "type": "Currency", "language": "en"},
                {"league": league_name, "type": "Currency", "date": date.today().isoformat(), "language": "en"},
                {
                    "league": league_name,
                    "type": "Currency",
                    "date": (date.today() - timedelta(days=1)).isoformat(),
                    "language": "en",
                },
            ]

            last_response: httpx.Response | None = None
            for params in candidate_params:
                response = await client.get(
                    "/api/data/currencyoverview",
                    params=params,
                )
                last_response = response
                if response.status_code >= 400:
                    continue

                payload = response.json()
                lines = payload.get("lines", [])
                if isinstance(lines, list) and lines:
                    return payload

            if last_response is None:
                raise httpx.HTTPError("No response received from poe.ninja currency overview")

            last_response.raise_for_status()
            return last_response.json()

    async def _get_poe2_exchange_snapshot(self, league_name: str) -> ExchangeRateSnapshotDTO | None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self.poe2_dev_currency_url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError:
            logger.warning("POE2 exchange rates unavailable")
            return None

        values_by_name = self._extract_poe2_dev_chaos_values(html)
        if not values_by_name:
            return None

        rates = {"chaos": Decimal("1")}
        exalted_chaos = self._find_named_value(values_by_name, "Exalted Orb")
        divine_chaos = self._find_named_value(values_by_name, "Divine Orb")
        if exalted_chaos not in {None, Decimal("0")}:
            rates["ex"] = exalted_chaos
        if divine_chaos not in {None, Decimal("0")}:
            rates["div"] = divine_chaos
        return ExchangeRateSnapshotDTO(
            league_name=league_name,
            game="poe2",
            source="poe2.dev",
            rates=rates,
            observed_at=datetime.now(UTC),
        )

    async def _fetch_poe_watch_currency_lines(
        self,
        league_name: str,
        item_names: list[str],
    ) -> dict[str, dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.poe_watch_base_url, timeout=30.0) as client:
            itemdata_response = await client.get("/itemdata")
            itemdata_response.raise_for_status()
            itemdata = itemdata_response.json()

            wanted = {name.lower() for name in item_names}
            items_by_name = {
                str(entry.get("name", "")).lower(): entry
                for entry in itemdata
                if isinstance(entry, dict)
                and str(entry.get("name", "")).lower() in wanted
            }

            results: dict[str, dict[str, Any]] = {}
            for item_name in wanted:
                item_entry = items_by_name.get(item_name)
                if not item_entry:
                    continue

                item_id = item_entry.get("id")
                if item_id is None:
                    continue

                item_response = await client.get("/item", params={"id": item_id})
                item_response.raise_for_status()
                payload = item_response.json()
                leagues = payload.get("leagues", [])
                if not isinstance(leagues, list):
                    continue

                match = next(
                    (
                        league_entry
                        for league_entry in leagues
                        if isinstance(league_entry, dict)
                        and str(league_entry.get("name", "")).lower() == league_name.lower()
                    ),
                    None,
                )
                if match:
                    results[item_name] = match

            return results

    def _find_currency_entry(self, entries: list[dict[str, Any]], requested_name: str) -> dict[str, Any] | None:
        requested_keys = self._candidate_keys(requested_name)
        for entry in entries:
            entry_keys = set()
            for key in ("name", "id", "currencyTypeName", "detailsId"):
                value = entry.get(key)
                if isinstance(value, str):
                    entry_keys.update(self._candidate_keys(value))

            if requested_keys & entry_keys:
                return entry
        return None

    def _candidate_keys(self, value: str) -> set[str]:
        normalized = self._normalize_name(value)
        aliases = {normalized}
        alias_map = {
            "divineorb": {"divine", "div", "divorb"},
            "exaltedorb": {"exalted", "exa", "ex", "exorb"},
            "chaosorb": {"chaos", "c", "chaosorb"},
        }
        aliases.update(alias_map.get(normalized, set()))
        return aliases

    def _find_named_value(self, values_by_name: dict[str, Decimal], requested_name: str) -> Decimal | None:
        requested_keys = self._candidate_keys(requested_name)
        for entry_name, value in values_by_name.items():
            if requested_keys & self._candidate_keys(entry_name):
                return value
        return None

    def _extract_poe2_dev_chaos_values(self, html: str) -> dict[str, Decimal]:
        text = self._html_to_text(html)
        pattern = re.compile(
            r"(?P<name>[A-Z][A-Za-z'0-9\- ]+?)\s+(?P<value>\d+(?:\.\d+)?)\s*c\b",
            re.IGNORECASE,
        )
        values: dict[str, Decimal] = {}
        for match in pattern.finditer(text):
            name = " ".join(match.group("name").split())
            value = self._extract_decimal(match.group("value"))
            if name and value is not None:
                values[name] = value
        return values

    @staticmethod
    def _html_to_text(html: str) -> str:
        without_scripts = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
        without_styles = re.sub(r"<style.*?>.*?</style>", " ", without_scripts, flags=re.IGNORECASE | re.DOTALL)
        without_tags = re.sub(r"<[^>]+>", " ", without_styles)
        normalized = re.sub(r"\s+", " ", unescape(without_tags))
        return normalized

    @staticmethod
    def _normalize_name(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    def _extract_orbwatch_equivalent(
        self,
        entry: dict[str, Any],
        exalted_entry: dict[str, Any] | None,
    ) -> Decimal | None:
        direct_fields = ("chaosEquivalent", "exaltedEquivalent", "value", "market", "price")
        for field in direct_fields:
            value = self._extract_decimal(entry.get(field))
            if value is not None:
                return value

        if exalted_entry:
            entry_market = self._extract_decimal(entry.get("market"))
            exalted_market = self._extract_decimal(exalted_entry.get("market"))
            if entry_market is not None and exalted_market not in {None, Decimal("0")}:
                return entry_market / exalted_market

        nested_numeric = self._find_first_numeric(entry, {"chaosEquivalent", "exaltedEquivalent", "market", "value"})
        if nested_numeric is not None:
            return nested_numeric

        return None

    def _build_quote_values_from_orbwatch(
        self,
        currencies: list[dict[str, Any]],
        target_entry: dict[str, Any],
        ex_value: Decimal,
    ) -> dict[str, Decimal]:
        quote_values = {"ex": ex_value}
        exalted_entry = self._find_currency_entry(currencies, "Exalted Orb")
        divine_entry = self._find_currency_entry(currencies, "Divine Orb")
        chaos_entry = self._find_currency_entry(currencies, "Chaos Orb")

        target_market = self._extract_decimal(target_entry.get("market"))
        exalted_market = self._extract_decimal(exalted_entry.get("market")) if exalted_entry else None
        divine_market = self._extract_decimal(divine_entry.get("market")) if divine_entry else None
        chaos_market = self._extract_decimal(chaos_entry.get("market")) if chaos_entry else None

        if target_market is not None and exalted_market not in {None, Decimal("0")}:
            quote_values["ex"] = target_market / exalted_market
        if target_market is not None and divine_market not in {None, Decimal("0")}:
            quote_values["div"] = target_market / divine_market
        if target_market is not None and chaos_market not in {None, Decimal("0")}:
            quote_values["chaos"] = target_market / chaos_market
        return quote_values

    @staticmethod
    def _build_quote_values_from_chaos(
        target_chaos: Decimal,
        exalted_chaos: Decimal | None,
        divine_chaos: Decimal | None,
    ) -> dict[str, Decimal]:
        quote_values = {"chaos": target_chaos}
        if exalted_chaos not in {None, Decimal("0")}:
            quote_values["ex"] = target_chaos / exalted_chaos
        if divine_chaos not in {None, Decimal("0")}:
            quote_values["div"] = target_chaos / divine_chaos
        return quote_values

    def _find_first_numeric(self, payload: Any, preferred_keys: set[str]) -> Decimal | None:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in preferred_keys:
                    parsed = self._extract_decimal(value)
                    if parsed is not None:
                        return parsed
                nested = self._find_first_numeric(value, preferred_keys)
                if nested is not None:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._find_first_numeric(item, preferred_keys)
                if nested is not None:
                    return nested
        return None

    @staticmethod
    def _extract_decimal(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float, str)):
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                return None
        return None
