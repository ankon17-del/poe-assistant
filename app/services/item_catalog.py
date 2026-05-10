from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import TemplateItem
from app.models.tracked_item import TrackedItem


COMMON_CURRENCIES: list[str] = [
    "Divine Orb",
    "Exalted Orb",
    "Chaos Orb",
    "Regal Orb",
    "Vaal Orb",
    "Orb of Alchemy",
    "Orb of Annulment",
    "Orb of Chance",
    "Orb of Alteration",
    "Orb of Augmentation",
    "Orb of Transmutation",
]


class ItemCatalogService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, query: str, limit: int = 8) -> list[str]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return COMMON_CURRENCIES[:limit]

        template_names = await self.session.scalars(select(TemplateItem.item_name).distinct())
        tracked_names = await self.session.scalars(select(TrackedItem.item_name).distinct())
        all_names = self._dedupe_names([*COMMON_CURRENCIES, *template_names, *tracked_names])

        ranked = sorted(
            all_names,
            key=lambda name: self._sort_key(name=name, query=normalized_query),
        )
        filtered = [name for name in ranked if normalized_query in name.lower()]
        return filtered[:limit]

    @staticmethod
    def _dedupe_names(names: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for name in names:
            normalized = name.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(normalized)
        return result

    @staticmethod
    def _sort_key(name: str, query: str) -> tuple[int, int, str]:
        lowered = name.lower()
        starts = 0 if lowered.startswith(query) else 1
        contains_index = lowered.find(query)
        position = contains_index if contains_index >= 0 else 9999
        return (starts, position, name)
