from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tracked_item import TrackedItem
from app.models.template import TemplateGroup, UserTemplate
from app.models.user import User
from app.services.tracking import TrackingService


@dataclass(frozen=True)
class TemplateActivationResult:
    template_name: str
    created_count: int


class TemplateService:
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

        before_count = await self.session.scalar(
            select(func.count()).select_from(TrackedItem).where(
                TrackedItem.user_id == user.id,
                TrackedItem.is_active.is_(True),
            )
        )
        tracking = TrackingService(self.session)
        for item in template.items:
            threshold = Decimal(item.default_threshold) if item.default_threshold is not None else None
            await tracking.add_item(
                user=user,
                item_name=item.item_name,
                item_type=item.item_type,
                target_price=threshold,
                target_currency="ex",
                league_name=league_name,
                game=game,
            )

        after_count = await self.session.scalar(
            select(func.count()).select_from(TrackedItem).where(
                TrackedItem.user_id == user.id,
                TrackedItem.is_active.is_(True),
            )
        )
        created_count = max(0, (after_count or 0) - (before_count or 0))

        return TemplateActivationResult(template_name=template.name, created_count=created_count)
