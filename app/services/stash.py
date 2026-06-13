from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.currency_market_source import CurrencyMarketSource
from app.integrations.tracking_source import TrackingRequest
from app.models.enums import IntegrationType
from app.models.user import User
from app.services.integrations import IntegrationService
from app.services.poe_account import PoeAccountApiService, PoeAccountError, StashSnapshot


@dataclass(frozen=True)
class StashCapabilityStatus:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class StashGuide:
    slug: str
    title: str
    summary: str
    sections: tuple[tuple[str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class StashPanelSummary:
    account_connected: bool
    account_name: str | None
    oauth_available: bool
    oauth_blocker: str | None
    approved_scopes: tuple[str, ...]
    stash_scopes_ready: bool
    live_snapshot: StashSnapshot | None
    live_error: str | None
    priced_candidates: tuple["PricedStashCandidate", ...]
    valuation_source: str | None
    estimated_liquid_chaos: float | None
    statuses: tuple[StashCapabilityStatus, ...]
    next_steps: tuple[str, ...]


@dataclass(frozen=True)
class PricedStashCandidate:
    tab_name: str
    item_name: str
    quantity: int
    unit_price_chaos: float
    total_price_chaos: float


class StashService:
    _guides: tuple[StashGuide, ...] = (
        StashGuide(
            slug="triage",
            title="Быстрый stash triage",
            summary="Короткий маршрут, если у тебя 5-10 минут и хочется быстро понять, где в тайнике лежат самые лёгкие деньги.",
            sections=(
                (
                    "1. С чего начать",
                    (
                        "Открой currency, fragments, scarabs и essences раньше всего: там чаще всего лежит самая ликвидная масса.",
                        "Сначала смотри не на редкость предмета, а на объём: большие стаки часто приносят больше пользы, чем один красивый уник.",
                        "Отдельно проверь invitations, breach/legion/expedition currency и boss fragments.",
                    ),
                ),
                (
                    "2. Что считать быстрыми деньгами",
                    (
                        "Всё, что имеет понятную ликвидность: div/ex/chaos, scarabs, essences, catalysts, oils, invitations, breachstones.",
                        "Если предмет легко найти по exact name и он не требует длинного manual price check, это хороший кандидат на быструю продажу.",
                        "Когда не хватает валюты на апгрейд, сначала монетизируй ликвидные стаки, а не редкие вещи на потом.",
                    ),
                ),
                (
                    "3. Где чаще всего лежит мусор",
                    (
                        "Широкие dump tabs с rares, случайными uniques и полусобранными craft bases.",
                        "Старые механики, которые ты уже не фармишь: splinters, low-tier maps, random fossils маленькими пачками.",
                        "Вкладки без понятного плана: если вещь не идёт в билд, не продаётся быстро и не копится под цель, это кандидат на разбор.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="liquid",
            title="Что продавать быстрее всего",
            summary="Если нужна быстрая ликвидация, этот порядок обычно даёт самый понятный cash-out.",
            sections=(
                (
                    "1. Топ ликвидности",
                    (
                        "Валюта, scarabs, essences, oils, catalysts, invitations и boss fragments обычно продаются быстрее всего.",
                        "Следом идут карты, логбуки, эмблемы, breachstones и другие понятные endgame consumables.",
                        "Если у тебя много мелких стаков, собери их в более крупные партии: так их проще продать.",
                    ),
                ),
                (
                    "2. Что продавать после этого",
                    (
                        "Сильные bases, востребованные уникалки, jewels с понятными модами и gear, который легко описать названием и 2-3 аффиксами.",
                        "Всё, что требует длинного craft-context, продавай только если уверен в цене; иначе это уже не быстрые деньги.",
                    ),
                ),
                (
                    "3. Чего не ждать от быстрой продажи",
                    (
                        "Сомнительные rares без очевидного use-case.",
                        "Уникалки без meta-спроса только потому, что они когда-то были дорогими.",
                        "Редкие базы без influence, fracture или явного craft-потенциала.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="uniques",
            title="Как проверять unique tabs",
            summary="Большинство unique tabs — это смесь реальной ценности и большого количества приятного мусора.",
            sections=(
                (
                    "1. Что искать глазами",
                    (
                        "Meta-defining uniques, chase belts/rings/amulets, build-enabling jewels и вещи, которые ты сам часто видишь в гайдах.",
                        "Double-corrupt, хорошие rolls, high ilvl и редкие варианты важнее, чем сам факт, что предмет unique.",
                        "Если unique ищется по exact name и у него есть 1-2 критичных roll ranges, это сильный кандидат на отдельный price check.",
                    ),
                ),
                (
                    "2. Как не тратить время впустую",
                    (
                        "Не price-check'ай всю вкладку подряд. Сначала вытащи только те uniques, которые реально известны как useful или expensive.",
                        "Смотри на повторы: 6 копий среднего unique редко скрывают сокровище.",
                    ),
                ),
                (
                    "3. Когда unique лучше оставить",
                    (
                        "Если он дешёвый, но точно идёт в один из твоих билдов или шаблонов фарма.",
                        "Если это часть будущего upgrade path, а не случайная находка.",
                    ),
                ),
            ),
        ),
        StashGuide(
            slug="currency",
            title="Как смотреть currency и fragments",
            summary="Это самый практичный stash-layer: именно здесь чаще всего лежит основная ликвидность аккаунта.",
            sections=(
                (
                    "1. Проверка валюты",
                    (
                        "Начни с div/ex/chaos, потом переходи к bulk-consumables: essences, catalysts, oils, scarabs, invitations.",
                        "Bulk-ресурсы часто монетизируются быстрее и спокойнее, чем редкий gear.",
                    ),
                ),
                (
                    "2. Fragments и boss pieces",
                    (
                        "Собери в обзор invitations, fragments, breachstones, emblems, logbooks и другие endgame pieces.",
                        "Такие вещи удобно продавать сериями: 5-10 одинаковых предметов уже ощущаются как товар, а не случайный мусор.",
                    ),
                ),
                (
                    "3. Когда стоит придержать",
                    (
                        "Если ты прямо сейчас фармишь эту механику и она даёт доход выше мгновенной продажи.",
                        "Если предметы копятся под крупную batch-sale, а не лежат бесцельно.",
                    ),
                ),
            ),
        ),
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = get_settings()
        self.currency_market_source = CurrencyMarketSource()

    async def get_panel_summary(self, user: User) -> StashPanelSummary:
        integration = await IntegrationService(self.session).get_by_type(user, IntegrationType.poe_oauth)

        oauth_available = bool(
            self.settings.poe_oauth_client_id
            and self.settings.poe_oauth_client_secret
            and self.settings.poe_oauth_redirect_uri
        )
        oauth_blocker = None
        if not self.settings.poe_oauth_client_id:
            oauth_blocker = "не задан POE_OAUTH_CLIENT_ID"
        elif not self.settings.poe_oauth_client_secret:
            oauth_blocker = "не задан POE_OAUTH_CLIENT_SECRET"
        elif not self.settings.poe_oauth_redirect_uri:
            oauth_blocker = "не задан POE_OAUTH_REDIRECT_URI"

        scopes = tuple(scope.strip() for scope in (integration.scopes or "").split() if scope.strip()) if integration else ()
        stash_scopes_ready = "account:stashes" in scopes

        live_snapshot: StashSnapshot | None = None
        live_error: str | None = None
        priced_candidates: tuple[PricedStashCandidate, ...] = ()
        valuation_source: str | None = None
        estimated_liquid_chaos: float | None = None
        if integration and stash_scopes_ready:
            try:
                live_snapshot = await PoeAccountApiService(self.session).get_stash_snapshot(user)
                if live_snapshot:
                    priced_candidates, valuation_source, estimated_liquid_chaos = await self._build_priced_candidates(live_snapshot)
            except PoeAccountError as exc:
                live_error = str(exc)

        statuses = (
            StashCapabilityStatus(
                title="Привязка аккаунта",
                status="готово" if integration else "ожидает",
                detail=(
                    f"Подключён аккаунт {integration.external_account_name or 'Path of Exile'}."
                    if integration
                    else "Аккаунт пока не подключён."
                ),
            ),
            StashCapabilityStatus(
                title="Stash scope",
                status="готово" if stash_scopes_ready else "ожидает",
                detail=(
                    "У пользователя уже есть scope account:stashes, можно читать личные тайники."
                    if stash_scopes_ready
                    else "Текущий токен ещё не содержит account:stashes. Нужна повторная авторизация с полным списком scopes."
                ),
            ),
            StashCapabilityStatus(
                title="Live stash summary",
                status="готово" if live_snapshot else ("ошибка" if live_error else "ожидает"),
                detail=(
                    f"Загружены вкладки лиги {live_snapshot.league_name}: всего {live_snapshot.total_tabs}."
                    if live_snapshot
                    else live_error or "Живой обзор вкладок включится после подключения аккаунта и выдачи нужного scope."
                ),
            ),
        )

        if not oauth_available:
            next_steps = (
                "Дописать OAuth переменные в проде и сделать redeploy.",
                "После этого подключить PoE аккаунт через /account.",
                "Следом включить живой обзор тайника.",
            )
        elif not integration:
            next_steps = (
                "Подключить PoE аккаунт через /account.",
                "Подтвердить scopes на экране авторизации.",
                "После этого обновить /stash и проверить первый обзор вкладок.",
            )
        elif not stash_scopes_ready:
            next_steps = (
                "Переподключить аккаунт через /account, чтобы токен получил account:stashes.",
                "После новой авторизации обновить /stash.",
                "Следом можно будет включать таб-за-табом более глубокий анализ.",
            )
        elif live_error:
            next_steps = (
                "Проверить действительность токена и обновить /stash ещё раз.",
                "Если ошибка повторится, посмотреть API-ответ и скорректировать endpoint или scope usage.",
                "После этого перейти к расширенному анализу вкладок.",
            )
        else:
            next_steps = (
                "Следующий шаг — скрытая ликвидность и кандидаты на быструю продажу.",
                "Потом — обзор вкладок по категориям и сигналы, где лежат деньги.",
                "Дальше — account-aware рекомендации на основе персонажей и лиги.",
            )

        return StashPanelSummary(
            account_connected=integration is not None,
            account_name=integration.external_account_name if integration else None,
            oauth_available=oauth_available,
            oauth_blocker=oauth_blocker,
            approved_scopes=scopes,
            stash_scopes_ready=stash_scopes_ready,
            live_snapshot=live_snapshot,
            live_error=live_error,
            priced_candidates=priced_candidates,
            valuation_source=valuation_source,
            estimated_liquid_chaos=estimated_liquid_chaos,
            statuses=statuses,
            next_steps=next_steps,
        )

    async def _build_priced_candidates(
        self,
        snapshot: StashSnapshot,
    ) -> tuple[tuple[PricedStashCandidate, ...], str | None, float | None]:
        candidates: list[PricedStashCandidate] = []
        source_labels: list[str] = []
        total_estimated = Decimal("0")
        supported_tab_types = {"CurrencyStash", "FragmentStash"}

        lookup_rows: list[tuple[str, str, int]] = []
        for tab in snapshot.tabs:
            if tab.type not in supported_tab_types:
                continue
            for item in tab.item_summaries:
                lookup_rows.append((tab.name, item.name, item.quantity))

        if not lookup_rows:
            return (), None, None

        price_snapshots: dict[str, tuple[Decimal, str]] = {}
        for _, item_name, _ in lookup_rows:
            if item_name in price_snapshots:
                continue
            price = await self.currency_market_source.get_price(
                TrackingRequest(
                    tracked_item_id=0,
                    item_name=item_name,
                    item_type="currency",
                    trade_url=None,
                    target_price=None,
                    target_currency="chaos",
                    league_name=snapshot.league_name,
                    game="poe1",
                )
            )
            if price is None:
                continue
            chaos_value = price.quote_values.get("chaos") or price.market_value
            if chaos_value is None:
                continue
            price_snapshots[item_name] = (chaos_value, price.source)

        for tab_name, item_name, quantity in lookup_rows:
            priced = price_snapshots.get(item_name)
            if priced is None:
                continue
            unit_price, source_label = priced
            source_labels.append(source_label)
            total_price = unit_price * quantity
            total_estimated += total_price
            if total_price < 5:
                continue

            candidates.append(
                PricedStashCandidate(
                    tab_name=tab_name,
                    item_name=item_name,
                    quantity=quantity,
                    unit_price_chaos=float(unit_price),
                    total_price_chaos=float(total_price),
                )
            )

        candidates.sort(key=lambda candidate: (-candidate.total_price_chaos, -candidate.unit_price_chaos, candidate.item_name))
        unique_sources = list(dict.fromkeys(source_labels))
        estimate = float(total_estimated) if total_estimated > 0 else None
        return tuple(candidates[:8]), (", ".join(unique_sources) if unique_sources else None), estimate

    @classmethod
    def list_guides(cls) -> tuple[StashGuide, ...]:
        return cls._guides

    @classmethod
    def get_guide(cls, slug: str) -> StashGuide | None:
        for guide in cls._guides:
            if guide.slug == slug:
                return guide
        return None
