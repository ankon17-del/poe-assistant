from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings


class PoeOAuthConfigError(RuntimeError):
    pass


class PoeOAuthStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    state: str
    verifier: str
    scopes: str


@dataclass(frozen=True)
class TokenPayload:
    access_token: str
    refresh_token: str | None
    token_type: str
    scope: str | None
    expires_in: int | None
    username: str | None
    sub: str | None
    raw: dict[str, Any]


class PoeOAuthService:
    def __init__(self):
        self.settings = get_settings()

    def build_authorization_request(self, scopes: str | None = None) -> AuthorizationRequest:
        self._require_client_configuration(require_secret=False)
        pkce = self._generate_pkce_pair()
        state = secrets.token_urlsafe(24)
        scope_string = scopes or self.settings.poe_oauth_default_account_scopes
        query = urlencode(
            {
                "client_id": self.settings.poe_oauth_client_id,
                "response_type": "code",
                "scope": scope_string,
                "state": state,
                "redirect_uri": self.settings.poe_oauth_redirect_uri,
                "code_challenge": pkce.challenge,
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(
            url=f"{self.settings.poe_oauth_authorize_url}?{query}",
            state=state,
            verifier=pkce.verifier,
            scopes=scope_string,
        )

    async def exchange_authorization_code(
        self,
        code: str,
        code_verifier: str,
        scopes: str | None = None,
    ) -> TokenPayload:
        self._require_client_configuration(require_secret=False)
        payload = {
            "client_id": self.settings.poe_oauth_client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.poe_oauth_redirect_uri,
            "scope": scopes or self.settings.poe_oauth_default_account_scopes,
            "code_verifier": code_verifier,
        }
        if self.settings.poe_oauth_client_secret:
            payload["client_secret"] = self.settings.poe_oauth_client_secret
        data = await self._post_token_form(payload)
        return self._parse_token_payload(data)

    async def refresh_access_token(self, refresh_token: str) -> TokenPayload:
        self._require_client_configuration(require_secret=False)
        payload = {
            "client_id": self.settings.poe_oauth_client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if self.settings.poe_oauth_client_secret:
            payload["client_secret"] = self.settings.poe_oauth_client_secret
        data = await self._post_token_form(payload)
        return self._parse_token_payload(data)

    async def request_service_token(self, scopes: str | None = None) -> TokenPayload:
        self._require_client_configuration(require_secret=True)
        data = await self._post_token_form(
            {
                "client_id": self.settings.poe_oauth_client_id,
                "client_secret": self.settings.poe_oauth_client_secret,
                "grant_type": "client_credentials",
                "scope": scopes or self.settings.poe_oauth_default_service_scopes,
            }
        )
        return self._parse_token_payload(data)

    async def _post_token_form(self, payload: dict[str, str]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.settings.poe_oauth_token_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": self.settings.poe_api_user_agent,
                    "Accept": "application/json",
                },
            )
        response.raise_for_status()
        return response.json()

    def _require_client_configuration(self, require_secret: bool) -> None:
        if not self.settings.poe_oauth_client_id:
            raise PoeOAuthConfigError("POE_OAUTH_CLIENT_ID is not configured.")
        if not self.settings.poe_oauth_redirect_uri:
            raise PoeOAuthConfigError("POE_OAUTH_REDIRECT_URI is not configured.")
        if require_secret and not self.settings.poe_oauth_client_secret:
            raise PoeOAuthConfigError("POE_OAUTH_CLIENT_SECRET is required for this flow.")

    @staticmethod
    def _generate_pkce_pair() -> PkcePair:
        verifier_bytes = secrets.token_bytes(32)
        verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")
        challenge_digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(challenge_digest).rstrip(b"=").decode("ascii")
        return PkcePair(verifier=verifier, challenge=challenge)

    @staticmethod
    def _parse_token_payload(data: dict[str, Any]) -> TokenPayload:
        return TokenPayload(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "bearer"),
            scope=data.get("scope"),
            expires_in=data.get("expires_in"),
            username=data.get("username"),
            sub=data.get("sub"),
            raw=data,
        )
