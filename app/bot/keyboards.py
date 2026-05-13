from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.i18n import LANGUAGE_NAMES, SUPPORTED_LOCALES, tr
from app.models.league import League
from app.models.template import TemplateGroup
from app.models.tracked_item import TrackedItem
from app.services.builds import BuildRecommendation


def home_menu_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=tr(locale, "templates"), callback_data="menu:templates"),
                InlineKeyboardButton(text=tr(locale, "economy"), callback_data="menu:economy"),
            ],
            [
                InlineKeyboardButton(text=tr(locale, "builds"), callback_data="menu:builds"),
                InlineKeyboardButton(text=tr(locale, "tracking"), callback_data="menu:tracking"),
            ],
            [
                InlineKeyboardButton(text=tr(locale, "alerts"), callback_data="menu:alerts"),
                InlineKeyboardButton(text=tr(locale, "account"), callback_data="menu:account"),
            ],
            [
                InlineKeyboardButton(text=tr(locale, "stash"), callback_data="menu:stash"),
                InlineKeyboardButton(text=tr(locale, "help"), callback_data="menu:help"),
            ],
        ]
    )


def menu_section_keyboard(*buttons: tuple[str, str], include_home: bool = True, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=text, callback_data=callback_data)] for text, callback_data in buttons]
    if include_home:
        rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def with_home_button(markup: InlineKeyboardMarkup, *, label: str | None = None, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [list(row) for row in markup.inline_keyboard]
    rows.append([InlineKeyboardButton(text=label or tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def language_keyboard(current_locale: str | None = None, *, back_callback: str = "menu:home") -> InlineKeyboardMarkup:
    locale = current_locale or "ru"
    rows = []
    for code in SUPPORTED_LOCALES:
        prefix = "• " if code == locale else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{LANGUAGE_NAMES[code]}", callback_data=f"settings:language:{code}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=back_callback)])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def templates_keyboard(
    templates: list[TemplateGroup],
    game: str | None = None,
    *,
    back_callback: str = "templates:choose_game",
    locale: str = "ru",
) -> InlineKeyboardMarkup:
    game_label = "POE 2" if game == "poe2" else "POE 1" if game == "poe1" else None
    rows = [
        [
            InlineKeyboardButton(
                text=f"{template.name} ({len(template.items)})" if not game_label else f"{template.name} ({len(template.items)}) · {game_label}",
                callback_data=(f"template_select:{game}:{template.id}" if game else f"template:{template.id}"),
            )
        ]
        for template in templates
    ]
    if game:
        rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=back_callback)])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_browser_game_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="templates:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="templates:game:poe1")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")],
        ]
    )


def template_goal_keyboard(game: str, goals: list, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=goal.title, callback_data=f"templates:goal:{game}:{goal.key}")] for goal in goals]
    rows.append([InlineKeyboardButton(text=tr(locale, "show_all_templates"), callback_data=f"templates:all:{game}")])
    rows.append([InlineKeyboardButton(text=f"{tr(locale, 'back')} · POE", callback_data="templates:choose_game")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_game_keyboard(template_id: int, locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data=f"template_game:{template_id}:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data=f"template_game:{template_id}:poe1")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")],
        ]
    )


def template_preview_keyboard(template_id: int, game: str, locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(locale, "choose_strategy"), callback_data=f"template_strategy:{template_id}:{game}:balanced")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"templates:goals:{game}")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")],
        ]
    )


