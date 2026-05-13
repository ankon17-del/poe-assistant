from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.dependencies import session_scope
from app.bot.keyboards import (
    add_entry_keyboard,
    account_keyboard,
    build_budget_keyboard,
    build_detail_keyboard,
    build_game_keyboard,
    build_goal_keyboard,
    build_playstyle_keyboard,
    build_recommendation_list_keyboard,
    currency_presets_keyboard,
    duplicate_resolution_keyboard,
    game_keyboard,
    league_keyboard,
    home_menu_keyboard,
    menu_section_keyboard,
    paused_alerts_keyboard,
    search_results_keyboard,
    stash_keyboard,
    stash_guide_keyboard,
    template_browser_game_keyboard,
    template_game_keyboard,
    template_goal_keyboard,
    template_league_keyboard,
    template_preview_keyboard,
    template_strategy_keyboard,
    templates_keyboard,
    threshold_currency_keyboard,
    tracking_actions_keyboard,
    with_home_button,
)
from app.services.builds import BuildRecommendation, BuildService
from app.models.enums import IntegrationType
from app.models.league import League
from app.services.economy import EconomyService
from app.services.integrations import IntegrationService
from app.services.item_catalog import ItemCatalogService
from app.services.leagues import LeagueService
from app.services.poe_oauth import PoeOAuthConfigError, PoeOAuthService
from app.services.stats import StatsService
from app.services.stash import StashService
from app.services.templates import TemplateService
from app.services.tracking import TrackingService
from app.services.users import UserService

router = Router()


class AddTrackingStates(StatesGroup):
    choosing_mode = State()
    choosing_game = State()
    choosing_league = State()
    entering_search = State()
    choosing_currency = State()
    entering_trade_url = State()
    entering_trade_name = State()
    entering_threshold = State()
    resolving_duplicate = State()


async def ensure_user(session, telegram_id: int, username: str | None):
    return await UserService(session).get_or_create(telegram_id=telegram_id, username=username)


def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def build_tracking_lines(item) -> list[str]:
    league_name = item.league.name if item.league else "Без лиги"
    game_label = "POE 2" if item.league and item.league.realm == "poe2" else "POE 1"
    lines = [f"#{item.id} · {item.item_name}", f"{game_label} / {league_name}"]
    if item.target_price is not None:
        lines.append(f"Порог: {format_decimal(Decimal(item.target_price))} {item.target_currency}")
        status_label = "активен" if item.notify_enabled else "сработал, ждёт перезапуска"
        lines.append(f"Статус: {status_label}")
    elif item.trade_url:
        lines.append("Статус: активен")
    if item.trade_url:
        lines.append("Источник: trade URL")
    return lines


def build_tracking_list_text(items: list) -> str:
    lines = [f"Трекинг · {len(items)}"]
    grouped: dict[tuple[str, str], list] = {}
    for item in items:
        game_label = "POE 2" if item.league and item.league.realm == "poe2" else "POE 1"
        league_name = item.league.name if item.league else "Без лиги"
        grouped.setdefault((game_label, league_name), []).append(item)

    for (game_label, league_name), group_items in sorted(grouped.items(), key=lambda entry: (entry[0][0], entry[0][1])):
        lines.append("")
        lines.append(f"{game_label} / {league_name} · {len(group_items)}")
        for item in group_items:
            lines.append("\n".join(build_tracking_lines(item)))
    return "\n\n".join(lines)


def build_paused_alerts_text(items: list) -> str:
    poe1_count = sum(1 for item in items if item.league and item.league.realm == "poe1")
    poe2_count = sum(1 for item in items if item.league and item.league.realm == "poe2")

    lines = [f"Алерты на паузе · {len(items)}"]
    if poe1_count:
        lines.append(f"POE 1: {poe1_count}")
    if poe2_count:
        lines.append(f"POE 2: {poe2_count}")
    lines.append("")
    for item in items:
        lines.append("\n".join(build_tracking_lines(item)))
    lines.append("")
    lines.append("Можно перезапустить alert целиком, по игре или отключить его совсем.")
    return "\n\n".join(lines)


def build_account_text(*, integration, oauth_config_error: str | None) -> str:
    lines = ["Аккаунт"]
    if integration:
        lines.append("Статус: подключён")
        if integration.external_account_name:
            lines.append(f"Аккаунт: {integration.external_account_name}")
        if integration.scopes:
            lines.append(f"Scopes: {integration.scopes}")
    else:
        lines.append("Статус: не подключён")

    if oauth_config_error:
        lines.append("")
        lines.append(f"OAuth сейчас недоступен: {oauth_config_error}")
    elif integration:
        lines.append("")
        lines.append("Можно обновить статус или отключить привязку ниже.")
    else:
        lines.append("")
        lines.append("Нажми кнопку ниже, чтобы привязать аккаунт Path of Exile к Telegram.")

    return "\n".join(lines)


def build_stash_text(summary) -> str:
    lines = ["Тайник", ""]

    if summary.account_connected:
        if summary.account_name:
            lines.append(f"PoE аккаунт: подключён ({summary.account_name})")
        else:
            lines.append("PoE аккаунт: подключён")
    else:
        lines.append("PoE аккаунт: пока не подключён")

    if summary.approved_scopes:
        lines.append(f"Scopes: {' '.join(summary.approved_scopes)}")

    if summary.oauth_blocker:
        lines.append(f"Блокер OAuth: {summary.oauth_blocker}")

    lines.append("")
    lines.append("Статус готовности:")
    for item in summary.statuses:
        lines.append(f"- {item.title}: {item.status}")
        lines.append(f"  {item.detail}")

    lines.append("")
    lines.append("Что здесь появится:")
    for insight in summary.upcoming_insights:
        lines.append(f"- {insight}")

    lines.append("")
    lines.append("Следующие шаги:")
    for step in summary.next_steps:
        lines.append(f"- {step}")

    lines.append("")
    lines.append("Phase 6 уже начата: UX и сервисный фундамент готовы, дальше нам нужны account-data и stash-scopes.")
    return "\n".join(lines)


def build_stash_guide_text(guide) -> str:
    lines = [
        f"Stash assistant · {guide.title}",
        "",
        guide.summary,
    ]
    for section_title, bullets in guide.sections:
        lines.append("")
        lines.append(section_title)
        lines.extend(f"- {bullet}" for bullet in bullets)
    lines.append("")
    lines.append("Это ручной playbook: уже полезно без OAuth, а потом мы наложим на него живой stash-scan и автоматические инсайты.")
    return "\n".join(lines)


def build_template_preview_text(template, game: str) -> str:
    game_label = "POE 2" if game == "poe2" else "POE 1"
    lines = [f"Шаблон: {template.name}", f"Игра: {game_label}"]
    if template.description:
        lines.append(template.description)
    lines.append("")
    lines.append("Будет добавлено:")
    for item in template.items:
        item_line = f"- {item.item_name}"
        details: list[str] = []
        if item.item_type:
            details.append(item.item_type)
        if item.default_threshold is not None:
            details.append(f">= {format_decimal(Decimal(item.default_threshold))} {item.default_target_currency}")
        if details:
            item_line += f" ({', '.join(details)})"
        lines.append(item_line)
    lines.append("")
    lines.append("Если всё подходит, дальше выберем лигу и применим шаблон туда.")
    return "\n".join(lines)


def build_template_activation_text(result, league) -> str:
    game_label = "POE 2" if league.realm == "poe2" else "POE 1"
    lines = [
        f"Шаблон {result.template_name} подключен.",
        f"Игра: {game_label}",
        f"Лига: {league.name}",
        f"Создано watcher'ов: {result.created_count}",
        f"Обновлено или реактивировано: {result.updated_count}",
    ]

    if result.created_items:
        lines.append("")
        lines.append("Созданы:")
        lines.extend(f"- {item_name}" for item_name in result.created_items)

    if result.updated_items:
        lines.append("")
        lines.append("Обновлены или реактивированы:")
        lines.extend(f"- {item_name}" for item_name in result.updated_items)

    return "\n".join(lines)


