from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import IntegrationType
from app.models.user import User
from app.services.integrations import IntegrationService
from app.services.poe_oauth import PoeOAuthService


class PoeAccountError(RuntimeError):
    pass


class PoeAccountNotConnectedError(PoeAccountError):
    pass


class PoeAccountScopeError(PoeAccountError):
    pass


class PoeAccountApiError(PoeAccountError):
    pass


class PoeAccountRateLimitError(PoeAccountApiError):
    def __init__(self, message: str, retry_after_seconds: int | None = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class AccountSnapshot:
    account_name: str | None
    profile_name: str | None
    poe1_leagues: tuple[str, ...]
    poe1_primary_league: str | None
    poe1_character_count: int
    poe2_character_count: int
    poe1_stash_note: str | None


@dataclass(frozen=True)
class StashItemSummary:
    name: str
    quantity: int
    entry_count: int


@dataclass(frozen=True)
class StashTabOverview:
    id: str
    name: str
    type: str
    item_count: int
    is_folder: bool
    is_special: bool
    priority_score: int
    priority_reason: str | None
    preview_items: tuple[str, ...]
    item_summaries: tuple[StashItemSummary, ...]


@dataclass(frozen=True)
class StashSnapshot:
    league_name: str
    total_tabs: int
    folder_tabs: int
    special_tabs: int
    empty_tabs: int
    total_items: int
    sample_tabs: tuple[str, ...]
    liquid_tabs: tuple[StashTabOverview, ...]
    dense_tabs: tuple[StashTabOverview, ...]
    dump_tabs: tuple[StashTabOverview, ...]
    tabs: tuple[StashTabOverview, ...]
    failed_tabs: int = 0
    is_partial: bool = False
    is_cached: bool = False


class PoeAccountApiService:
    _logger = logging.getLogger(__name__)
    _snapshot_cache_ttl = timedelta(seconds=45)
    _detail_fetch_concurrency = 2
    _snapshot_cache: dict[tuple[int, str], tuple[datetime, StashSnapshot]] = {}
    _special_type_labels = {
        "CurrencyStash": "Currency",
        "FragmentStash": "Fragments",
        "MapStash": "Maps",
        "DivinationCardStash": "Div Cards",
        "EssenceStash": "Essences",
        "DelveStash": "Delve",
        "BlightStash": "Blight",
        "DeliriumStash": "Delirium",
        "UltimatumStash": "Ultimatum",
        "GemStash": "Gems",
        "FlaskStash": "Flasks",
        "UniqueStash": "Uniques",
    }
    _liquid_type_bonus = {
        "CurrencyStash": 120,
        "FragmentStash": 110,
        "EssenceStash": 100,
        "DivinationCardStash": 95,
        "MapStash": 85,
        "DelveStash": 70,
        "BlightStash": 70,
        "DeliriumStash": 65,
        "UltimatumStash": 65,
        "UniqueStash": 50,
    }
    _normal_tab_types = {"NormalStash", "PremiumStash", "QuadStash", "Folder"}

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.integrations = IntegrationService(session)
        self.oauth = PoeOAuthService()

    async def get_account_snapshot(self, user: User) -> AccountSnapshot:
        integration = await self._get_connected_integration(user)
        profile = await self._authorized_get_json(user, integration, "/profile")
        poe1_leagues_payload = await self._authorized_get_json(user, integration, "/account/leagues")
        poe1_characters_payload = await self._authorized_get_json(user, integration, "/character")
        poe2_characters_payload = await self._authorized_get_json(user, integration, "/character/poe2")

        poe1_leagues = tuple(
            league.get("name")
            for league in poe1_leagues_payload.get("leagues", [])
            if league.get("name")
        )

        return AccountSnapshot(
            account_name=integration.external_account_name,
            profile_name=profile.get("name"),
            poe1_leagues=poe1_leagues,
            poe1_primary_league=self.choose_primary_poe1_league(poe1_leagues, self.settings.default_league_name),
            poe1_character_count=len(poe1_characters_payload.get("characters", [])),
            poe2_character_count=len(poe2_characters_payload.get("characters", [])),
            poe1_stash_note="Сейчас этот stash-view работает по PoE1 account stashes. PoE2 лига пока не участвует в выборе тайника.",
        )

    async def get_stash_snapshot(self, user: User, league_name: str | None = None) -> StashSnapshot:
        integration = await self._get_connected_integration(user)
        leagues_payload = await self._authorized_get_json(user, integration, "/account/leagues")
        leagues = tuple(
            league.get("name")
            for league in leagues_payload.get("leagues", [])
            if league.get("name")
        )
        selected_league = league_name or self.choose_primary_poe1_league(leagues, self.settings.default_league_name)
        if not selected_league:
            raise PoeAccountApiError("No PoE1 league is available for stash access.")

        cached_snapshot = self._get_cached_snapshot(user.id, selected_league)
        if cached_snapshot is not None:
            return cached_snapshot

        stashes_payload = await self._authorized_get_json(user, integration, f"/stash/{selected_league}")
        listed_stashes = stashes_payload.get("stashes", [])
        if not isinstance(listed_stashes, list):
            raise PoeAccountApiError("PoE API returned an unexpected stash list payload.")

        folder_tabs = sum(
            1
            for stash in listed_stashes
            if self._is_folder_tab(stash)
        )
        sample_tabs = tuple(
            self._normalize_tab_name(stash)
            for stash in listed_stashes[:5]
        )

        leaf_tabs = [stash for stash in listed_stashes if not self._is_folder_tab(stash)]
        semaphore = asyncio.Semaphore(self._detail_fetch_concurrency)
        detail_results = await asyncio.gather(
            *(
                self._load_tab_overview(
                    user=user,
                    integration=integration,
                    league_name=selected_league,
                    listed_stash=stash,
                    semaphore=semaphore,
                )
                for stash in leaf_tabs
            ),
            return_exceptions=True,
        )

        tab_overviews: list[StashTabOverview] = []
        failed_tabs = 0
        for listed_stash, result in zip(leaf_tabs, detail_results):
            if isinstance(result, Exception):
                failed_tabs += 1
                self._logger.warning(
                    "Failed to load stash tab detail league=%s tab=%s error=%s",
                    selected_league,
                    self._normalize_tab_name(listed_stash),
                    result,
                )
                tab_overviews.append(self._build_tab_overview_from_listing(listed_stash, ()))
                continue
            tab_overviews.append(result)

        special_tabs = sum(1 for tab in tab_overviews if tab.is_special)
        empty_tabs = sum(1 for tab in tab_overviews if tab.item_count == 0)
        total_items = sum(tab.item_count for tab in tab_overviews)

        liquid_tabs = tuple(
            sorted(
                [tab for tab in tab_overviews if tab.priority_reason],
                key=lambda tab: (-tab.priority_score, -tab.item_count, tab.name),
            )[:4]
        )
        dense_tabs = tuple(
            sorted(
                [tab for tab in tab_overviews if tab.item_count > 0],
                key=lambda tab: (-tab.item_count, -tab.priority_score, tab.name),
            )[:4]
        )
        dump_tabs = tuple(
            sorted(
                [
                    tab
                    for tab in tab_overviews
                    if not tab.is_special and tab.item_count >= 40
                ],
                key=lambda tab: (-tab.item_count, tab.name),
            )[:4]
        )

        snapshot = StashSnapshot(
            league_name=selected_league,
            total_tabs=len(tab_overviews),
            folder_tabs=folder_tabs,
            special_tabs=special_tabs,
            empty_tabs=empty_tabs,
            total_items=total_items,
            sample_tabs=sample_tabs,
            liquid_tabs=liquid_tabs,
            dense_tabs=dense_tabs,
            dump_tabs=dump_tabs,
            tabs=tuple(tab_overviews),
            failed_tabs=failed_tabs,
            is_partial=failed_tabs > 0,
        )
        if failed_tabs > 0 and cached_snapshot is not None:
            return replace(cached_snapshot, is_cached=True)

        if failed_tabs == 0:
            self._store_cached_snapshot(user.id, selected_league, snapshot)

        return snapshot

    async def _authorized_get_json(self, user: User, integration, path: str) -> dict[str, Any]:
        token = await self._ensure_access_token(user, integration)
        response = await self._request_json(path, token)
        if response.status_code != 401:
            return response.json()

        if not integration.refresh_token:
            raise PoeAccountApiError("PoE access token expired and no refresh token is available.")

        refreshed = await self.oauth.refresh_access_token(integration.refresh_token)
        updated = await self.integrations.upsert_oauth_tokens(
            user=user,
            integration_type=IntegrationType.poe_oauth,
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token,
            scopes=refreshed.scope,
            external_account_id=refreshed.sub,
            external_account_name=refreshed.username or integration.external_account_name,
            expires_in=refreshed.expires_in,
        )
        retry_response = await self._request_json(path, updated.access_token or "")
        if retry_response.status_code == 401:
            raise PoeAccountApiError("PoE API still returns 401 after token refresh.")
        return retry_response.json()

    async def _request_json(self, path: str, access_token: str) -> httpx.Response:
        async with httpx.AsyncClient(base_url=self.settings.poe_api_base_url, timeout=30.0) as client:
            response = await client.get(
                path,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "User-Agent": self.settings.poe_api_user_agent,
                },
            )
        if response.status_code == 403:
            raise PoeAccountScopeError(f"PoE API rejected {path} with 403. The connected token likely lacks a required scope.")
        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            retry_after_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            raise PoeAccountRateLimitError(
                f"PoE API rate-limited {path} with HTTP 429.",
                retry_after_seconds=retry_after_seconds,
            )
        if response.status_code not in (200, 401):
            raise PoeAccountApiError(f"PoE API request failed for {path}: HTTP {response.status_code}")
        return response

    async def _ensure_access_token(self, user: User, integration) -> str:
        access_token = integration.access_token or ""
        if not access_token:
            raise PoeAccountApiError("Connected PoE integration has no access token.")

        expires_at = integration.expires_at
        if expires_at is None:
            return access_token

        refresh_at = expires_at - timedelta(minutes=5)
        now = datetime.now(UTC)
        if now < refresh_at:
            return access_token

        if not integration.refresh_token:
            return access_token

        refreshed = await self.oauth.refresh_access_token(integration.refresh_token)
        updated = await self.integrations.upsert_oauth_tokens(
            user=user,
            integration_type=IntegrationType.poe_oauth,
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token,
            scopes=refreshed.scope,
            external_account_id=refreshed.sub,
            external_account_name=refreshed.username or integration.external_account_name,
            expires_in=refreshed.expires_in,
        )
        return updated.access_token or access_token

    async def _get_connected_integration(self, user: User):
        integration = await self.integrations.get_by_type(user, IntegrationType.poe_oauth)
        if integration is None:
            raise PoeAccountNotConnectedError("PoE account is not connected.")
        return integration

    async def _fetch_stash_detail(
        self,
        user: User,
        integration,
        league_name: str,
        listed_stash: dict[str, Any],
    ) -> dict[str, Any]:
        stash_id = listed_stash.get("id")
        if not stash_id:
            return listed_stash

        parent_id = listed_stash.get("parent")
        if parent_id:
            path = f"/stash/{league_name}/{parent_id}/{stash_id}"
        else:
            path = f"/stash/{league_name}/{stash_id}"
        return await self._authorized_get_json(user, integration, path)

    async def _load_tab_overview(
        self,
        *,
        user: User,
        integration,
        league_name: str,
        listed_stash: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> StashTabOverview:
        async with semaphore:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    detail = await self._fetch_stash_detail(user, integration, league_name, listed_stash)
                    stash_payload = detail.get("stash") if isinstance(detail, dict) and "stash" in detail else detail
                    items = stash_payload.get("items", []) if isinstance(stash_payload, dict) else []
                    return self._build_tab_overview_from_listing(listed_stash, items)
                except PoeAccountRateLimitError as exc:
                    last_error = exc
                    if attempt == 2:
                        break
                    delay_seconds = exc.retry_after_seconds or (attempt + 1)
                    await asyncio.sleep(max(delay_seconds, 1))
                except PoeAccountApiError as exc:
                    last_error = exc
                    break
            raise last_error or PoeAccountApiError("Unknown stash detail loading error.")

    def _build_tab_overview_from_listing(
        self,
        listed_stash: dict[str, Any],
        items: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> StashTabOverview:
        raw_type = str(listed_stash.get("type") or "Unknown")
        name = self._normalize_tab_name(listed_stash)
        item_count = len(items)
        is_special = raw_type not in self._normal_tab_types
        preview_items = tuple(self._format_item_preview(item) for item in list(items)[:3])
        item_summaries = self._build_item_summaries(items)
        priority_score = item_count + self._liquid_type_bonus.get(raw_type, 0)
        priority_reason = self._priority_reason(raw_type)

        return StashTabOverview(
            id=str(listed_stash.get("id") or ""),
            name=name,
            type=raw_type,
            item_count=item_count,
            is_folder=self._is_folder_tab(listed_stash),
            is_special=is_special,
            priority_score=priority_score,
            priority_reason=priority_reason,
            preview_items=preview_items,
            item_summaries=item_summaries,
        )

    @classmethod
    def _priority_reason(cls, raw_type: str) -> str | None:
        label = cls._special_type_labels.get(raw_type)
        if label:
            return label
        return None

    @classmethod
    def _normalize_tab_name(cls, stash: dict[str, Any]) -> str:
        name = str(stash.get("name") or "").strip()
        raw_type = str(stash.get("type") or "Unknown")
        label = cls._special_type_labels.get(raw_type)
        if label and name:
            return f"{name} ({label})"
        if label:
            return label
        if name.isdigit():
            return f"Tab {name}"
        return name or raw_type

    @staticmethod
    def _is_folder_tab(stash: dict[str, Any]) -> bool:
        metadata = stash.get("metadata") or {}
        return bool(metadata.get("folder")) or stash.get("type") == "Folder" or stash.get("children")

    @classmethod
    def _format_item_preview(cls, item: dict[str, Any]) -> str:
        name = str(item.get("name") or "").strip()
        type_line = str(item.get("typeLine") or item.get("baseType") or "").strip()
        stack_size = item.get("stackSize")
        prefix = f"{stack_size}x " if isinstance(stack_size, int) and stack_size > 1 else ""
        if name and type_line:
            text = f"{prefix}{name} {type_line}".strip()
        else:
            text = f"{prefix}{name or type_line or 'item'}".strip()
        return text[:48] + "..." if len(text) > 48 else text

    @classmethod
    def _build_item_summaries(
        cls,
        items: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> tuple[StashItemSummary, ...]:
        aggregated: dict[str, list[int]] = {}
        for item in items:
            display_name = cls._format_item_name(item)
            if not display_name:
                continue
            quantity = item.get("stackSize")
            stack_quantity = quantity if isinstance(quantity, int) and quantity > 0 else 1
            bucket = aggregated.setdefault(display_name, [0, 0])
            bucket[0] += stack_quantity
            bucket[1] += 1

        ordered = sorted(
            (
                StashItemSummary(name=name, quantity=totals[0], entry_count=totals[1])
                for name, totals in aggregated.items()
            ),
            key=lambda summary: (-summary.quantity, -summary.entry_count, summary.name),
        )
        return tuple(ordered)

    @staticmethod
    def _format_item_name(item: dict[str, Any]) -> str:
        name = str(item.get("name") or "").strip()
        type_line = str(item.get("typeLine") or item.get("baseType") or "").strip()
        if name and type_line:
            return f"{name} {type_line}".strip()
        return name or type_line or ""

    @staticmethod
    def choose_primary_poe1_league(leagues: tuple[str, ...], fallback_default: str | None = None) -> str | None:
        if not leagues:
            return None

        league_set = set(leagues)
        if fallback_default and fallback_default in league_set and "POE2" not in fallback_default.upper():
            return fallback_default

        preferred_non_standard = [
            league
            for league in leagues
            if "standard" not in league.lower()
            and "hardcore" not in league.lower()
            and "ssf" not in league.lower()
            and "solo self-found" not in league.lower()
            and "ruthless" not in league.lower()
        ]
        if preferred_non_standard:
            return preferred_non_standard[0]

        for league in leagues:
            if league.lower() == "standard":
                return league

        softcore_non_ruthless = [
            league
            for league in leagues
            if "hardcore" not in league.lower()
            and "ssf" not in league.lower()
            and "solo self-found" not in league.lower()
            and "ruthless" not in league.lower()
        ]
        if softcore_non_ruthless:
            return softcore_non_ruthless[0]

        return leagues[0]

    @classmethod
    def _get_cached_snapshot(cls, user_id: int, league_name: str) -> StashSnapshot | None:
        cache_key = (user_id, league_name)
        cached = cls._snapshot_cache.get(cache_key)
        if cached is None:
            return None

        cached_at, snapshot = cached
        if datetime.now(UTC) - cached_at > cls._snapshot_cache_ttl:
            cls._snapshot_cache.pop(cache_key, None)
            return None

        return replace(snapshot, is_cached=True)

    @classmethod
    def _store_cached_snapshot(cls, user_id: int, league_name: str, snapshot: StashSnapshot) -> None:
        cls._snapshot_cache[(user_id, league_name)] = (datetime.now(UTC), snapshot)
