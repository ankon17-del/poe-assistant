import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models import all as _models  # noqa: F401
from app.models.template import TemplateGroup, TemplateItem


DEFAULT_TEMPLATES = [
    {
        "name": "Currency Farming",
        "description": "Baseline currency watchers for either game.",
        "category": "currency",
        "items": [
            ("Divine Orb", "currency", Decimal("15")),
            ("Exalted Orb", "currency", Decimal("8"), "chaos"),
        ],
    },
    {
        "name": "POE2 Starter Economy",
        "description": "A clean starter setup for POE2 currency tracking.",
        "category": "currency",
        "items": [
            ("Divine Orb", "currency", Decimal("160"), "chaos"),
            ("Exalted Orb", "currency", Decimal("9"), "chaos"),
        ],
    },
    {
        "name": "POE2 Exchange Watch",
        "description": "Useful POE2 exchange checkpoints for daily market checks.",
        "category": "currency",
        "items": [
            ("Divine Orb", "currency", Decimal("17"), "ex"),
            ("Exalted Orb", "currency", Decimal("9"), "chaos"),
        ],
    },
    {
        "name": "POE1 Currency Farming",
        "description": "Baseline POE1 currency checkpoints for farming sessions.",
        "category": "currency",
        "items": [
            ("Divine Orb", "currency", Decimal("12"), "ex"),
            ("Exalted Orb", "currency", Decimal("10"), "chaos"),
        ],
    },
    {
        "name": "Essence Farming",
        "description": "High-signal POE1 essences for quick sale tracking.",
        "category": "farming",
        "items": [
            ("Deafening Essence of Contempt", "essence", Decimal("1"), "ex"),
            ("Deafening Essence of Wrath", "essence", Decimal("1"), "ex"),
            ("Deafening Essence of Loathing", "essence", Decimal("1"), "ex"),
        ],
    },
    {
        "name": "Boss Drops",
        "description": "Popular POE1 boss uniques and chase drops.",
        "category": "bossing",
        "items": [
            ("Watcher's Eye", "unique", None, "ex"),
            ("Awakened Multistrike Support", "gem", None, "ex"),
            ("Forbidden Flame", "jewel", None, "ex"),
        ],
    },
    {
        "name": "Scarab Market",
        "description": "Common POE1 scarab market movers.",
        "category": "mapping",
        "items": [
            ("Divination Scarab", "scarab", Decimal("1"), "ex"),
            ("Ambush Scarab", "scarab", Decimal("1"), "ex"),
            ("Expedition Scarab", "scarab", Decimal("1"), "ex"),
        ],
    },
]


async def main() -> None:
    async with async_session_factory() as session:
        for template_data in DEFAULT_TEMPLATES:
            existing = await session.scalar(
                select(TemplateGroup)
                .where(TemplateGroup.name == template_data["name"])
                .options(selectinload(TemplateGroup.items))
            )

            group = existing or TemplateGroup(name=template_data["name"])
            group.description = template_data["description"]
            group.category = template_data["category"]
            group.is_public = True
            group.items = [
                TemplateItem(
                    item_name=item_name,
                    item_type=item_type,
                    default_threshold=threshold,
                    default_target_currency=target_currency,
                    priority=index * 10,
                )
                for index, (item_name, item_type, threshold, target_currency) in enumerate(
                    template_data["items"], start=1
                )
            ]
            if existing is None:
                session.add(group)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
