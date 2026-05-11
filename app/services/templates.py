from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.template import TemplateGroup, UserTemplate
from app.models.user import User
from app.services.tracking import TrackingService


@dataclass(frozen=True)
class TemplateActivationResult:
    template_name: str
    created_count: int
    updated_count: int
    created_items: list[str]
    updated_items: list[str]


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

    @classmethod
    def get_template_realm(cls, template: TemplateGroup) -> str:
        return cls.TEMPLATE_REALMS.get(template.name, "both")

    async def get_public_by_id(self, template_group_id: int) -> TemplateGroup | None:
        return await self.session.scalar(
            select(TemplateGroup)
            .where(TemplateGroup.id == template_group_id, TemplateGroup.is_public.is_(True))
            .options(selectinload(TemplateGroup.items))
        )

    async def activate(
        self,
        user: User,
        template_group_id: int,
        *,
        league_name: str | None = None,
        game: str | None = None,
    ) -> TemplateActivationResult | None:
        template = await self.get_public_by_id(template_group_id)
        if not template:
            return None

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
        for item in template.items:
            threshold = Decimal(item.default_threshold) if item.default_threshold is not None else None
            result = await tracking.add_item(
                user=user,
                item_name=item.item_name,
                item_type=item.item_type,
                target_price=threshold,
                target_currency=item.default_target_currency or "ex",
                league_name=league_name,
                game=game,
            )
            if result.action == "created":
                created_items.append(result.item.item_name)
            else:
                updated_items.append(result.item.item_name)

        return TemplateActivationResult(
            template_name=template.name,
            created_count=len(created_items),
            updated_count=len(updated_items),
            created_items=created_items,
            updated_items=updated_items,
        )
