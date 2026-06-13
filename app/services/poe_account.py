from __future__ import annotations

from dataclasses import dataclass
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
class StashSnapshot:
    league_name: str
    total_tabs: int
    folder_tabs: int
    special_tabs: int
    sample_tabs: tuple[str, ...]


class PoeAccountApiService:
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
            poe1_stash_note="PoE1 stash is selected from PoE1 account leagues only. PoE2 leagues are not used for this stash view yet.",
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

        stashes_payload = await self._authorized_get_json(user, integration, f"/stash/{selected_league}")
        stash_tabs = stashes_payload.get("stashes", [])

        total_tabs = len(stash_tabs)
        folder_tabs = 0
        special_tabs = 0
        sample_tabs: list[str] = []
        generic_types = {"NormalStash", "PremiumStash", "QuadStash", "Folder", "MapStash"}

        for stash in stash_tabs:
            stash_type = stash.get("type") or ""
            child_tabs = stash.get("stashes") or ()
            if stash_type == "Folder" or child_tabs:
                folder_tabs += 1
            if stash_type and stash_type not in generic_types:
                special_tabs += 1

            label = stash.get("name") or stash_type or stash.get("id")
            if label and len(sample_tabs) < 5:
                sample_tabs.append(str(label))

        return StashSnapshot(
            league_name=selected_league,
            total_tabs=total_tabs,
            folder_tabs=folder_tabs,
            special_tabs=special_tabs,
            sample_tabs=tuple(sample_tabs),
        )

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