def template_strategy_keyboard(template_id: int, game: str, strategies: list, selected_key: str, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = []
    for strategy in strategies:
        prefix = "• " if strategy.key == selected_key else ""
        rows.append([InlineKeyboardButton(text=f"{prefix}{strategy.title}", callback_data=f"template_strategy:{template_id}:{game}:{strategy.key}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "choose_league"), callback_data=f"template_strategy_league:{template_id}:{game}:{selected_key}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"template_back:{template_id}:{game}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_league_keyboard(template_id: int, leagues: list[League], game: str, strategy_key: str, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=league.name, callback_data=f"template_strategy_apply:{template_id}:{league.id}:{strategy_key}")] for league in leagues]
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"template_strategy:{template_id}:{game}:{strategy_key}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="template:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tracking_actions_keyboard(items: list[TrackedItem], locale: str = "ru") -> InlineKeyboardMarkup:
    restart_label = {"ru": "перезапустить", "en": "restart", "fr": "relancer", "de": "neu starten"}.get(locale, "restart")
    off_label = {"ru": "отключить", "en": "disable", "fr": "désactiver", "de": "deaktivieren"}.get(locale, "disable")
    rows = []
    for item in items:
        if item.target_price is not None and not item.notify_enabled:
            rows.append([InlineKeyboardButton(text=f"{tr(locale, 'alerts')} #{item.id} · {restart_label}", callback_data=f"list2:reactivate:{item.id}")])
        rows.append([InlineKeyboardButton(text=f"{tr(locale, 'tracking')} #{item.id} · {off_label}", callback_data=f"list2:remove:{item.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def paused_alerts_keyboard(items: list[TrackedItem], locale: str = "ru") -> InlineKeyboardMarkup:
    all_on = {"ru": "включить все", "en": "all on", "fr": "tout activer", "de": "alle aktivieren"}.get(locale, "all on")
    on_label = {"ru": "включить", "en": "enable", "fr": "activer", "de": "aktivieren"}.get(locale, "enable")
    off_label = {"ru": "отключить", "en": "disable", "fr": "désactiver", "de": "deaktivieren"}.get(locale, "disable")
    rows = []
    if items:
        rows.append([InlineKeyboardButton(text=f"{tr(locale, 'alerts')} · {all_on}", callback_data="alerts:reactivate_all")])
        has_poe1 = any(item.league and item.league.realm == "poe1" for item in items)
        has_poe2 = any(item.league and item.league.realm == "poe2" for item in items)
        if has_poe1:
            rows.append([InlineKeyboardButton(text=f"POE 1 · {all_on}", callback_data="alerts:reactivate_game:poe1")])
        if has_poe2:
            rows.append([InlineKeyboardButton(text=f"POE 2 · {all_on}", callback_data="alerts:reactivate_game:poe2")])
    for item in items:
        rows.append([InlineKeyboardButton(text=f"#{item.id} · {on_label}", callback_data=f"alerts:reactivate:{item.id}")])
        rows.append([InlineKeyboardButton(text=f"#{item.id} · {off_label}", callback_data=f"alerts:remove:{item.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def account_keyboard(connect_url: str | None, is_connected: bool, locale: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if connect_url:
        rows.append([InlineKeyboardButton(text=tr(locale, "connect_account"), url=connect_url)])
    rows.append([InlineKeyboardButton(text=tr(locale, "refresh_status"), callback_data="account:refresh")])
    if is_connected:
        rows.append([InlineKeyboardButton(text=tr(locale, "disconnect_account"), callback_data="account:disconnect")])
    rows.append([InlineKeyboardButton(text=tr(locale, "language"), callback_data="settings:language_menu")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stash_keyboard(connect_url: str | None, account_connected: bool, locale: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if connect_url and not account_connected:
        rows.append([InlineKeyboardButton(text=tr(locale, "connect_account"), url=connect_url)])
    rows.append([InlineKeyboardButton(text=tr(locale, "quick_stash_triage"), callback_data="stash:guide:triage")])
    rows.append([InlineKeyboardButton(text=tr(locale, "what_to_sell_fast"), callback_data="stash:guide:liquid")])
    rows.append([InlineKeyboardButton(text=tr(locale, "check_uniques"), callback_data="stash:guide:uniques")])
    rows.append([InlineKeyboardButton(text=tr(locale, "check_currency"), callback_data="stash:guide:currency")])
    rows.append([InlineKeyboardButton(text=tr(locale, "refresh_stash"), callback_data="stash:refresh")])
    rows.append([InlineKeyboardButton(text=tr(locale, "open_account"), callback_data="stash:account")])
    rows.append([InlineKeyboardButton(text=tr(locale, "language"), callback_data="settings:language_menu")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def stash_guide_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data="stash:back:panel")],
            [InlineKeyboardButton(text=tr(locale, "open_account"), callback_data="stash:account")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
        ]
    )


def build_game_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="builds:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="builds:game:poe1")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
        ]
    )


def build_goal_keyboard(game: str, locale: str = "ru") -> InlineKeyboardMarkup:
    goal_titles = {
        "ru": ["Старт лиги", "Фарм валюты", "Комфортный прогресс", "Убить боссов"],
        "en": ["League start", "Currency farm", "Comfortable progress", "Kill bosses"],
        "fr": ["Début de ligue", "Farm de currency", "Progression confortable", "Tuer des boss"],
        "de": ["Liga-Start", "Currency farmen", "Bequemer Fortschritt", "Bosse töten"],
    }
    titles = goal_titles.get(locale, goal_titles["ru"])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=titles[0], callback_data=f"builds:goal:{game}:league_start")],
            [InlineKeyboardButton(text=titles[1], callback_data=f"builds:goal:{game}:currency_farm")],
            [InlineKeyboardButton(text=titles[2], callback_data=f"builds:goal:{game}:comfortable_progress")],
            [InlineKeyboardButton(text=titles[3], callback_data=f"builds:goal:{game}:boss_kill")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data="builds:back:game")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
        ]
    )


def build_budget_keyboard(game: str, goal: str, locale: str = "ru") -> InlineKeyboardMarkup:
    titles = {
        "ru": ("Стартовый", "Средний", "Высокий"),
        "en": ("Starter", "Mid", "High"),
        "fr": ("Départ", "Moyen", "Élevé"),
        "de": ("Starter", "Mittel", "Hoch"),
    }.get(locale, ("Стартовый", "Средний", "Высокий"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=titles[0], callback_data=f"builds:budget:{game}:{goal}:starter")],
            [InlineKeyboardButton(text=titles[1], callback_data=f"builds:budget:{game}:{goal}:mid")],
            [InlineKeyboardButton(text=titles[2], callback_data=f"builds:budget:{game}:{goal}:high")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"builds:back:goal:{game}")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
        ]
    )


def build_playstyle_keyboard(game: str, goal: str, budget_tier: str, locale: str = "ru") -> InlineKeyboardMarkup:
    titles = {
        "ru": ("Быстрый фарм", "Спокойный / живучий", "Боссинг", "Универсальный"),
        "en": ("Fast farming", "Safe / tanky", "Bossing", "All-round"),
        "fr": ("Farm rapide", "Safe / tanky", "Bossing", "Polyvalent"),
        "de": ("Schneller Farm", "Sicher / tanky", "Bossing", "Allround"),
    }.get(locale, ("Быстрый фарм", "Спокойный / живучий", "Боссинг", "Универсальный"))
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=titles[0], callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:speed")],
            [InlineKeyboardButton(text=titles[1], callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:safe")],
            [InlineKeyboardButton(text=titles[2], callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:boss")],
            [InlineKeyboardButton(text=titles[3], callback_data=f"builds:playstyle:{game}:{goal}:{budget_tier}:allround")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"builds:back:budget:{game}:{goal}")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
        ]
    )


def build_recommendation_list_keyboard(game: str, goal: str, budget_tier: str, playstyle: str, recommendations: list[BuildRecommendation], locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=recommendation.title, callback_data=f"builds:detail:{game}:{goal}:{budget_tier}:{playstyle}:{index}")] for index, recommendation in enumerate(recommendations)]
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"builds:back:playstyle:{game}:{goal}:{budget_tier}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_detail_keyboard(game: str, goal: str, budget_tier: str, playstyle: str, recommendation_index: int, recommendation: BuildRecommendation | None, locale: str = "ru") -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if recommendation:
        if recommendation.planner_url:
            rows.append([InlineKeyboardButton(text="Planner", url=recommendation.planner_url)])
        if recommendation.guide_url:
            rows.append([InlineKeyboardButton(text="Guide", url=recommendation.guide_url)])
        if recommendation.tree_url:
            rows.append([InlineKeyboardButton(text="Tree", url=recommendation.tree_url)])
        if recommendation.atlas_url:
            rows.append([InlineKeyboardButton(text="Atlas", url=recommendation.atlas_url)])
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data=f"builds:back:list:{game}:{goal}:{budget_tier}:{playstyle}")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_entry_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(locale, "search_by_name"), callback_data="add:mode:item")],
            [InlineKeyboardButton(text=tr(locale, "trade_url"), callback_data="add:mode:trade_url")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")],
        ]
    )