def build_template_preview_text(template, game: str, strategy=None, resolved_items: list | None = None) -> str:
    game_label = "POE 2" if game == "poe2" else "POE 1"
    lines = [f"Шаблон: {template.name}", f"Игра: {game_label}"]
    if template.description:
        lines.append(template.description)
    if strategy is None or resolved_items is None:
        lines.extend(["", "Будет добавлено:"])
        for item in template.items:
            item_line = f"- {item.item_name}"
            details: list[str] = []
            if item.item_type:
                details.append(item.item_type)
            if item.default_threshold is not None:
                details.append(f">= {format_decimal(Decimal(item.default_threshold))} {item.default_target_currency}")
            if details:
                item_line += f" ({', '.join(details)})"
            lines.append(item_line)
        lines.extend(["", "Если всё подходит, дальше выберем стратегию и лигу для применения шаблона."])
        return "\n".join(lines)

    lines.extend(
        [
            "",
            f"Стратегия: {strategy.title}",
            strategy.description,
            "",
            "Будет добавлено:",
        ]
    )
    for item in resolved_items:
        item_line = f"- {item.item_name}"
        details: list[str] = []
        if item.item_type:
            details.append(item.item_type)
        if item.target_price is not None:
            details.append(f">= {format_decimal(item.target_price)} {item.target_currency}")
        if details:
            item_line += f" ({', '.join(details)})"
        lines.append(item_line)
    lines.extend(
        [
            "",
            "Сначала выбери стратегию применения, потом лигу. Так один и тот же шаблон можно запускать как более ранний, аккуратный или широкий сетап.",
        ]
    )
    return "\n".join(lines)


def build_template_activation_text(result, league) -> str:
    game_label = "POE 2" if league.realm == "poe2" else "POE 1"
    lines = [
        f"Шаблон {result.template_name} подключен.",
        f"Игра: {game_label}",
        f"Лига: {league.name}",
        f"Стратегия: {result.strategy_name}",
        f"Создано watcher'ов: {result.created_count}",
        f"Обновлено или реактивировано: {result.updated_count}",
    ]

    if result.created_items:
        lines.append("")
        lines.append("Созданы:")
        lines.extend(f"- {item_name}" for item_name in result.created_items)

    if result.updated_items:
        lines.append("")
        lines.append("Обновлены или реактивированы:")
        lines.extend(f"- {item_name}" for item_name in result.updated_items)

    return "\n".join(lines)


def build_assistant_intro_text() -> str:
    return (
        "Build assistant:\n\n"
        "Помогу подобрать стартовое направление под игру, бюджет и стиль.\n"
        "Сначала выбери POE 1 или POE 2."
    )


def build_home_text() -> str:
    return (
        "POE Assistant\n\n"
        "Открой нужный раздел через меню ниже.\n\n"
        "Что уже можно делать:\n"
        "- шаблоны для быстрых сетапов\n"
        "- экономика и currency alerts\n"
        "- билды с planner / guide / tree\n"
        "- трекинг и alerts под рукой\n"
        "- аккаунт и тайник готовы к расширению после ответа GGG"
    )


def build_menu_help_text() -> str:
    return (
        "Навигация:\n\n"
        "/menu или /start — главный экран\n"
        "/add — добавить watcher вручную\n"
        "/templates — готовые сетапы\n"
        "/economy — рынок и currency alerts\n"
        "/builds — подбор билдов\n"
        "/list — активный трекинг\n"
        "/alerts — сработавшие alerts\n"
        "/account — привязка PoE-аккаунта\n"
        "/stash — stash-панель\n"
        "/stats — статистика\n"
        "/settings — текущие MVP-настройки"
    )


def build_templates_section_text() -> str:
    return (
        "Шаблоны\n\n"
        "Готовые наборы watcher'ов под игру, цель и стратегию.\n"
        "Подходят для быстрого старта без ручной сборки сетапа."
    )


def build_economy_section_text() -> str:
    return (
        "Экономика\n\n"
        "Здесь у нас рынок, currency alerts и быстрый обзор движения валют.\n"
        "Можно открыть полный dashboard или сразу перейти к сработавшим alerts."
    )


def build_builds_section_text() -> str:
    return (
        "Билды\n\n"
        "Подбор билдов по игре, цели, бюджету и стилю.\n"
        "Внутри есть planner, guide, tree, atlas и endgame-подсказки."
    )


def build_tracking_section_text() -> str:
    return (
        "Трекинг\n\n"
        "Управление активными watcher'ами и быстрый вход в мастер добавления.\n"
        "Если что-то уже сработало, отсюда же удобно перейти в alerts."
    )


def build_account_section_text() -> str:
    return (
        "Аккаунт\n\n"
        "Панель привязки PoE-аккаунта и состояние интеграции.\n"
        "Сейчас это foundation-слой, который ждёт ответ GGG для полного раскрытия."
    )


def build_stash_section_text() -> str:
    return (
        "Тайник\n\n"
        "Stash-панель и readiness под будущий реальный stash-analysis.\n"
        "До ответа GGG здесь держим основу и навигацию к связанным функциям."
    )


def build_goal_prompt_text(game: str) -> str:
    game_label = BuildService.game_label(game)
    return (
        f"Build assistant · {game_label}\n\n"
        "Какая у тебя сейчас главная цель?"
    )


def build_budget_prompt_text(game: str, goal: str) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    return (
        f"Build assistant · {game_label}\n\n"
        f"Цель: {goal_label}\n"
        "\n"
        "Теперь выбери бюджетный уровень. Это не точная валюта, а скорее стадия готовности:\n"
        "- стартовый\n"
        "- средний\n"
        "- высокий"
    )


def build_playstyle_prompt_text(game: str, goal: str, budget_tier: str) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    budget_label = BuildService.budget_label(budget_tier)
    return (
        f"Build assistant · {game_label}\n"
        f"Цель: {goal_label}\n"
        f"Бюджет: {budget_label}\n\n"
        "Какой стиль тебе ближе?"
    )


def build_recommendations_overview_text(
    *,
    game: str,
    goal: str,
    budget_tier: str,
    playstyle: str,
    recommendations: list[BuildRecommendation],
) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    budget_label = BuildService.budget_label(budget_tier)
    playstyle_label = BuildService.playstyle_label(playstyle)

    lines = [
        "Build assistant:",
        "",
        f"Игра: {game_label}",
        f"Цель: {goal_label}",
        f"Бюджет: {budget_label}",
        f"Стиль: {playstyle_label}",
    ]

    if not recommendations:
        lines.extend(
            [
                "",
                "Пока не нашёл подходящий билд под такой фильтр.",
                "Попробуй соседний стиль или другой уровень бюджета.",
            ]
        )
        return "\n".join(lines)

    best_match = recommendations[0]
    safest_option = next(
        (recommendation for recommendation in recommendations if recommendation.archetype in {"tank", "safe"}),
        recommendations[0],
    )
    fastest_option = next(
        (recommendation for recommendation in recommendations if recommendation.archetype in {"mapper"} or "speed" in recommendation.playstyles),
        recommendations[0],
    )

    lines.extend(
        [
            "",
            "Короткий verdict:",
            f"- Лучший матч под задачу: {best_match.title}",
            f"- Самый безопасный вариант: {safest_option.title}",
            f"- Самый быстрый вариант: {fastest_option.title}",
        ]
    )

    lines.extend(["", "Подходящие варианты:"])
    for index, recommendation in enumerate(recommendations, start=1):
        lines.extend(
            [
                "",
                f"{index}. {recommendation.title}",
                f"Класс: {recommendation.class_name}",
                f"Ядро: {recommendation.core_skill}",
                recommendation.summary,
                f"Бюджет: {recommendation.budget_estimate}",
                f"Эндгейм-фокус: {', '.join(recommendation.endgame_goals)}",
            ]
        )

    lines.extend(
        [
            "",
            "Нажми на билд ниже, и я открою подробный разбор со слотами, trade-targets и кнопками на planner / guide / tree / atlas.",
        ]
    )

    return "\n".join(lines)


