from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx


@dataclass(frozen=True)
class MarketPriceEntry:
    name: str
    chaos_value: Decimal
    source: str


class StashMarketSource:
    poe_ninja_base_url = "https://poe.ninja"
    _cache: dict[tuple[str, str, str], dict[str, MarketPriceEntry]] = {}

    async def get_price_index(
        self,
        *,
        league_name: str,
        stash_type: str,
    ) -> tuple[dict[str, MarketPriceEntry], str] | None:
        endpoint_type_pairs = self._stash_type_mappings().get(stash_type)
        if not endpoint_type_pairs:
            return None

        merged: dict[str, MarketPriceEntry] = {}
        source_labels: list[str] = []

        for endpoint, market_type in endpoint_type_pairs:
            result = await self._fetch_market_type(
                league_name=league_name,
                endpoint=endpoint,
                market_type=market_type,
            )
            if result is None:
                continue

            price_index, source_label = result
            source_labels.append(source_label)
            merged.update(price_index)

        if not merged:
            return None

        unique_sources = list(dict.fromkeys(source_labels))
        return merged, ", ".join(unique_sources)

    async def _fetch_market_type(
        self,
        *,
        league_name: str,
        endpoint: str,
        market_type: str,
    ) -> tuple[dict[str, MarketPriceEntry], str] | None:
        cache_key = (league_name, endpoint, market_type)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached, "poe.ninja (cached)"

        async with httpx.AsyncClient(base_url=self.poe_ninja_base_url, timeout=30.0) as client:
            last_payload: dict[str, Any] | None = None
            last_candidate = league_name
            for candidate_league in self._league_candidates(league_name):
                response = await client.get(
                    "/poe1/api/economy/exchange/current/overview",
                    params={"league": candidate_league, "type": market_type},
                )
                if response.status_code >= 400:
                    continue
                payload = response.json()
                last_payload = payload
                index = self._build_price_index(payload)
                if index:
                    self._cache[cache_key] = index
                    source = "poe.ninja"
                    if candidate_league.lower() != league_name.lower():
                        source = f"poe.ninja ({candidate_league} fallback)"
                    return index, source
                last_candidate = candidate_league

        if last_payload:
            index = self._build_price_index(last_payload)
            if index:
                self._cache[cache_key] = index
                source = "poe.ninja"
                if last_candidate.lower() != league_name.lower():
                    source = f"poe.ninja ({last_candidate} fallback)"
                return index, source
        return None

    @staticmethod
    def _league_candidates(league_name: str) -> list[str]:
        candidates = [league_name]
        if league_name.lower() != "standard":
            candidates.append("Standard")
        return candidates

    @classmethod
    def _build_price_index(cls, payload: dict[str, Any]) -> dict[str, MarketPriceEntry]:
        index: dict[str, MarketPriceEntry] = {}
        items = payload.get("items", [])
        lines = payload.get("lines", [])
        if not isinstance(items, list) or not isinstance(lines, list):
            return index

        items_by_id = {
            str(item.get("id")): item
            for item in items
            if isinstance(item, dict) and item.get("id") is not None
        }
        for line in lines:
            if not isinstance(line, dict):
                continue
            item_name = cls._resolve_line_name(line, items_by_id)
            chaos_value = cls._extract_chaos_value(line)
            if not item_name or chaos_value in {None, Decimal("0")}:
                continue
            normalized = cls._normalize_name(item_name)
            index[normalized] = MarketPriceEntry(name=item_name, chaos_value=chaos_value, source="poe.ninja")
        return index

    @staticmethod
    def _resolve_line_name(line: dict[str, Any], items_by_id: dict[str, dict[str, Any]]) -> str | None:
        line_id = line.get("id")
        if line_id is not None:
            item = items_by_id.get(str(line_id))
            if item:
                value = item.get("name")
                if isinstance(value, str) and value.strip():
                    return value.strip()
        for key in ("name", "currencyTypeName", "baseType", "detailsId"):
            value = line.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_chaos_value(line: dict[str, Any]) -> Decimal | None:
        for key in ("primaryValue", "chaosValue", "chaosEquivalent"):
            value = line.get(key)
            if value is None:
                continue
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError):
                continue
        return None

    @staticmethod
    def _normalize_name(value: str) -> str:
        return "".join(ch for ch in value.lower() if ch.isalnum())

    @staticmethod
    def _stash_type_mappings() -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "CurrencyStash": (("exchange", "Currency"),),
            "FragmentStash": (("exchange", "Fragment"), ("exchange", "Scarab")),
            "EssenceStash": (("exchange", "Essence"),),
            "DivinationCardStash": (("exchange", "DivinationCard"),),
            "MapStash": (("exchange", "Map"), ("exchange", "UniqueMap")),
        }
