from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class OAuthState:
    state: str
    code_verifier: str
    scopes: str
    telegram_id: int
    created_at: datetime


class OAuthStateStore:
    def __init__(self, ttl_minutes: int = 10):
        self.ttl = timedelta(minutes=ttl_minutes)
        self._states: dict[str, OAuthState] = {}

    def create(self, state: str, code_verifier: str, scopes: str, telegram_id: int) -> OAuthState:
        self.prune()
        item = OAuthState(
            state=state,
            code_verifier=code_verifier,
            scopes=scopes,
            telegram_id=telegram_id,
            created_at=datetime.now(UTC),
        )
        self._states[state] = item
        return item

    def pop(self, state: str) -> OAuthState | None:
        self.prune()
        return self._states.pop(state, None)

    def prune(self) -> None:
        threshold = datetime.now(UTC) - self.ttl
        expired = [state for state, item in self._states.items() if item.created_at < threshold]
        for state in expired:
            self._states.pop(state, None)


oauth_state_store = OAuthStateStore()
