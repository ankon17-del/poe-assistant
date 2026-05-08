import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.template import TemplateGroup, TemplateItem


DEFAULT_TEMPLATES = [
    {
        "name": "Currency Farming",
        "description": "Core currency items for farming sessions.",
        "category": "currency",
        "items": [
            ("Divine Orb", "currency", Decimal("1")),
            ("Exalted Orb", "currency", Decimal("1")),
            ("Chaos Orb", "currency", Decimal("1")),
        ],
    },
    {
        "name": "Essence Farming",
        "description": "High-signal essences for quick sale tracking.",
        "category": "farming",
        "items": [
            ("Deafening Essence of Contempt", "essence", Decimal("1")),
            ("Deafening Essence of Wrath", "essence", Decimal("1")),
            ("Deafening Essence of Loathing", "essence", Decimal("1")),
        ],
    },
    {
        "name": "Boss Drops",
        "description": "Popular boss uniques and fragments.",
        "category": "bossing",
        "items": [
            ("Watcher's Eye", "unique", None),
            ("Awakened Multistrike Support", "gem", None),
            ("Forbidden Flame", "jewel", None),
        ],
    },
    {
        "name": "Scarab Market",
        "description": "Common scarab market movers.",
        "category": "mapping",
        "items": [
            ("Divination Scarab", "scarab", Decimal("1")),
            ("Ambush Scarab", "scarab", Decimal("1")),
            ("Expedition Scarab", "scarab", Decimal("1")),
        ],
    },
]


async def main() -> None:
    async with async_session_factory() as session:
        for template_data in DEFAULT_TEMPLATES:
            existing = await session.scalar(
                select(TemplateGroup).where(TemplateGroup.name == template_data["name"])
            )
            if existing:
                continue

            group = TemplateGroup(
                name=template_data["name"],
                description=template_data["description"],
                category=template_data["category"],
                is_public=True,
            )
            group.items = [
                TemplateItem(
                    item_name=item_name,
                    item_type=item_type,
                    default_threshold=threshold,
                    priority=index * 10,
                )
                for index, (item_name, item_type, threshold) in enumerate(template_data["items"], start=1)
            ]
            session.add(group)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())