def build_recommendation_detail_text(
    *,
    game: str,
    goal: str,
    budget_tier: str,
    playstyle: str,
    recommendation: BuildRecommendation,
) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    budget_label = BuildService.budget_label(budget_tier)
    playstyle_label = BuildService.playstyle_label(playstyle)

    lines = [
        "Build assistant:",
        "",
        f"Игра: {game_label}",
        f"Цель: {goal_label}",
        f"Бюджет: {budget_label}",
        f"Стиль: {playstyle_label}",
        "",
        recommendation.title,
        f"Класс: {recommendation.class_name}",
        f"Ядро: {recommendation.core_skill}",
        recommendation.summary,
        *(["Источник/референсы: " + recommendation.source_note] if recommendation.source_note else []),
        f"Примерный бюджет: {recommendation.budget_estimate}",
        f"Покупать в первую очередь: {', '.join(recommendation.buy_priority)}",
        f"Какие статы добирать: {', '.join(recommendation.stat_targets)}",
        f"Первые апгрейды: {', '.join(recommendation.first_upgrades)}",
        f"Дерево / приоритеты прокачки: {', '.join(recommendation.tree_focus)}",
        f"Атлас / направление фарма: {', '.join(recommendation.atlas_focus)}",
        f"Что этим билдом фармить: {', '.join(recommendation.farm_mechanics)}",
        "Эндгейм-чеклист по слотам:",
        *[f"  - {entry}" for entry in recommendation.endgame_slot_checklist],
        f"Эндгейм-цели: {', '.join(recommendation.endgame_goals)}",
        f"Chase-апгрейды: {', '.join(recommendation.chase_upgrades)}",
        f"Если хочется похожее, но по-другому: {recommendation.alternative_hint}",
    ]

    if recommendation.gear_sheet:
        lines.append("Gear sheet по слотам:")
        lines.extend(f"  - {entry}" for entry in recommendation.gear_sheet)

    if recommendation.gear_progression:
        lines.append("Как собирать по стадиям:")
        lines.extend(f"  - {entry}" for entry in recommendation.gear_progression)

    if recommendation.market_targets:
        lines.append("Что искать на трейде:")
        lines.extend(f"  - {entry}" for entry in recommendation.market_targets)
    else:
        lines.append(f"На каких слотах и архетипе шмоток фокус: {', '.join(recommendation.gear_focus)}")

    if recommendation.avoid_warnings:
        lines.append("Чего избегать:")
        lines.extend(f"  - {entry}" for entry in recommendation.avoid_warnings)
    else:
        lines.append(f"Осторожно: {', '.join(recommendation.cautions)}")

    if recommendation.planner_url or recommendation.guide_url or recommendation.tree_url or recommendation.atlas_url:
        lines.append("Визуальные ресурсы доступны кнопками ниже.")

    return "\n".join(lines)


def build_economy_text(summaries: list, overview) -> str:
    lines = [
        "Экономика",
        "",
        f"Активные currency alerts: {overview.total_active_currency_alerts}",
        f"На паузе: {overview.total_paused_currency_alerts}",
    ]

    if overview.market_hints:
        lines.extend(["", "Что делать сейчас:"])
        for hint in overview.market_hints:
            lines.append(f"- {hint.title}: {hint.detail}")

    if overview.market_pulse:
        lines.extend(["", "Market pulse:"])
        if overview.market_pulse.hottest_movement:
            movement = overview.market_pulse.hottest_movement
            game_label = "POE 2" if movement.game == "poe2" else "POE 1"
            currency_label = "Divine Orb" if movement.currency_code == "div" else "Exalted Orb"
            direction = "растёт" if movement.delta_value > 0 else "снижается"
            delta_percent = movement.delta_ratio.copy_abs() * Decimal("100")
            lines.append(
                f"- Самое сильное движение: {currency_label} [{game_label} / {movement.league_name}] "
                f"{direction} на {format_decimal(delta_percent)}%"
            )
        if overview.market_pulse.hottest_alert:
            alert = overview.market_pulse.hottest_alert
            game_label = "POE 2" if alert.game == "poe2" else "POE 1"
            progress_percent = min(alert.progress_ratio * Decimal("100"), Decimal("999"))
            lines.append(
                f"- Самый горячий alert: #{alert.tracked_item_id} {alert.item_name} "
                f"[{game_label} / {alert.league_name}] — {format_decimal(progress_percent)}% до срабатывания"
            )
        if overview.market_pulse.total_moving_markets:
            lines.append(f"- Двигающихся market-срезов: {overview.market_pulse.total_moving_markets}")

    if overview.top_watched_currencies:
        lines.extend(["", "Топ отслеживаемых валют:"])
        for entry in overview.top_watched_currencies:
            line = f"- {entry.item_name}: {entry.total_watchers}"
            details = []
            if entry.active_watchers:
                details.append(f"активных {entry.active_watchers}")
            if entry.paused_watchers:
                details.append(f"на паузе {entry.paused_watchers}")
            if details:
                line += f" ({', '.join(details)})"
            lines.append(line)

    if overview.nearest_alerts:
        lines.extend(["", "Ближе всего к срабатыванию:"])
        for alert in overview.nearest_alerts:
            game_label = "POE 2" if alert.game == "poe2" else "POE 1"
            progress_percent = min(alert.progress_ratio * Decimal("100"), Decimal("999"))
            lines.append(
                f"- #{alert.tracked_item_id} {alert.item_name} "
                f"[{game_label} / {alert.league_name}] "
                f"{format_decimal(alert.current_value)} / {format_decimal(alert.target_price)} {alert.target_currency} "
                f"({format_decimal(progress_percent)}%)"
            )

    if overview.market_movements:
        lines.extend(["", "Движение рынка:"])
        for movement in overview.market_movements:
            game_label = "POE 2" if movement.game == "poe2" else "POE 1"
            currency_label = "Divine Orb" if movement.currency_code == "div" else "Exalted Orb"
            direction = "рост" if movement.delta_value > 0 else "снижение"
            delta_percent = movement.delta_ratio.copy_abs() * Decimal("100")
            lines.append(
                f"- {currency_label} [{game_label} / {movement.league_name}] "
                f"{direction}: {format_decimal(movement.previous_value)} -> {format_decimal(movement.current_value)} chaos "
                f"({format_decimal(delta_percent)}%)"
            )

    for summary in summaries:
        game_label = "POE 2" if summary.game == "poe2" else "POE 1"
        lines.extend(["", f"{game_label} / {summary.league_name}"])

        snapshot = summary.exchange_snapshot
        if snapshot:
            rates = snapshot.rates
            lines.append(f"Источник: {snapshot.source}")
            if "div" in rates:
                lines.append(f"1 div ~= {format_decimal(rates['div'])} chaos")
            if "ex" in rates:
                lines.append(f"1 ex ~= {format_decimal(rates['ex'])} chaos")
            if "div" in rates and "ex" in rates and rates["ex"] != 0:
                lines.append(f"1 div ~= {format_decimal(rates['div'] / rates['ex'])} ex")
        else:
            lines.append("Курсы сейчас недоступны.")

        if not snapshot and summary.game == "poe1" and summary.league_name.lower() != "standard":
            lines.append("Для этой POE1-лиги отдельный источник курсов пока не ответил.")
            lines.append("Я также попробовал fallback на Standard, но внешние данные не пришли.")

        if summary.active_watchers:
            lines.append(f"Активные alerts: {len(summary.active_watchers)}")
            for watcher in summary.active_watchers[:5]:
                lines.append(
                    f"- #{watcher.tracked_item_id} {watcher.item_name} >= "
                    f"{format_decimal(watcher.target_price)} {watcher.target_currency}"
                )
            if len(summary.active_watchers) > 5:
                lines.append(f"- ... еще {len(summary.active_watchers) - 5}")
        else:
            lines.append("Активных alerts пока нет.")

        if summary.paused_watchers:
            lines.append(f"На паузе: {len(summary.paused_watchers)}")
            for watcher in summary.paused_watchers[:3]:
                lines.append(
                    f"- #{watcher.tracked_item_id} {watcher.item_name} "
                    f"({format_decimal(watcher.target_price)} {watcher.target_currency})"
                )
            if len(summary.paused_watchers) > 3:
                lines.append(f"- ... еще {len(summary.paused_watchers) - 3}")
            lines.append("Открой /alerts, чтобы быстро перезапустить их.")

    lines.extend(
        [
            "",
            "Подсказка: currency alert срабатывает, когда рыночная цена достигает или превышает твой порог.",
        ]
    )
    return "\n".join(lines)


