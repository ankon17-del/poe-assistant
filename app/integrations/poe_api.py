from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class PoeApiAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class RateLimitState:
    policy: str | None
    rules: list[str]
    retry_after_seconds: int | None
    raw_headers: dict[str, str]


class PoeApiClient:
    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
        access_token: str | None = None,
        timeout_seconds: float = 30.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.poe_api_base_url).rstrip("/")
        self.user_agent = user_agent or settings.poe_api_user_agent
        self.access_token = access_token if access_token is not None else settings.poe_api_access_token
        self.timeout_seconds = timeout_seconds

    async def list_leagues(self, realm: str = "poe2", limit: int = 50) -> list[dict[str, Any]]:
        payload = await self._get_json("/league", params={"realm": realm, "limit": limit})
        return payload.get("leagues", [])

    async def get_public_stashes(self, realm: str = "pc", change_id: str | None = None) -> dict[str, Any]:
        params: dict[str, str] = {}
        if change_id:
            params["id"] = change_id
        return await self._get_json(f"/public-stash-tabs/{realm}", params=params)

    async def get_currency_exchange(self, league: str, realm: str = "poe2") -> dict[str, Any]:
        return await self._get_json(f"/currency-exchange/{league}", params={"realm": realm})

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            headers = {
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            }
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            response = await client.get(
                path,
                params=params,
                headers=headers,
            )

        self._log_rate_limit_state(response)
        if response.status_code == 401:
            raise PoeApiAuthError(
                "PoE API returned 401 Unauthorized. Configure POE_API_ACCESS_TOKEN with a token that has "
                "the required scope, or set POE_OAUTH_CLIENT_ID/POE_OAUTH_CLIENT_SECRET so the app can "
                "request a service token automatically."
            )
        response.raise_for_status()
        return response.json()

    def _log_rate_limit_state(self, response: httpx.Response) -> None:
        state = self._parse_rate_limit_state(response)
        if state.policy or state.retry_after_seconds is not None:
            logger.info(
                "PoE API rate limit policy=%s rules=%s retry_after=%s",
                state.policy,
                ",".join(state.rules),
                state.retry_after_seconds,
            )

    @staticmethod
    def _parse_rate_limit_state(response: httpx.Response) -> RateLimitState:
        headers = {key.lower(): value for key, value in response.headers.items()}
        rules_raw = headers.get("x-rate-limit-rules", "")
        rules = [rule.strip() for rule in rules_raw.split(",") if rule.strip()]
        retry_after = headers.get("retry-after")

        return RateLimitState(
            policy=headers.get("x-rate-limit-policy"),
            rules=rules,
            retry_after_seconds=int(retry_after) if retry_after and retry_after.isdigit() else None,
            raw_headers=headers,
        )
