from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.template import TemplateGroup
from app.models.tracked_item import TrackedItem


def templates_keyboard(templates: list[TemplateGroup]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{template.name} ({len(template.items)} шт.)",
                callback_data=f"template:{template.id}",
            )
        ]
        for template in templates
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tracking_actions_keyboard(items: list[TrackedItem]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Отключить #{item.id}", callback_data=f"tracking:remove:{item.id}")]
        for item in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