def infer_trade_context(trade_url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(trade_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) >= 4 and segments[0] == "trade" and segments[1] == "search":
        return "poe1", segments[2]
    if len(segments) >= 5 and segments[0] == "trade2" and segments[1] == "search":
        realm = segments[2]
        league_name = segments[3]
        return ("poe2" if realm == "poe2" else realm, league_name)
    return None, None


def normalize_threshold_currency(raw_value: str) -> str:
    mapping = {
        "ex": "ex",
        "exa": "ex",
        "exalted": "ex",
        "chaos": "chaos",
        "c": "chaos",
        "div": "div",
        "divine": "div",
    }
    normalized = raw_value.strip().lower()
    if normalized not in mapping:
        raise InvalidOperation
    return mapping[normalized]


def parse_threshold_input(raw_value: str) -> tuple[Decimal, str]:
    normalized = raw_value.strip().lower().replace(",", ".")
    parts = normalized.split()
    if not parts:
        raise InvalidOperation

    amount = Decimal(parts[0])
    currency = "ex" if len(parts) == 1 else normalize_threshold_currency(parts[1])
    return amount, currency


async def delete_if_possible(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def show_wizard_message(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
) -> None:
    data = await state.get_data()
    wizard_message_id = data.get("wizard_message_id")
    if wizard_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=wizard_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    await state.update_data(wizard_message_id=sent.message_id, wizard_chat_id=chat_id)


async def finish_wizard(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup=None,
) -> None:
    await show_wizard_message(state=state, bot=bot, chat_id=chat_id, text=text, reply_markup=reply_markup)
    await state.clear()


async def load_account_panel(telegram_id: int, username: str | None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        integration = await IntegrationService(session).get_by_type(user, IntegrationType.poe_oauth)

    oauth_service = PoeOAuthService()
    connect_url: str | None = None
    oauth_config_error: str | None = None
    try:
        connect_url = oauth_service.build_connect_url(telegram_id=telegram_id)
    except PoeOAuthConfigError as exc:
        oauth_config_error = str(exc)

    text = build_account_text(integration=integration, oauth_config_error=oauth_config_error)
    keyboard = account_keyboard(connect_url=connect_url, is_connected=integration is not None)
    return text, keyboard


async def load_stash_panel(telegram_id: int, username: str | None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        summary = await StashService(session).get_panel_summary(user)

    connect_url = None
    if summary.oauth_available and not summary.account_connected:
        oauth_service = PoeOAuthService()
        try:
            connect_url = oauth_service.build_connect_url(telegram_id=telegram_id)
        except PoeOAuthConfigError:
            connect_url = None

    return build_stash_text(summary), stash_keyboard(connect_url=connect_url, account_connected=summary.account_connected)


async def load_tracking_panel(telegram_id: int, username: str | None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        items = await TrackingService(session).list_items(user)

    if not items:
        return "Активного трекинга пока нет. Добавь предмет через /add.", menu_section_keyboard(("Добавить трекинг", "menu:add"))
    return build_tracking_list_text(items), with_home_button(tracking_actions_keyboard(items))


async def load_alerts_panel(telegram_id: int, username: str | None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        items = await TrackingService(session).list_paused_price_alerts(user)

    if not items:
        return (
            "Сработавших price alerts пока нет.\n\n"
            "Когда alert сработает, он появится здесь, и его можно будет быстро перезапустить.",
            menu_section_keyboard(("Открыть экономику", "menu:economy")),
        )
    return build_paused_alerts_text(items), with_home_button(paused_alerts_keyboard(items))


async def load_economy_panel(telegram_id: int, username: str | None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        summaries, overview = await EconomyService(session).get_user_economy_dashboard(user)

    return build_economy_text(summaries, overview), menu_section_keyboard(
        ("Обновить экономику", "menu:economy"),
        ("Открыть alerts", "menu:alerts"),
    )


async def answer_home_screen(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)
    await message.answer(build_home_text(), reply_markup=home_menu_keyboard())


async def edit_home_screen(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(build_home_text(), reply_markup=home_menu_keyboard())
    await callback.answer()


async def begin_add_wizard(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddTrackingStates.choosing_mode)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "Новый трекинг\n\n"
            "Шаг 1/4: выбери тип источника."
        ),
        reply_markup=add_entry_keyboard(),
    )


async def render_duplicate_resolution(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    items: list,
) -> None:
    lines = [
        "Нашёл похожие watcher'ы.",
        "Можно обновить один из них или создать новый отдельно.",
        "",
    ]
    for item in items:
        threshold = (
            f"{format_decimal(Decimal(item.target_price))} {item.target_currency}"
            if item.target_price is not None
            else "без порога"
        )
        lines.append(f"#{item.id} - {item.item_name} ({threshold})")

    await show_wizard_message(
        state=state,
        bot=bot,
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=duplicate_resolution_keyboard(items),
    )


async def finalize_tracking_creation(
    *,
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    user_telegram_id: int,
    username: str | None,
    create_new: bool,
    existing_item_id: int | None = None,
) -> None:
    data = await state.get_data()
    async with session_scope() as session:
        user = await ensure_user(session, user_telegram_id, username)
        result = await TrackingService(session).add_item(
            user=user,
            item_name=data["item_name"],
            item_type=data.get("item_type", "item"),
            trade_url=data.get("trade_url"),
            target_price=Decimal(data["target_price"]) if data.get("target_price") is not None else None,
            target_currency=data.get("target_currency", "ex"),
            league_name=data.get("league_name"),
            game=data.get("game"),
            existing_item_id=existing_item_id,
            create_new=create_new,
        )

    item = result.item
    action_text = "Обновил" if result.action == "updated" else "Добавил"
    response_lines = [f"{action_text} трекинг #{item.id}: {item.item_name}"]
    if item.target_price is not None:
        response_lines.append(f"Порог: {format_decimal(Decimal(item.target_price))} {item.target_currency}")
    if item.trade_url:
        response_lines.append("Источник: trade URL")

    await finish_wizard(
        state=state,
        bot=bot,
        chat_id=chat_id,
        text="\n".join(response_lines),
        reply_markup=tracking_actions_keyboard([item]),
    )


@router.message(Command("start"))
async def start(message: Message) -> None:
    await answer_home_screen(message)


@router.message(Command("menu"))
async def menu(message: Message) -> None:
    await answer_home_screen(message)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(build_menu_help_text(), reply_markup=menu_section_keyboard(("Открыть меню", "menu:home")))


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery) -> None:
    await edit_home_screen(callback)


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_menu_help_text(),
            reply_markup=menu_section_keyboard(("Домой", "menu:home"), include_home=False),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:templates")
async def menu_templates(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_templates_section_text(),
            reply_markup=menu_section_keyboard(
                ("Открыть шаблоны", "menu:templates:open"),
                ("Добавить трекинг вручную", "menu:add"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:economy")
async def menu_economy(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_economy_section_text(),
            reply_markup=menu_section_keyboard(
                ("Открыть обзор экономики", "menu:economy:open"),
                ("Сработавшие alerts", "menu:alerts:open"),
                ("Шаблоны рынка", "menu:templates:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:builds")
async def menu_builds(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_builds_section_text(),
            reply_markup=menu_section_keyboard(
                ("Подобрать билд", "menu:builds:open"),
                ("Открыть шаблоны", "menu:templates:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:tracking")
async def menu_tracking(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_tracking_section_text(),
            reply_markup=menu_section_keyboard(
                ("Активный трекинг", "menu:tracking:open"),
                ("Добавить watcher", "menu:add"),
                ("Сработавшие alerts", "menu:alerts:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:alerts")
async def menu_alerts(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            "Алерты\n\nСработавшие currency alerts, которые стоят на паузе и ждут перезапуска.",
            reply_markup=menu_section_keyboard(
                ("Открыть alerts", "menu:alerts:open"),
                ("Открыть экономику", "menu:economy:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:account")
async def menu_account(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_account_section_text(),
            reply_markup=menu_section_keyboard(
                ("Открыть панель аккаунта", "menu:account:open"),
                ("Открыть тайник", "menu:stash:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:stash")
async def menu_stash(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_stash_section_text(),
            reply_markup=menu_section_keyboard(
                ("Открыть stash-панель", "menu:stash:open"),
                ("Открыть аккаунт", "menu:account:open"),
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:templates:open")
async def menu_templates_open(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            "Шаблоны:\nСначала выбери игру, и я покажу только релевантные наборы.",
            reply_markup=with_home_button(template_browser_game_keyboard()),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:economy:open")
async def menu_economy_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_economy_panel(callback.from_user.id, callback.from_user.username)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer("Экономика обновлена")


@router.callback_query(F.data == "menu:builds:open")
async def menu_builds_open(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(
            build_assistant_intro_text(),
            reply_markup=with_home_button(build_game_keyboard()),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:tracking:open")
async def menu_tracking_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_tracking_panel(callback.from_user.id, callback.from_user.username)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:alerts:open")
async def menu_alerts_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_alerts_panel(callback.from_user.id, callback.from_user.username)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:account:open")
async def menu_account_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))
    await callback.answer()


@router.callback_query(F.data == "menu:stash:open")
async def menu_stash_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))
    await callback.answer()


@router.callback_query(F.data == "menu:add")
async def menu_add(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await begin_add_wizard(callback.message, state)
    await callback.answer()


@router.message(Command("account"))
async def account(message: Message) -> None:
    text, keyboard = await load_account_panel(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=with_home_button(keyboard))


@router.message(Command("stash"))
async def stash(message: Message) -> None:
    text, keyboard = await load_stash_panel(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=with_home_button(keyboard))


@router.message(Command("builds"))
async def builds(message: Message) -> None:
    await message.answer(build_assistant_intro_text(), reply_markup=with_home_button(build_game_keyboard()))


@router.message(Command("add"))
async def add_tracking(message: Message, state: FSMContext) -> None:
    raw_text = message.text or ""
    payload = raw_text.removeprefix("/add").strip()
    if not payload:
        await begin_add_wizard(message, state)
        return

    trade_url = payload if payload.startswith("http") else None
    item_name = "Trade URL" if trade_url else payload
    target_price: Decimal | None = None
    target_currency = "ex"

    if trade_url:
        game, league_name = infer_trade_context(trade_url)
        await state.clear()
        await state.update_data(
            item_type="item",
            trade_url=trade_url,
            target_price=None,
            target_currency="ex",
            game=game,
            league_name=league_name,
        )
        await state.set_state(AddTrackingStates.entering_trade_name)
        await show_wizard_message(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            text=(
                "Trade URL получен.\n\n"
                "Шаг 2/3: пришли короткое название трекера.\n"
                "Например: Mageblood, TS Bow, Mirror Ring."
            ),
        )
        return

    if "|" in payload and not trade_url:
        name_part, price_part = [part.strip() for part in payload.split("|", 1)]
        item_name = name_part
        try:
            target_price, target_currency = parse_threshold_input(price_part)
        except InvalidOperation:
            await message.answer(
                "Не понял порог.\n\nПримеры:\n"
                "/add Divine Orb | 1\n"
                "/add Divine Orb | 150 chaos\n"
                "/add Divine Orb | 0.5 div"
            )
            return
    elif not trade_url:
        await message.answer(
            "Для команды в одну строку нужен порог.\n\n"
            "Примеры:\n"
            "/add Divine Orb | 1\n"
            "/add Divine Orb | 150 chaos\n"
            "/add Divine Orb | 0.5 div\n\n"
            "Если удобнее, используй просто /add."
        )
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        result = await TrackingService(session).add_item(
            user=user,
            item_name=item_name,
            trade_url=trade_url,
            target_price=target_price,
            target_currency=target_currency,
        )

    response_lines = [f"{'Обновил' if result.action == 'updated' else 'Добавил'} трекинг #{result.item.id}: {result.item.item_name}"]
    if target_price is not None:
        response_lines.append(f"Порог: {format_decimal(target_price)} {target_currency}")
    if trade_url:
        response_lines.append("Источник: trade URL")
    await message.answer("\n".join(response_lines), reply_markup=tracking_actions_keyboard([result.item]))


@router.callback_query(F.data == "add:mode:item")
async def add_mode_item(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTrackingStates.choosing_game)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Новый трекинг\n\nШаг 2/4: выбери игру.",
        reply_markup=game_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "add:mode:trade_url")
async def add_mode_trade_url(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(item_type="item", trade_url=None)
    await state.set_state(AddTrackingStates.entering_trade_url)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Новый трекинг\n\nШаг 2/4: пришли trade URL отдельным сообщением.",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:game:"))
async def add_choose_game(callback: CallbackQuery, state: FSMContext) -> None:
    game = callback.data.rsplit(":", 1)[1]
    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)

    await state.update_data(game=game)
    await state.set_state(AddTrackingStates.choosing_league)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            "Новый трекинг\n\n"
            "Шаг 3/4: выбери лигу.\n"
            "Актуальные лиги показываю выше стандартных."
        ),
        reply_markup=league_keyboard(leagues),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:league:"))
async def add_choose_league(callback: CallbackQuery, state: FSMContext) -> None:
    league_id = int(callback.data.rsplit(":", 1)[1])
    async with session_scope() as session:
        league = await session.get(League, league_id)

    if not league:
        await callback.answer("Не нашел эту лигу", show_alert=True)
        return

    await state.update_data(league_id=league.id, league_name=league.name, game=league.realm)
    await state.set_state(AddTrackingStates.entering_search)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Лига: {league.name}\n\n"
            "Шаг 4/4: выбери частую валюту кнопкой ниже\n"
            "или пришли часть названия предмета / валюты."
        ),
        reply_markup=currency_presets_keyboard(),
    )
    await callback.answer()


@router.message(AddTrackingStates.entering_search)
async def add_search_query(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    if not query:
        return

    async with session_scope() as session:
        results = await ItemCatalogService(session).search(query=query)

    await state.update_data(search_query=query, search_results=results)
    await state.set_state(AddTrackingStates.entering_search)
    await delete_if_possible(message)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=f"Варианты для: {query}\n\nВыбери готовый вариант или используй свой текст как есть.",
        reply_markup=search_results_keyboard(results, query),
    )


@router.callback_query(F.data.startswith("add:preset_currency:"))
async def add_choose_currency_preset(callback: CallbackQuery, state: FSMContext) -> None:
    preset_key = callback.data.rsplit(":", 1)[1]
    preset_map = {
        "divine_orb": "Divine Orb",
        "exalted_orb": "Exalted Orb",
        "chaos_orb": "Chaos Orb",
    }
    item_name = preset_map.get(preset_key)
    if not item_name:
        await callback.answer("Не нашел такой пресет", show_alert=True)
        return

    await state.update_data(item_name=item_name, item_type="currency", trade_url=None)
    await state.set_state(AddTrackingStates.choosing_currency)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Выбран пресет: {item_name}\n\n"
            "Теперь выбери валюту порога."
        ),
        reply_markup=threshold_currency_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:item:"))
async def add_choose_item(callback: CallbackQuery, state: FSMContext) -> None:
    token = callback.data.rsplit(":", 1)[1]
    data = await state.get_data()
    if token == "exact":
        item_name = data.get("search_query", "")
    else:
        results = data.get("search_results", [])
        index = int(token)
        if index >= len(results):
            await callback.answer("Этот вариант уже устарел, попробуй поиск еще раз", show_alert=True)
            return
        item_name = results[index]

    await state.update_data(item_name=item_name, item_type="item", trade_url=None)
    await state.set_state(AddTrackingStates.choosing_currency)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Предмет: {item_name}\n\n"
            "Теперь выбери валюту порога."
        ),
        reply_markup=threshold_currency_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:currency:"))
async def add_choose_threshold_currency(callback: CallbackQuery, state: FSMContext) -> None:
    target_currency = callback.data.rsplit(":", 1)[1]
    await state.update_data(target_currency=target_currency)
    await state.set_state(AddTrackingStates.entering_threshold)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=(
            f"Валюта порога: {target_currency}\n\n"
            "Теперь пришли только число.\n"
            "Например: 1, 150 или 0.5"
        ),
    )
    await callback.answer()


@router.message(AddTrackingStates.entering_threshold)
async def add_enter_threshold(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation:
        await message.answer("Не получилось разобрать число.\nПримеры: 1, 150, 0.5")
        return

    await delete_if_possible(message)
    await state.update_data(target_price=str(amount))
    data = await state.get_data()

    league_id = data.get("league_id")
    if not league_id:
        await finalize_tracking_creation(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            user_telegram_id=message.from_user.id,
            username=message.from_user.username,
            create_new=False,
        )
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        similar_items = await TrackingService(session).find_similar_items(
            user=user,
            league_id=league_id,
            item_name=data["item_name"],
            trade_url=data.get("trade_url"),
        )

    if similar_items:
        await state.set_state(AddTrackingStates.resolving_duplicate)
        await render_duplicate_resolution(
            state=state,
            bot=message.bot,
            chat_id=message.chat.id,
            items=similar_items,
        )
        return

    await finalize_tracking_creation(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        user_telegram_id=message.from_user.id,
        username=message.from_user.username,
        create_new=False,
    )


@router.message(AddTrackingStates.entering_trade_url)
async def add_enter_trade_url(message: Message, state: FSMContext) -> None:
    trade_url = (message.text or "").strip()
    if not trade_url.startswith("http"):
        await message.answer("Жду полноценный URL, который начинается с http или https.")
        return

    await delete_if_possible(message)
    game, league_name = infer_trade_context(trade_url)
    await state.update_data(
        trade_url=trade_url,
        item_type="item",
        target_price=None,
        target_currency="ex",
        game=game,
        league_name=league_name,
    )
    await state.set_state(AddTrackingStates.entering_trade_name)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            "Trade URL принят.\n\n"
            "Шаг 3/4: пришли название трекера.\n"
            "Например: Mageblood."
        ),
    )


@router.message(AddTrackingStates.entering_trade_name)
async def add_enter_trade_name(message: Message, state: FSMContext) -> None:
    item_name = (message.text or "").strip()
    if not item_name:
        await message.answer("Нужно название трекера.\nНапример: Mageblood")
        return

    await delete_if_possible(message)
    await state.update_data(item_name=item_name, item_type="item")
    await state.set_state(AddTrackingStates.choosing_currency)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=(
            f"Название: {item_name}\n\n"
            "Теперь выбери валюту порога."
        ),
        reply_markup=threshold_currency_keyboard(),
    )


@router.callback_query(F.data.startswith("add:resolve:update:"))
async def add_resolve_update(callback: CallbackQuery, state: FSMContext) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])
    await finalize_tracking_creation(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        create_new=False,
        existing_item_id=tracked_item_id,
    )
    await callback.answer("Watcher обновлен")


@router.callback_query(F.data == "add:resolve:create")
async def add_resolve_create(callback: CallbackQuery, state: FSMContext) -> None:
    await finalize_tracking_creation(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        user_telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        create_new=True,
    )
    await callback.answer("Создал отдельный watcher")


@router.callback_query(F.data == "add:cancel")
async def add_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await finish_wizard(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Ок, отменил создание трекинга.",
    )
    await callback.answer("Отменено")


@router.callback_query(F.data == "add:back:game")
async def add_back_to_game(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTrackingStates.choosing_game)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Новый трекинг\n\nШаг 2/4: выбери игру.",
        reply_markup=game_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "add:back:league")
async def add_back_to_league(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    game = data.get("game", "poe2")
    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)

    await state.set_state(AddTrackingStates.choosing_league)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text="Снова выбери лигу.",
        reply_markup=league_keyboard(leagues),
    )
    await callback.answer()


@router.callback_query(F.data == "add:back:item")
async def add_back_to_item(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    query = data.get("search_query", "")
    results = data.get("search_results", [])
    await state.set_state(AddTrackingStates.entering_search)
    await show_wizard_message(
        state=state,
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        text=f"Снова выбери вариант для: {query}",
        reply_markup=search_results_keyboard(results, query),
    )
    await callback.answer()


@router.message(Command("remove"))
async def remove_tracking(message: Message) -> None:
    payload = (message.text or "").removeprefix("/remove").strip()
    if not payload.isdigit():
        await message.answer("Укажи id трекинга. Пример: /remove 12")
        return

    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=int(payload))

    await message.answer("Трекинг отключен." if removed else "Не нашел такой активный трекинг.")


@router.callback_query(F.data.startswith("list:remove:"))
async def remove_tracking_from_list(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_items(user)

    if removed:
        await callback.answer("Трекинг уже отключен или не найден", show_alert=True)
        return

    await callback.answer("Трекинг отключен")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=tracking_actions_keyboard(items),
    )


@router.callback_query(F.data.startswith("list2:remove:"))
async def remove_tracking_from_list_v2(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_items(user)

    if not removed:
        await callback.answer("Трекинг уже отключен или не найден", show_alert=True)
        return

    await callback.answer("Трекинг отключен")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Активного трекинга пока нет. Добавь предмет через /add.")
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=tracking_actions_keyboard(items),
    )


@router.callback_query(F.data.startswith("list2:reactivate:"))
async def reactivate_tracking_from_list_v2(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        reactivated = await TrackingService(session).reactivate_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_items(user)

    if not reactivated:
        await callback.answer("Трекер уже активен, отключён или не найден", show_alert=True)
        return

    await callback.answer("Трекер снова активен")
    if not callback.message:
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=tracking_actions_keyboard(items),
    )


@router.callback_query(F.data.startswith("tracking:remove:"))
async def remove_tracking_callback(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)

    if not removed:
        await callback.answer("Трекер уже отключён или не найден", show_alert=True)
        return

    await callback.answer("Трекер отключён")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("tracking:reactivate:"))
async def reactivate_tracking_callback(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        reactivated = await TrackingService(session).reactivate_item(user=user, tracked_item_id=tracked_item_id)

    if not reactivated:
        await callback.answer("Трекер уже активен, отключён или не найден", show_alert=True)
        return

    await callback.answer("Трекер снова активен")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.message(Command("list"))
async def list_tracking(message: Message) -> None:
    text, keyboard = await load_tracking_panel(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("alerts"))
async def paused_alerts(message: Message) -> None:
    text, keyboard = await load_alerts_panel(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "alerts:reactivate_all")
async def reactivate_all_paused_alerts(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        reactivated_count = await TrackingService(session).reactivate_all_paused_price_alerts(user)
        items = await TrackingService(session).list_paused_price_alerts(user)

    if reactivated_count == 0:
        await callback.answer("Сработавших alerts для перезапуска нет", show_alert=True)
        return

    await callback.answer(f"Перезапустил alerts: {reactivated_count}")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Сработавших price alerts пока нет. Всё снова активно.")
        return

    await callback.message.edit_text(build_paused_alerts_text(items), reply_markup=paused_alerts_keyboard(items))


@router.callback_query(F.data.startswith("alerts:reactivate_game:"))
async def reactivate_paused_alerts_for_game(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    game_label = "POE 2" if game == "poe2" else "POE 1"

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        reactivated_count = await TrackingService(session).reactivate_paused_price_alerts_for_game(user, game)
        items = await TrackingService(session).list_paused_price_alerts(user)

    if reactivated_count == 0:
        await callback.answer(f"Сработавших alerts для {game_label} сейчас нет", show_alert=True)
        return

    await callback.answer(f"Перезапустил alerts для {game_label}: {reactivated_count}")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Сработавших price alerts пока нет. Всё снова активно.")
        return

    await callback.message.edit_text(build_paused_alerts_text(items), reply_markup=paused_alerts_keyboard(items))


@router.callback_query(F.data.startswith("alerts:reactivate:"))
async def reactivate_paused_alert_from_panel(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        reactivated = await TrackingService(session).reactivate_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_paused_price_alerts(user)

    if not reactivated:
        await callback.answer("Этот alert уже активен, отключён или не найден", show_alert=True)
        return

    await callback.answer("Alert снова активен")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Сработавших price alerts пока нет. Всё снова активно.")
        return

    await callback.message.edit_text(build_paused_alerts_text(items), reply_markup=paused_alerts_keyboard(items))


@router.callback_query(F.data.startswith("alerts:remove:"))
async def remove_paused_alert_from_panel(callback: CallbackQuery) -> None:
    tracked_item_id = int(callback.data.rsplit(":", 1)[1])

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        removed = await TrackingService(session).remove_item(user=user, tracked_item_id=tracked_item_id)
        items = await TrackingService(session).list_paused_price_alerts(user)

    if not removed:
        await callback.answer("Этот alert уже отключён или не найден", show_alert=True)
        return

    await callback.answer("Alert отключён")
    if not callback.message:
        return

    if not items:
        await callback.message.edit_text("Сработавших price alerts пока нет.")
        return

    await callback.message.edit_text(build_paused_alerts_text(items), reply_markup=paused_alerts_keyboard(items))


@router.callback_query(F.data == "account:refresh")
async def refresh_account_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username)
    await callback.answer("Статус обновлён")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))


@router.callback_query(F.data == "account:disconnect")
async def disconnect_account(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        disconnected = await IntegrationService(session).disconnect(user, IntegrationType.poe_oauth)

    if not disconnected:
        await callback.answer("PoE аккаунт уже не подключён", show_alert=True)
        return

    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username)
    await callback.answer("PoE аккаунт отключён")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))


@router.callback_query(F.data == "stash:refresh")
async def refresh_stash_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username)
    await callback.answer("Stash-панель обновлена")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))


