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


@dataclass(frozen=True)
class StashGuide:
    slug: str
    title: str
    summary: str
    sections: tuple[tuple[str, tuple[str, ...]], ...]


class StashService:
    _guides: tuple[StashGuide, ...] = (
        StashGuide(
            slug="triage",
            title="Быстрый stash triage",
            summary="Короткий маршрут, если у тебя 5-10 минут и хочется быстро понять, где в тайниках лежат самые лёгкие деньги.",
            sections=(
                (
                    "1. С чего начать",
                    (
                        "Открой currency / fragments / scarabs / essences раньше всего: там чаще всего лежит самая ликвидная масса.",
                        "Сначала смотри не на редкость предмета, а на объём: большие стаки часто дают больше диванов, чем один красивый уник.",
                        "Отдельно проверь вкладки с invitations, fragments, breach/legion/expedition currency и scarabs.",
                    ),
                ),
                (
                    "2. Что считать быстрыми деньгами",
                    (
                        "Всё, что имеет понятную рыночную ликвидность: div/ex/chaos, scarabs, essences, catalysts, oils, invitations, breachstones.",
                        "Если предмет не требует долгого price check и его легко искать по exact name — это хороший кандидат на быструю продажу.",
                        "Когда не хватает валюты на апгрейд, сначала выноси в продажу именно такие вещи, а не редкие шлемы 'на потом'.",
                    ),
                ),
                (
                    "3. Где чаще всего лежит мусор",
                    (
                        "Широкие dump tabs с rares, униками 'на всякий случай' и полусобранными craft bases.",
                        "Старые механики, которые ты больше не фармишь: splinters, low-tier maps, random fossils/резонаторы маленькими пачками.",
                        "Вкладки, где у тебя нет явного плана: если вещь не идёт в билд, не продаётся быстро и не копится под цель — это кандидат на разбор.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="liquid",
            title="Что продавать быстрее всего",
            summary="Если нужна быстрая ликвидация, вот какой порядок обычно даёт самый понятный кэш-аут.",
            sections=(
                (
                    "1. Топ ликвидности",
                    (
                        "Валюта, scarabs, essences, oils, catalysts, invitations и boss fragments обычно продаются быстрее всего.",
                        "Следом идут карты/логбуки/эмблемы/бичстоуны и другие понятные endgame-consumables.",
                        "Если у тебя много мелких стаков, собирай их в более крупные — так их проще продать и глазами, и рынку.",
                    ),
                ),
                (
                    "2. Что продавать после этого",
                    (
                        "Сильные bases, востребованные уникалки, jewels с понятными модами и gear, который легко объяснить названием + 2-3 аффиксами.",
                        "Всё, что требует долгого craft-context, продавай только если ты уверен в цене; иначе это уже не 'быстрые деньги'.",
                    ),
                ),
                (
                    "3. Чего не ждать от быстрой продажи",
                    (
                        "Сомнительные rares без очевидного use-case.",
                        "Уникалки без meta-спроса просто потому, что они красивые или когда-то были дорогими.",
                        "Редкие базы без influence/fracture/явного крафтового потенциала.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="uniques",
            title="Как проверять unique tabs",
            summary="Большинство unique tabs — это смесь настоящей ценности и огромного количества 'приятного мусора'.",
            sections=(
                (
                    "1. Что искать глазами",
                    (
                        "Meta-defining uniques, chase belts/rings/amulets, build-enabling jewels и вещи, которые ты сам часто видишь в гайдах.",
                        "Double-corrupt / good rolls / high ilvl / rare variants обычно важнее, чем сам факт 'о, это unique'.",
                        "Если уник ищется exact name и у него есть 1-2 критичных roll ranges — это сильный кандидат на отдельный price check.",
                    ),
                ),
                (
                    "2. Как не тратить время впустую",
                    (
                        "Не price-check'ай подряд всю вкладку. Сначала вытащи только те uniques, которые реально известны как useful или expensive.",
                        "Смотри на повторы: если у тебя 6 копий среднего уника, это редко скрытое сокровище.",
                    ),
                ),
                (
                    "3. Когда unique лучше оставить",
                    (
                        "Если он дешёвый, но точно идёт в один из твоих билдов или шаблонов фарма.",
                        "Если это piece для будущего chase-upgrade path, а не случайная находка.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="currency",
            title="Как смотреть currency / fragments",
            summary="Самый практичный stash-layer: именно здесь чаще всего лежит основная ликвидность account'а.",
            sections=(
                (
                    "1. Проверка валюты",
                    (
                        "Начни с div/ex/chaos и дальше смотри bulk-consumables: essences, catalysts, oils, scarabs, invitations.",
                        "Если рынок живой, bulk-ресурсы часто монетизируются быстрее и тише, чем редкий gear.",
                    ),
                ),
                (
                    "2. Fragments и boss pieces",
                    (
                        "Собери полный список invitations, fragments, breachstones, emblems, logbooks и похожих endgame pieces.",
                        "Такие вещи удобно продавать сериями: 5-10+ одинаковых предметов уже ощущаются как товар, а не мусор.",
                    ),
                ),
                (
                    "3. Когда стоит придержать",
                    (
                        "Если ты сам прямо сейчас фармишь эту механику и она конвертируется в доход выше мгновенной продажи.",
                        "Если предметы копятся под крупный batch-sale, а не лежат бесцельно.",
                    ),
                ),
            ),
        ),
    )

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

    @classmethod
    def list_guides(cls) -> tuple[StashGuide, ...]:
        return cls._guides

    @classmethod
    def get_guide(cls, slug: str) -> StashGuide | None:
        for guide in cls._guides:
            if guide.slug == slug:
                return guide
        return None
