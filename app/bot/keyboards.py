from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.template import TemplateGroup


def templates_keyboard(templates: list[TemplateGroup]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=template.name, callback_data=f"template:{template.id}")]
        for template in templates
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