@router.callback_query(F.data == "stash:back:panel")
async def stash_back_to_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))


@router.callback_query(F.data.startswith("stash:guide:"))
async def stash_open_guide(callback: CallbackQuery) -> None:
    slug = callback.data.rsplit(":", 1)[1]
    guide = StashService.get_guide(slug)
    if guide is None:
        await callback.answer("Этот stash-playbook не найден", show_alert=True)
        return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(build_stash_guide_text(guide), reply_markup=stash_guide_keyboard())


@router.callback_query(F.data == "stash:account")
async def stash_open_account_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username)
    await callback.answer("Открываю панель аккаунта")
    if callback.message:
        await callback.message.edit_text(text, reply_markup=with_home_button(keyboard))


@router.callback_query(F.data == "builds:back:game")
async def builds_back_to_game(callback: CallbackQuery) -> None:
    if callback.message:
        await callback.message.edit_text(build_assistant_intro_text(), reply_markup=with_home_button(build_game_keyboard()))
    await callback.answer()


@router.callback_query(F.data.startswith("builds:game:"))
async def builds_choose_goal(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    if callback.message:
        await callback.message.edit_text(build_goal_prompt_text(game), reply_markup=build_goal_keyboard(game))
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:goal:"))
async def builds_back_to_goal(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    if callback.message:
        await callback.message.edit_text(build_goal_prompt_text(game), reply_markup=build_goal_keyboard(game))
    await callback.answer()


@router.callback_query(F.data.startswith("builds:goal:"))
async def builds_choose_budget(callback: CallbackQuery) -> None:
    _, _, game, goal = callback.data.split(":")
    if callback.message:
        await callback.message.edit_text(
            build_budget_prompt_text(game, goal),
            reply_markup=build_budget_keyboard(game, goal),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:budget:"))
async def builds_back_to_budget(callback: CallbackQuery) -> None:
    _, _, _, game, goal = callback.data.split(":")
    if callback.message:
        await callback.message.edit_text(
            build_budget_prompt_text(game, goal),
            reply_markup=build_budget_keyboard(game, goal),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:budget:"))
async def builds_choose_playstyle(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier = callback.data.split(":")
    if callback.message:
        await callback.message.edit_text(
            build_playstyle_prompt_text(game, goal, budget_tier),
            reply_markup=build_playstyle_keyboard(game, goal, budget_tier),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:playstyle:"))
async def builds_back_to_playstyle(callback: CallbackQuery) -> None:
    _, _, _, game, goal, budget_tier = callback.data.split(":")
    if callback.message:
        await callback.message.edit_text(
            build_playstyle_prompt_text(game, goal, budget_tier),
            reply_markup=build_playstyle_keyboard(game, goal, budget_tier),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:list:"))
async def builds_back_to_list(callback: CallbackQuery) -> None:
    _, _, _, game, goal, budget_tier, playstyle = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    if callback.message:
        await callback.message.edit_text(
            build_recommendations_overview_text(
                game=game,
                goal=goal,
                budget_tier=budget_tier,
                playstyle=playstyle,
                recommendations=recommendations,
            ),
            reply_markup=build_recommendation_list_keyboard(
                game,
                goal,
                budget_tier,
                playstyle,
                recommendations,
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:playstyle:"))
async def builds_show_recommendations(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier, playstyle = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    if callback.message:
        await callback.message.edit_text(
            build_recommendations_overview_text(
                game=game,
                goal=goal,
                budget_tier=budget_tier,
                playstyle=playstyle,
                recommendations=recommendations,
            ),
            reply_markup=build_recommendation_list_keyboard(
                game,
                goal,
                budget_tier,
                playstyle,
                recommendations,
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:detail:"))
async def builds_show_detail(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier, playstyle, index_str = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    try:
        recommendation = recommendations[int(index_str)]
    except (IndexError, ValueError):
        await callback.answer("Билд не найден, попробуй выбрать заново.", show_alert=True)
        return

    if callback.message:
        await callback.message.edit_text(
            build_recommendation_detail_text(
                game=game,
                goal=goal,
                budget_tier=budget_tier,
                playstyle=playstyle,
                recommendation=recommendation,
            ),
            reply_markup=build_detail_keyboard(
                game,
                goal,
                budget_tier,
                playstyle,
                int(index_str),
                recommendation,
            ),
        )
    await callback.answer()


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
        summary = await StatsService(session).get_summary(user)

    await message.answer(
        "Статистика:\n"
        f"Продаж всего: {summary.total_sales}\n"
        f"Валюты всего: {format_decimal(summary.total_currency)}\n"
        f"Продаж сегодня: {summary.daily_sales}\n"
        f"Валюты сегодня: {format_decimal(summary.daily_currency)}"
    )

    await message.answer(
        "\n".join(
            [
                "Состояние трекинга:",
                f"Активные трекеры: {summary.active_trackers}",
                f"Currency alerts: {summary.active_currency_alerts}",
                f"Сработавшие alerts на паузе: {summary.paused_price_alerts}",
                f"Trade URL watcher'ы: {summary.active_trade_url_watchers}",
                f"Item watcher'ы: {summary.active_item_watchers}",
                f"POE 1 трекеры: {summary.poe1_trackers}",
                f"POE 2 трекеры: {summary.poe2_trackers}",
            ]
        )
    )

    if summary.paused_price_alerts:
        await message.answer(
            f"Сейчас на паузе alerts: {summary.paused_price_alerts}.\n"
            "Открой /alerts, чтобы быстро вернуть их в работу."
        )


@router.message(Command("economy"))
async def economy(message: Message) -> None:
    text, keyboard = await load_economy_panel(message.from_user.id, message.from_user.username)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)

    await message.answer(
        "Шаблоны:\nСначала выбери игру, и я покажу только релевантные наборы.",
        reply_markup=with_home_button(template_browser_game_keyboard()),
    )


@router.callback_query(F.data == "templates:choose_game")
async def templates_choose_game(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Шаблоны:\nСнова выбери игру, и я покажу релевантные цели и наборы.",
        reply_markup=with_home_button(template_browser_game_keyboard()),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:game:"))
async def templates_for_game(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]

    async with session_scope() as session:
        goals = TemplateService(session).list_goals()

    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        f"Шаблоны для {game_label}:\nСначала выбери цель, и я покажу наборы в более полезном порядке.",
        reply_markup=template_goal_keyboard(game, goals),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:goals:"))
async def templates_back_to_goals(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    async with session_scope() as session:
        goals = TemplateService(session).list_goals()

    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        f"Шаблоны для {game_label}:\nСначала выбери цель, и я покажу наборы в более полезном порядке.",
        reply_markup=template_goal_keyboard(game, goals),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:goal:"))
async def templates_for_goal(callback: CallbackQuery) -> None:
    _, _, game, goal_key = callback.data.split(":")

    async with session_scope() as session:
        service = TemplateService(session)
        templates = await service.list_public_for_goal(game, goal_key)
        goal = service.get_goal(goal_key)

    if not templates:
        await callback.answer("Для этой цели шаблонов пока нет", show_alert=True)
        return

    goal_title = goal.title if goal else "Под эту цель"
    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        f"{goal_title} · {game_label}\nНиже уже отсортированы самые релевантные наборы для этой задачи.",
        reply_markup=templates_keyboard(
            templates,
            game=game,
            back_callback=f"templates:goals:{game}",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:all:"))
async def templates_show_all_for_game(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]

    async with session_scope() as session:
        templates = await TemplateService(session).list_public_for_game(game)

    if not templates:
        await callback.answer("Для этой игры шаблонов пока нет", show_alert=True)
        return

    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        f"Все шаблоны для {game_label}\nЕсли нужен не рекомендованный сценарий, можно выбрать набор вручную.",
        reply_markup=templates_keyboard(
            templates,
            game=game,
            back_callback=f"templates:goals:{game}",
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_select:"))
async def choose_template_from_game_list(callback: CallbackQuery) -> None:
    _, game, template_id_raw = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^template:\d+$"))
async def activate_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":", 1)[1])

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"Шаблон: {template.name}\n\n"
        "Сначала выбери игру, для которой применить этот шаблон.",
        reply_markup=template_game_keyboard(template.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_game:"))
async def choose_template_game(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_strategy:"))
async def choose_template_strategy(callback: CallbackQuery) -> None:
    _, template_id_raw, game, strategy_key = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        service = TemplateService(session)
        template = await service.get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    strategy, resolved_items = service.resolve_items(template, strategy_key=strategy_key)
    await callback.message.edit_text(
        build_template_preview_text(template, game, strategy, resolved_items),
        reply_markup=template_strategy_keyboard(
            template.id,
            game,
            service.list_strategies(template),
            strategy.key,
        ),
    )
    await callback.answer("Стратегия обновлена")


@router.callback_query(F.data.startswith("template_strategy_league:"))
async def choose_template_league_for_strategy(callback: CallbackQuery) -> None:
    _, template_id_raw, game, strategy_key = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)
        service = TemplateService(session)
        template = await service.get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    strategy = service.get_strategy(template, strategy_key)
    await callback.message.edit_text(
        f"Шаблон: {template.name}\n"
        f"Игра: {'POE 2' if game == 'poe2' else 'POE 1'}\n"
        f"Стратегия: {strategy.title}\n\n"
        "Теперь выбери лигу, в которую добавить watchers из этого шаблона.",
        reply_markup=template_league_keyboard(template.id, leagues, game, strategy_key),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_pick_league:"))
async def choose_template_league_after_preview(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)
        template = await TemplateService(session).get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"Шаблон: {template.name}\n"
        f"Игра: {'POE 2' if game == 'poe2' else 'POE 1'}\n\n"
        "Теперь выбери лигу, в которую добавить watchers из этого шаблона.",
        reply_markup=template_league_keyboard(template.id, leagues, game),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_back:"))
async def template_back_to_game(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)

    if not template:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_strategy_apply:"))
async def activate_template_for_strategy(callback: CallbackQuery) -> None:
    _, template_id_raw, league_id_raw, strategy_key = callback.data.split(":")
    template_id = int(template_id_raw)
    league_id = int(league_id_raw)

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        league = await LeagueService(session).get_by_id(league_id)
        if not league:
            await callback.answer("Лига не найдена", show_alert=True)
            return

        result = await TemplateService(session).activate(
            user=user,
            template_group_id=template_id,
            league_name=league.name,
            game=league.realm,
            strategy_key=strategy_key,
        )

    if not result:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(build_template_activation_text(result, league))
    await callback.answer("Шаблон подключен")


@router.callback_query(F.data.startswith("template_league:"))
async def activate_template_for_league(callback: CallbackQuery) -> None:
    _, template_id_raw, league_id_raw = callback.data.split(":")
    template_id = int(template_id_raw)
    league_id = int(league_id_raw)

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        league = await LeagueService(session).get_by_id(league_id)
        if not league:
            await callback.answer("Лига не найдена", show_alert=True)
            return

        result = await TemplateService(session).activate(
            user=user,
            template_group_id=template_id,
            league_name=league.name,
            game=league.realm,
        )

    if not result:
        await callback.answer("Шаблон не найден", show_alert=True)
        return

    await callback.message.edit_text(build_template_activation_text(result, league))
    await callback.answer("Шаблон подключен")


@router.callback_query(F.data == "template:cancel")
async def cancel_template_activation(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Ок, отменил подключение шаблона.",
        reply_markup=menu_section_keyboard(("Домой", "menu:home"), include_home=False),
    )
    await callback.answer("Отменено")


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    text, _ = await load_account_panel(message.from_user.id, message.from_user.username)
    await message.answer(
        "Настройки MVP:\n"
        "Лига по умолчанию берётся из DEFAULT_LEAGUE_NAME.\n\n"
        f"{text}\n\n"
        "Для управления привязкой открой /account.",
    )
