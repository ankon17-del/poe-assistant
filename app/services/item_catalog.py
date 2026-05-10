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

        query_tokens = [token for token in normalized_query.split() if token]
        ranked = sorted(all_names, key=lambda name: self._sort_key(name=name, query=normalized_query))
        filtered = [
            name
            for name in ranked
            if self._matches_query(name=name, raw_query=normalized_query, query_tokens=query_tokens)
        ]
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
        exact = 0 if lowered == query else 1
        starts = 0 if lowered.startswith(query) else 1
        word_starts = 0 if any(part.startswith(query) for part in lowered.replace("-", " ").split()) else 1
        contains_index = lowered.find(query) if query else 9999
        position = contains_index if contains_index >= 0 else 9999
        return (exact, starts, word_starts, position, len(name), name)

    @staticmethod
    def _matches_query(name: str, raw_query: str, query_tokens: list[str]) -> bool:
        lowered = name.lower()
        if raw_query and raw_query in lowered:
            return True
        if not query_tokens:
            return False
        normalized_words = lowered.replace("-", " ").split()
        return all(
            any(token in word or word.startswith(token) for word in normalized_words)
            for token in query_tokens
        )
