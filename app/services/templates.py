from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.template import TemplateGroup, TemplateItem, UserTemplate
from app.models.user import User
from app.services.tracking import TrackingService


@dataclass(frozen=True)
class TemplateActivationResult:
    template_name: str
    strategy_name: str
    created_count: int
    updated_count: int
    created_items: list[str]
    updated_items: list[str]


@dataclass(frozen=True)
class TemplateStrategy:
    key: str
    title: str
    description: str


@dataclass(frozen=True)
class ResolvedTemplateItem:
    item_name: str
    item_type: str
    target_price: Decimal | None
    target_currency: str
    priority: int


@dataclass(frozen=True)
class TemplateGoal:
    key: str
    title: str
    description: str


class TemplateService:
    TEMPLATE_REALMS: dict[str, str] = {
        "Currency Farming": "both",
        "POE2 Starter Economy": "poe2",
        "POE2 Exchange Watch": "poe2",
        "POE1 Currency Farming": "poe1",
        "Essence Farming": "poe1",
        "Boss Drops": "poe1",
        "Scarab Market": "poe1",
    }

    CURRENCY_STRATEGIES: tuple[TemplateStrategy, ...] = (
        TemplateStrategy("premium", "Премиум", "Ждать более сильную цену и меньше ложного шума."),
        TemplateStrategy("balanced", "Сбалансированная", "Нормальный базовый режим без перекоса."),
        TemplateStrategy("snipe", "Ранний сигнал", "Ловить движение раньше, но чаще получать alerts."),
    )

    WATCH_STRATEGIES: tuple[TemplateStrategy, ...] = (
        TemplateStrategy("focused", "Фокус", "Следить только за самыми приоритетными позициями."),
        TemplateStrategy("balanced", "Сбалансированная", "Оставить основной состав шаблона как есть."),
        TemplateStrategy("wide", "Широкий охват", "Держать более широкий watchlist и ловить движение раньше."),
    )

    TEMPLATE_GOALS: tuple[TemplateGoal, ...] = (
        TemplateGoal("starter_setup", "Стартовый сетап", "Быстро собрать чистый базовый стартовый market setup."),
        TemplateGoal("currency_farm", "Фарм валюты", "Сфокусироваться на currency и быстрой ликвидности."),
        TemplateGoal("market_watch", "Рынок и обмен", "Следить за exchange-курсами и ранними сигналами рынка."),
        TemplateGoal("specialized_farm", "Специализированный фарм", "Подобрать pack под конкретную механику или тип фарма."),
    )

    GOAL_TEMPLATE_ORDER: dict[str, dict[str, list[str]]] = {
        "poe2": {
            "starter_setup": ["POE2 Starter Economy", "Currency Farming", "POE2 Exchange Watch"],
            "currency_farm": ["POE2 Starter Economy", "Currency Farming", "POE2 Exchange Watch"],
            "market_watch": ["POE2 Exchange Watch", "POE2 Starter Economy", "Currency Farming"],
            "specialized_farm": ["POE2 Starter Economy", "POE2 Exchange Watch", "Currency Farming"],
        },
        "poe1": {
            "starter_setup": ["POE1 Currency Farming", "Currency Farming", "Essence Farming"],
            "currency_farm": ["POE1 Currency Farming", "Currency Farming", "Scarab Market"],
            "market_watch": ["POE1 Currency Farming", "Currency Farming", "Scarab Market"],
            "specialized_farm": ["Essence Farming", "Scarab Market", "Boss Drops", "POE1 Currency Farming"],
        },
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_public(self) -> list[TemplateGroup]:
        result = await self.session.scalars(
            select(TemplateGroup)
            .where(TemplateGroup.is_public.is_(True))
            .options(selectinload(TemplateGroup.items))
            .order_by(TemplateGroup.category, TemplateGroup.name)
        )
        return list(result)

    async def list_public_for_game(self, game: str) -> list[TemplateGroup]:
        templates = await self.list_public()
        return [
            template
            for template in templates
            if self.get_template_realm(template) in {game, "both"}
        ]

    async def list_public_for_goal(self, game: str, goal_key: str) -> list[TemplateGroup]:
        templates = await self.list_public_for_game(game)
        order = self.GOAL_TEMPLATE_ORDER.get(game, {}).get(goal_key, [])
        order_index = {name: index for index, name in enumerate(order)}
        return sorted(
            templates,
            key=lambda template: (
                order_index.get(template.name, len(order_index) + 100),
                template.category,
                template.name,
            ),
        )

    @classmethod
    def get_template_realm(cls, template: TemplateGroup) -> str:
        return cls.TEMPLATE_REALMS.get(template.name, "both")

    async def get_public_by_id(self, template_group_id: int) -> TemplateGroup | None:
        return await self.session.scalar(
            select(TemplateGroup)
            .where(TemplateGroup.id == template_group_id, TemplateGroup.is_public.is_(True))
            .options(selectinload(TemplateGroup.items))
        )

    def list_goals(self) -> list[TemplateGoal]:
        return list(self.TEMPLATE_GOALS)

    def get_goal(self, goal_key: str) -> TemplateGoal | None:
        for goal in self.TEMPLATE_GOALS:
            if goal.key == goal_key:
                return goal
        return None

    def list_strategies(self, template: TemplateGroup) -> list[TemplateStrategy]:
        if template.category == "currency":
            return list(self.CURRENCY_STRATEGIES)
        return list(self.WATCH_STRATEGIES)

    def get_strategy(self, template: TemplateGroup, strategy_key: str | None) -> TemplateStrategy:
        strategies = self.list_strategies(template)
        lookup = {strategy.key: strategy for strategy in strategies}
        if strategy_key and strategy_key in lookup:
            return lookup[strategy_key]
        return lookup["balanced"]

    def resolve_items(
        self,
        template: TemplateGroup,
        *,
        strategy_key: str | None = None,
    ) -> tuple[TemplateStrategy, list[ResolvedTemplateItem]]:
        strategy = self.get_strategy(template, strategy_key)
        if template.category == "currency":
            items = [self._apply_currency_strategy(item, strategy.key) for item in template.items]
            return strategy, items

        if strategy.key == "focused":
            limit = max(1, math.ceil(len(template.items) / 2))
            source_items = sorted(template.items, key=lambda item: item.priority)[:limit]
            items = [self._to_resolved_item(item) for item in source_items]
            return strategy, items

        if strategy.key == "wide":
            items = [self._apply_watch_strategy(item, lower_threshold=True) for item in template.items]
            return strategy, items

        items = [self._to_resolved_item(item) for item in template.items]
        return strategy, items

    async def activate(
        self,
        user: User,
        template_group_id: int,
        *,
        league_name: str | None = None,
        game: str | None = None,
        strategy_key: str | None = None,
    ) -> TemplateActivationResult | None:
        template = await self.get_public_by_id(template_group_id)
        if not template:
            return None
        strategy, resolved_items = self.resolve_items(template, strategy_key=strategy_key)

        existing_link = await self.session.scalar(
            select(UserTemplate).where(
                UserTemplate.user_id == user.id,
                UserTemplate.template_group_id == template.id,
            )
        )
        if existing_link:
            existing_link.enabled = True
        else:
            self.session.add(UserTemplate(user_id=user.id, template_group_id=template.id, enabled=True))

        tracking = TrackingService(self.session)
        created_items: list[str] = []
        updated_items: list[str] = []
        for item in resolved_items:
            result = await tracking.add_item(
                user=user,
                item_name=item.item_name,
                item_type=item.item_type,
                target_price=item.target_price,
                target_currency=item.target_currency,
                league_name=league_name,
                game=game,
            )
            if result.action == "created":
                created_items.append(result.item.item_name)
            else:
                updated_items.append(result.item.item_name)

        return TemplateActivationResult(
            template_name=template.name,
            strategy_name=strategy.title,
            created_count=len(created_items),
            updated_count=len(updated_items),
            created_items=created_items,
            updated_items=updated_items,
        )

    @staticmethod
    def _to_resolved_item(item: TemplateItem) -> ResolvedTemplateItem:
        threshold = Decimal(item.default_threshold) if item.default_threshold is not None else None
        return ResolvedTemplateItem(
            item_name=item.item_name,
            item_type=item.item_type,
            target_price=threshold,
            target_currency=item.default_target_currency or "ex",
            priority=item.priority,
        )

    def _apply_currency_strategy(self, item: TemplateItem, strategy_key: str) -> ResolvedTemplateItem:
        multiplier = Decimal("1.00")
        if strategy_key == "premium":
            multiplier = Decimal("1.10")
        elif strategy_key == "snipe":
            multiplier = Decimal("0.90")

        resolved = self._to_resolved_item(item)
        if resolved.target_price is None:
            return resolved
        return ResolvedTemplateItem(
            item_name=resolved.item_name,
            item_type=resolved.item_type,
            target_price=self._scaled_threshold(resolved.target_price, multiplier),
            target_currency=resolved.target_currency,
            priority=resolved.priority,
        )

    def _apply_watch_strategy(self, item: TemplateItem, *, lower_threshold: bool) -> ResolvedTemplateItem:
        resolved = self._to_resolved_item(item)
        if resolved.target_price is None:
            return resolved
        multiplier = Decimal("0.80") if lower_threshold else Decimal("1.00")
        return ResolvedTemplateItem(
            item_name=resolved.item_name,
            item_type=resolved.item_type,
            target_price=self._scaled_threshold(resolved.target_price, multiplier),
            target_currency=resolved.target_currency,
            priority=resolved.priority,
        )

    @staticmethod
    def _scaled_threshold(value: Decimal, multiplier: Decimal) -> Decimal:
        scaled = value * multiplier
        return scaled.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
