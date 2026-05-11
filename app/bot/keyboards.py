from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.league import League
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
    rows = []
    for item in items:
        if item.target_price is not None and not item.notify_enabled:
            rows.append(
                [InlineKeyboardButton(text=f"Перезапустить #{item.id}", callback_data=f"list2:reactivate:{item.id}")]
            )
        rows.append([InlineKeyboardButton(text=f"Отключить #{item.id}", callback_data=f"list2:remove:{item.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def paused_alerts_keyboard(items: list[TrackedItem]) -> InlineKeyboardMarkup:
    rows = []
    if items:
        rows.append([InlineKeyboardButton(text="Перезапустить все", callback_data="alerts:reactivate_all")])
        has_poe1 = any(item.league and item.league.realm == "poe1" for item in items)
        has_poe2 = any(item.league and item.league.realm == "poe2" for item in items)
        if has_poe1:
            rows.append([InlineKeyboardButton(text="Перезапустить все POE 1", callback_data="alerts:reactivate_game:poe1")])
        if has_poe2:
            rows.append([InlineKeyboardButton(text="Перезапустить все POE 2", callback_data="alerts:reactivate_game:poe2")])
    for item in items:
        rows.append([InlineKeyboardButton(text=f"Перезапустить #{item.id}", callback_data=f"alerts:reactivate:{item.id}")])
        rows.append([InlineKeyboardButton(text=f"Отключить #{item.id}", callback_data=f"alerts:remove:{item.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_entry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поиск по названию", callback_data="add:mode:item")],
            [InlineKeyboardButton(text="Trade URL", callback_data="add:mode:trade_url")],
            [InlineKeyboardButton(text="Отмена", callback_data="add:cancel")],
        ]
    )


def game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="add:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="add:game:poe1")],
            [InlineKeyboardButton(text="Отмена", callback_data="add:cancel")],
        ]
    )


def league_keyboard(leagues: list[League]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=league.name, callback_data=f"add:league:{league.id}")]
        for league in leagues
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="add:back:game")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def currency_presets_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Divine Orb", callback_data="add:preset_currency:divine_orb")],
            [InlineKeyboardButton(text="Exalted Orb", callback_data="add:preset_currency:exalted_orb")],
            [InlineKeyboardButton(text="Chaos Orb", callback_data="add:preset_currency:chaos_orb")],
            [InlineKeyboardButton(text="Назад", callback_data="add:back:league")],
            [InlineKeyboardButton(text="Отмена", callback_data="add:cancel")],
        ]
    )


def search_results_keyboard(results: list[str], query: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=item_name, callback_data=f"add:item:{index}")]
        for index, item_name in enumerate(results)
    ]
    rows.append([InlineKeyboardButton(text=f"Использовать: {query}", callback_data="add:item:exact")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="add:back:league")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def threshold_currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Exalted (ex)", callback_data="add:currency:ex")],
            [InlineKeyboardButton(text="Chaos", callback_data="add:currency:chaos")],
            [InlineKeyboardButton(text="Divine", callback_data="add:currency:div")],
            [InlineKeyboardButton(text="Назад", callback_data="add:back:item")],
            [InlineKeyboardButton(text="Отмена", callback_data="add:cancel")],
        ]
    )


def duplicate_resolution_keyboard(items: list[TrackedItem]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Обновить #{item.id}", callback_data=f"add:resolve:update:{item.id}")]
        for item in items
    ]
    rows.append([InlineKeyboardButton(text="Создать новый", callback_data="add:resolve:create")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
