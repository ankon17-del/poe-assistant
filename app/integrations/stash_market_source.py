from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
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
                for params in self._candidate_params(candidate_league, market_type):
                    response = await client.get(f"/api/data/{endpoint}", params=params)
                    if response.status_code >= 400:
                        continue
                    payload = response.json()
                    last_payload = payload
                    lines = payload.get("lines", [])
                    if isinstance(lines, list) and lines:
                        index = self._build_price_index(lines)
                        if index:
                            self._cache[cache_key] = index
                            source = "poe.ninja"
                            if candidate_league.lower() != league_name.lower():
                                source = f"poe.ninja ({candidate_league} fallback)"
                            return index, source
                    last_candidate = candidate_league

        if last_payload:
            lines = last_payload.get("lines", [])
            if isinstance(lines, list) and lines:
                index = self._build_price_index(lines)
                if index:
                    self._cache[cache_key] = index
                    source = "poe.ninja"
                    if last_candidate.lower() != league_name.lower():
                        source = f"poe.ninja ({last_candidate} fallback)"
                    return index, source
        return None

    @staticmethod
    def _candidate_params(league_name: str, market_type: str) -> list[dict[str, str]]:
        today = date.today()
        return [
            {"league": league_name, "type": market_type, "language": "en"},
            {"league": league_name, "type": market_type, "date": today.isoformat(), "language": "en"},
            {"league": league_name, "type": market_type, "date": (today - timedelta(days=1)).isoformat(), "language": "en"},
        ]

    @staticmethod
    def _league_candidates(league_name: str) -> list[str]:
        candidates = [league_name]
        if league_name.lower() != "standard":
            candidates.append("Standard")
        return candidates

    @classmethod
    def _build_price_index(cls, lines: list[dict[str, Any]]) -> dict[str, MarketPriceEntry]:
        index: dict[str, MarketPriceEntry] = {}
        for line in lines:
            item_name = cls._resolve_line_name(line)
            chaos_value = cls._extract_chaos_value(line)
            if not item_name or chaos_value in {None, Decimal("0")}:
                continue
            normalized = cls._normalize_name(item_name)
            index[normalized] = MarketPriceEntry(name=item_name, chaos_value=chaos_value, source="poe.ninja")
        return index

    @staticmethod
    def _resolve_line_name(line: dict[str, Any]) -> str | None:
        for key in ("name", "currencyTypeName", "baseType", "detailsId"):
            value = line.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _extract_chaos_value(line: dict[str, Any]) -> Decimal | None:
        for key in ("chaosValue", "chaosEquivalent"):
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
            "CurrencyStash": (("currencyoverview", "Currency"),),
            "FragmentStash": (("currencyoverview", "Fragment"),),
            "EssenceStash": (("itemoverview", "Essence"),),
            "DivinationCardStash": (("itemoverview", "DivinationCard"),),
            "MapStash": (("itemoverview", "Map"), ("itemoverview", "UniqueMap")),
        }
