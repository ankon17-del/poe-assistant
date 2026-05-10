from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.integrations.currency_market_source import CurrencyMarketSource, PriceSnapshotDTO
from app.integrations.tracking_source import SaleEventDTO, TrackingRequest

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeApiPaths:
    search_url: str
    shared_query_url: str
    fetch_url: str
    referer: str


class PoeTradeClient:
    def __init__(self):
        self.settings = get_settings()
        self.currency_market_source = CurrencyMarketSource()

    async def poll_sales(self, trade_url: str, item_name: str | None = None) -> list[SaleEventDTO]:
        return []

    async def get_price_snapshot(self, request: TrackingRequest) -> PriceSnapshotDTO | None:
        if not request.trade_url or not request.league_name:
            return None

        paths = self._resolve_trade_paths(request.trade_url)
        if not paths:
            return None

        headers = self._build_headers(paths.referer)
        try:
            async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
                shared_query = await self._fetch_shared_query(client, paths.shared_query_url)
                if not shared_query:
                    return None

                search_payload = await self._execute_search(client, paths.search_url, shared_query)
                result_ids = search_payload.get("result", [])
                if not isinstance(result_ids, list) or not result_ids:
                    return None

                listings = await self._fetch_listings(
                    client=client,
                    fetch_url=paths.fetch_url,
                    search_id=str(search_payload.get("id", "")),
                    result_ids=result_ids[:10],
                )
        except httpx.HTTPError:
            logger.exception("Failed to poll trade market for %s", request.trade_url)
            return None

        if not listings:
            return None

        exchange_rates = await self.currency_market_source.get_exchange_rates(
            league_name=request.league_name,
            game=request.game,
        )

        best_listing, best_quote_values = self._select_best_listing(
            listings=listings,
            exchange_rates=exchange_rates or {},
            target_currency=(request.target_currency or "chaos").lower(),
        )
        if not best_listing or not best_quote_values:
            return None

        listing_price = best_listing.get("listing", {}).get("price", {})
        amount = Decimal(str(listing_price.get("amount")))
        currency = self._normalize_currency(str(listing_price.get("currency", "")))
        if not currency:
            return None

        item_payload = best_listing.get("item", {})
        listing_payload = best_listing.get("listing", {})
        item_name = request.item_name or item_payload.get("name") or item_payload.get("typeLine") or "Unknown Item"
        if item_payload.get("name") and item_payload.get("typeLine"):
            item_name = f"{item_payload['name']} {item_payload['typeLine']}".strip()

        return PriceSnapshotDTO(
            item_name=item_name,
            market_value=amount,
            unit=currency,
            quote_values=best_quote_values,
            league_name=request.league_name,
            source="pathofexile.trade",
            observed_at=datetime.now(UTC),
            raw_payload={
                "trade_url": request.trade_url,
                "listing": listing_payload,
                "item": item_payload,
            },
        )

    async def _fetch_shared_query(self, client: httpx.AsyncClient, shared_query_url: str) -> dict[str, Any] | None:
        response = await client.get(shared_query_url)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or "query" not in payload:
            return None
        return payload

    async def _execute_search(
        self,
        client: httpx.AsyncClient,
        search_url: str,
        shared_query: dict[str, Any],
    ) -> dict[str, Any]:
        response = await client.post(search_url, json=shared_query)
        response.raise_for_status()
        return response.json()

    async def _fetch_listings(
        self,
        *,
        client: httpx.AsyncClient,
        fetch_url: str,
        search_id: str,
        result_ids: list[str],
    ) -> list[dict[str, Any]]:
        response = await client.get(fetch_url + "/".join(["", ",".join(result_ids)]), params={"query": search_id})
        response.raise_for_status()
        payload = response.json()
        results = payload.get("result", [])
        return results if isinstance(results, list) else []

    def _select_best_listing(
        self,
        *,
        listings: list[dict[str, Any]],
        exchange_rates: dict[str, Decimal],
        target_currency: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Decimal] | None]:
        best_listing = None
        best_quote_values = None
        best_value = None

        for listing in listings:
            price_payload = listing.get("listing", {}).get("price", {})
            amount_raw = price_payload.get("amount")
            currency_raw = price_payload.get("currency")
            if amount_raw is None or currency_raw is None:
                continue

            normalized_currency = self._normalize_currency(str(currency_raw))
            if not normalized_currency:
                continue

            amount = Decimal(str(amount_raw))
            quote_values = self._build_quote_values(amount, normalized_currency, exchange_rates)
            comparison_value = quote_values.get(target_currency)
            if comparison_value is None:
                continue

            if best_value is None or comparison_value < best_value:
                best_value = comparison_value
                best_listing = listing
                best_quote_values = quote_values

        return best_listing, best_quote_values

    @staticmethod
    def _build_quote_values(
        amount: Decimal,
        listing_currency: str,
        exchange_rates: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        if not exchange_rates:
            return {listing_currency: amount}

        chaos_rate = exchange_rates.get(listing_currency)
        if chaos_rate in {None, Decimal("0")}:
            return {listing_currency: amount}

        chaos_value = amount * chaos_rate
        quote_values = {"chaos": chaos_value}

        ex_rate = exchange_rates.get("ex")
        div_rate = exchange_rates.get("div")
        if ex_rate not in {None, Decimal("0")}:
            quote_values["ex"] = chaos_value / ex_rate
        if div_rate not in {None, Decimal("0")}:
            quote_values["div"] = chaos_value / div_rate

        return quote_values

    @staticmethod
    def _normalize_currency(raw_currency: str) -> str | None:
        normalized = raw_currency.strip().lower()
        mapping = {
            "chaos": "chaos",
            "c": "chaos",
            "exa": "ex",
            "exalted": "ex",
            "ex": "ex",
            "div": "div",
            "divine": "div",
        }
        return mapping.get(normalized)

    @staticmethod
    def _resolve_trade_paths(trade_url: str) -> TradeApiPaths | None:
        parsed = urlparse(trade_url)
        if not parsed.netloc.endswith("pathofexile.com"):
            return None

        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 4 or segments[1] != "search":
            return None

        if segments[0] == "trade":
            if len(segments) != 4:
                return None
            league_name, query_id = segments[2], segments[3]
            search_url = f"https://www.pathofexile.com/api/trade/search/{league_name}"
            shared_query_url = f"{search_url}/{query_id}"
            fetch_url = "https://www.pathofexile.com/api/trade/fetch"
            return TradeApiPaths(
                search_url=search_url,
                shared_query_url=shared_query_url,
                fetch_url=fetch_url,
                referer=trade_url,
            )

        if segments[0] == "trade2":
            if len(segments) != 5:
                return None
            realm_name, league_name, query_id = segments[2], segments[3], segments[4]
            search_url = f"https://www.pathofexile.com/api/trade2/search/{realm_name}/{league_name}"
            shared_query_url = f"{search_url}/{query_id}"
            fetch_url = f"https://www.pathofexile.com/api/trade2/fetch/{realm_name}"
            return TradeApiPaths(
                search_url=search_url,
                shared_query_url=shared_query_url,
                fetch_url=fetch_url,
                referer=trade_url,
            )

        return None

    def _build_headers(self, referer: str) -> dict[str, str]:
        return {
            "User-Agent": self.settings.poe_api_user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
            "Origin": "https://www.pathofexile.com",
            "Content-Type": "application/json",
        }
