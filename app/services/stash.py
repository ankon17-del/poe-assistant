from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enums import IntegrationType
from app.models.user import User
from app.services.integrations import IntegrationService


@dataclass(frozen=True)
class StashCapabilityStatus:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class StashPanelSummary:
    account_connected: bool
    account_name: str | None
    oauth_available: bool
    oauth_blocker: str | None
    approved_scopes: tuple[str, ...]
    stash_scopes_ready: bool
    statuses: tuple[StashCapabilityStatus, ...]
    upcoming_insights: tuple[str, ...]
    next_steps: tuple[str, ...]


class StashService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()

    async def get_panel_summary(self, user: User) -> StashPanelSummary:
        integration = await IntegrationService(self.session).get_by_type(user, IntegrationType.poe_oauth)

        oauth_available = bool(self.settings.poe_oauth_client_id and self.settings.poe_oauth_redirect_uri)
        oauth_blocker = None
        if not self.settings.poe_oauth_client_id:
            oauth_blocker = "ожидаем client_id от GGG"
        elif not self.settings.poe_oauth_redirect_uri:
            oauth_blocker = "не задан POE_OAUTH_REDIRECT_URI"

        scopes = tuple(
            scope.strip()
            for scope in (integration.scopes or "").split()
            if scope.strip()
        ) if integration else ()

        stash_scope_markers = ("stash", "stashes", "account:stashes")
        stash_scopes_ready = any(marker in scope for scope in scopes for marker in stash_scope_markers)

        statuses = (
            StashCapabilityStatus(
                title="Привязка аккаунта",
                status="готово" if integration else "ожидает",
                detail=(
                    f"Подключён аккаунт {integration.external_account_name}."
                    if integration and integration.external_account_name
                    else "Аккаунт пока не привязан."
                ),
            ),
            StashCapabilityStatus(
                title="OAuth/scopes",
                status="готово" if stash_scopes_ready else "ожидает",
                detail=(
                    "Есть scope для чтения stash-данных, можно будет перейти к реальному анализу."
                    if stash_scopes_ready
                    else "Пока у нас нет stash-scopes, поэтому реальный разбор тайников ещё не включён."
                ),
            ),
            StashCapabilityStatus(
                title="Фаза 6 foundation",
                status="готово",
                detail="Панель анализа, сценарии инсайтов и next steps уже собраны внутри бота.",
            ),
        )

        upcoming_insights = (
            "Скрытая валюта и ценные стаки, которые легко не заметить глазами.",
            "Дорогие предметы и вкладки, которые сейчас стоит проверить на продажу.",
            "Ликвидационные кандидаты: что можно быстро продать ради div/chaos.",
            "Сигналы по перегруженным вкладкам: что пора разобрать, а не копить дальше.",
        )

        next_steps: tuple[str, ...]
        if not oauth_available:
            next_steps = (
                "Ждём ответ от GGG с client_id/client_secret.",
                "После этого подключаем PoE аккаунт через /account.",
                "Следом включаем реальный stash-read и начинаем анализ тайников.",
            )
        elif not integration:
            next_steps = (
                "Подключить PoE аккаунт через /account.",
                "Проверить выданные scopes.",
                "После появления stash-scopes включить реальный анализ вкладок.",
            )
        elif not stash_scopes_ready:
            next_steps = (
                "Привязка аккаунта уже есть, это хорошо.",
                "Следующий блокер — дождаться stash-scopes от GGG.",
                "Как только scopes будут одобрены, включим живой разбор тайников без переделки UX.",
            )
        else:
            next_steps = (
                "Сервис готов к переходу в живой stash-read.",
                "Следом можно будет выводить hidden currency, liquidation picks и tab-by-tab обзор.",
            )

        return StashPanelSummary(
            account_connected=integration is not None,
            account_name=integration.external_account_name if integration else None,
            oauth_available=oauth_available,
            oauth_blocker=oauth_blocker,
            approved_scopes=scopes,
            stash_scopes_ready=stash_scopes_ready,
            statuses=statuses,
            upcoming_insights=upcoming_insights,
            next_steps=next_steps,
        )