def game_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="POE 2", callback_data="add:game:poe2")],
            [InlineKeyboardButton(text="POE 1", callback_data="add:game:poe1")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")],
        ]
    )


def league_keyboard(leagues: list[League], locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=league.name, callback_data=f"add:league:{league.id}")] for league in leagues]
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data="add:back:game")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def currency_presets_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Divine Orb", callback_data="add:preset_currency:divine_orb")],
            [InlineKeyboardButton(text="Exalted Orb", callback_data="add:preset_currency:exalted_orb")],
            [InlineKeyboardButton(text="Chaos Orb", callback_data="add:preset_currency:chaos_orb")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data="add:back:league")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")],
        ]
    )


def search_results_keyboard(results: list[str], query: str, locale: str = "ru") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=item_name, callback_data=f"add:item:{index}")] for index, item_name in enumerate(results)]
    rows.append([InlineKeyboardButton(text=tr(locale, "use_exact", query=query), callback_data="add:item:exact")])
    rows.append([InlineKeyboardButton(text=tr(locale, "back"), callback_data="add:back:league")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def threshold_currency_keyboard(locale: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Exalted (ex)", callback_data="add:currency:ex")],
            [InlineKeyboardButton(text="Chaos", callback_data="add:currency:chaos")],
            [InlineKeyboardButton(text="Divine", callback_data="add:currency:div")],
            [InlineKeyboardButton(text=tr(locale, "back"), callback_data="add:back:item")],
            [InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")],
            [InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")],
        ]
    )


def duplicate_resolution_keyboard(items: list[TrackedItem], locale: str = "ru") -> InlineKeyboardMarkup:
    update_label = {"ru": "Обновить", "en": "Update", "fr": "Mettre à jour", "de": "Aktualisieren"}.get(locale, "Update")
    create_label = {"ru": "Создать новый", "en": "Create new", "fr": "Créer un nouveau", "de": "Neu erstellen"}.get(locale, "Create new")
    rows = [[InlineKeyboardButton(text=f"{update_label} #{item.id}", callback_data=f"add:resolve:update:{item.id}")] for item in items]
    rows.append([InlineKeyboardButton(text=create_label, callback_data="add:resolve:create")])
    rows.append([InlineKeyboardButton(text=tr(locale, "home"), callback_data="menu:home")])
    rows.append([InlineKeyboardButton(text=tr(locale, "cancel"), callback_data="add:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
