from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
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
    league_name: str | None
    source: str
    observed_at: datetime
    raw_payload: dict[str, Any]


class CurrencyMarketSource:
    poe_ninja_base_url = "https://poe.ninja"
    orbwatch_base_url = "https://orbwatch.trade"

    async def get_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        if request.item_type != "currency" or not request.league_name:
            return None

        if request.game == "poe2":
            return await self._get_poe2_currency_price(request)

        return await self._get_poe1_currency_price(request)

    async def _get_poe2_currency_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
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
            league_name=request.league_name,
            source="orbwatch.trade",
            observed_at=datetime.now(UTC),
            raw_payload=target_entry,
        )

    async def _get_poe1_currency_price(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        try:
            async with httpx.AsyncClient(base_url=self.poe_ninja_base_url, timeout=30.0) as client:
                response = await client.get(
                    "/api/data/currencyoverview",
                    params={
                        "league": request.league_name,
                        "type": "Currency",
                        "date": date.today().isoformat(),
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            logger.exception("Failed to fetch POE1 currency market data for %s", request.league_name)
            return None

        lines = payload.get("lines", [])
        if not isinstance(lines, list) or not lines:
            return None

        target_entry = self._find_currency_entry(lines, request.item_name)
        if not target_entry:
            return None

        market_value = self._extract_decimal(target_entry.get("chaosEquivalent"))
        if market_value is None:
            return None

        return PriceSnapshotDTO(
            item_name=request.item_name,
            market_value=market_value,
            unit="chaos",
            league_name=request.league_name,
            source="poe.ninja",
            observed_at=datetime.now(UTC),
            raw_payload=target_entry,
        )

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
