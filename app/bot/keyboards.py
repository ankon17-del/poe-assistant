from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.league import League
from app.models.template import TemplateGroup
from app.models.tracked_item import TrackedItem
from app.services.builds import BuildRecommendation


def templates_keyboard(templates: list[TemplateGroup], game: str | None = None) -> InlineKeyboardMarkup:
    game_label = "POE 2" if game == "poe2" else "POE 1" if game == "poe1" else None
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{template.name} ({len(template.items)} шт.)"
                    if not game_label
                    else f"{template.name} ({len(template.items)} шт.) · {game_label}"
                ),
                callback_data=(f"template_select:{game}:{template.id}" if game else f"template:{template.id}"),
            )
        ]
        for template in templates
    ]
    if game:
        rows.append([InlineKeyboardButton(text="Назад", callback_data="templates:choose_game")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="template:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_browser_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="templates:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="templates:game:poe1")],
            [InlineKeyboardButton(text="Отмена", callback_data="template:cancel")],
        ]
    )


def template_game_keyboard(template_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data=f"template_game:{template_id}:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data=f"template_game:{template_id}:poe1")],
            [InlineKeyboardButton(text="Отмена", callback_data="template:cancel")],
        ]
    )


def template_preview_keyboard(template_id: int, game: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Выбрать лигу", callback_data=f"template_pick_league:{template_id}:{game}")],
            [InlineKeyboardButton(text="Назад", callback_data="templates:choose_game")],
            [InlineKeyboardButton(text="Отмена", callback_data="template:cancel")],
        ]
    )


def template_league_keyboard(template_id: int, leagues: list[League], game: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=league.name, callback_data=f"template_league:{template_id}:{league.id}")]
        for league in leagues
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=f"template_back:{template_id}:{game}")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="template:cancel")])
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


def account_keyboard(connect_url: str | None, is_connected: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if connect_url:
        rows.append([InlineKeyboardButton(text="Подключить PoE аккаунт", url=connect_url)])
    rows.append([InlineKeyboardButton(text="Обновить статус", callback_data="account:refresh")])
    if is_connected:
        rows.append([InlineKeyboardButton(text="Отключить аккаунт", callback_data="account:disconnect")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stash_keyboard(connect_url: str | None, account_connected: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if connect_url and not account_connected:
        rows.append([InlineKeyboardButton(text="Подключить PoE аккаунт", url=connect_url)])
    rows.append([InlineKeyboardButton(text="Обновить stash-анализ", callback_data="stash:refresh")])
    rows.append([InlineKeyboardButton(text="Открыть панель аккаунта", callback_data="stash:account")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_game_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="builds:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="builds:game:poe1")],
        ]
    )


def build_goal_keyboard(game: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Старт лиги", callback_data=f"builds:goal:{game}:league_start")],
            [InlineKeyboardButton(text="Фарм валюты", callback_data=f"builds:goal:{game}:currency_farm")],
            [InlineKeyboardButton(text="Комфортный прогресс", callback_data=f"builds:goal:{game}:comfortable_progress")],
            [InlineKeyboardButton(text="Убить боссов", callback_data=f"builds:goal:{game}:boss_kill")],
            [InlineKeyboardButton(text="Назад", callback_data="builds:back:game")],
        ]
    )


def build_budget_keyboard(game: str, goal: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Стартовый", callback_data=f"builds:budget:{game}:{goal}:starter")],
            [InlineKeyboardButton(text="Средний", callback_data=f"builds:budget:{game}:{goal}:mid")],
            [InlineKeyboardButton(text="Высокий", callback_data=f"builds:budget:{game}:{goal}:high")],
            [InlineKeyboardButton(text="Назад", callback_data=f"builds:back:goal:{game}")],
        ]
    )


def build_playstyle_keyboard(game: str, goal: str, budget_tier: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Быстрый фарм", callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:speed")],
            [InlineKeyboardButton(text="Спокойный / живучий", callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:safe")],
            [InlineKeyboardButton(text="Боссинг", callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:boss")],
            [InlineKeyboardButton(text="Универсальный", callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:allround")],
            [InlineKeyboardButton(text="Назад", callback_data=f"builds:back:budget:{game}:{goal}")],
        ]
    )


def build_recommendation_list_keyboard(
    game: str,
    goal: str,
    budget_tier: str,
    playstyle: str,
    recommendations: list[BuildRecommendation],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=recommendation.title,
                callback_data=f"builds:detail:{game}:{goal}:{budget_tier}:{playstyle}:{index}",
            )
        ]
        for index, recommendation in enumerate(recommendations)
    ]
    rows.append([InlineKeyboardButton(text="Назад к стилю", callback_data=f"builds:back:playstyle:{game}:{goal}:{budget_tier}")])
    rows.append([InlineKeyboardButton(text="Назад к бюджету", callback_data=f"builds:back:budget:{game}:{goal}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_detail_keyboard(
    game: str,
    goal: str,
    budget_tier: str,
    playstyle: str,
    recommendation_index: int,
    recommendation: BuildRecommendation | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if recommendation:
        if recommendation.planner_url:
            rows.append([InlineKeyboardButton(text="Открыть Planner", url=recommendation.planner_url)])
        if recommendation.guide_url:
            rows.append([InlineKeyboardButton(text="Открыть Guide", url=recommendation.guide_url)])
        if recommendation.tree_url:
            tree_label = "Открыть Tree в Planner" if recommendation.tree_url == recommendation.planner_url else "Открыть Tree"
            rows.append([InlineKeyboardButton(text=tree_label, url=recommendation.tree_url)])
        if recommendation.atlas_url:
            if recommendation.atlas_url == recommendation.guide_url:
                atlas_label = "Открыть Atlas в Guide"
            elif recommendation.atlas_url == recommendation.planner_url or recommendation.atlas_url == recommendation.tree_url:
                atlas_label = "Открыть Atlas в Planner"
            else:
                atlas_label = "Открыть Atlas"
            rows.append([InlineKeyboardButton(text=atlas_label, url=recommendation.atlas_url)])
    rows.append([InlineKeyboardButton(text="Назад к подборке", callback_data=f"builds:back:list:{game}:{goal}:{budget_tier}:{playstyle}")])
    rows.append([InlineKeyboardButton(text="Назад к стилю", callback_data=f"builds:back:playstyle:{game}:{goal}:{budget_tier}")])
    rows.append([InlineKeyboardButton(text="Назад к бюджету", callback_data=f"builds:back:budget:{game}:{goal}")])
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
