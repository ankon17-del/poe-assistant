from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.bot.dependencies import session_scope
from app.bot.i18n import DEFAULT_LOCALE, LANGUAGE_NAMES, normalize_locale, tr
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
    language_keyboard,
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
from app.services.poe_account import PoeAccountApiService, PoeAccountError
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


async def load_user_locale(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> str:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        if user.language:
            return normalize_locale(user.language)
    return normalize_locale(telegram_locale) if telegram_locale else DEFAULT_LOCALE


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


def build_account_text(*, integration, oauth_config_error: str | None, locale: str = DEFAULT_LOCALE, snapshot=None, live_error: str | None = None) -> str:
    copy = {
        "ru": {
            "title": "Аккаунт",
            "connected": "Статус: подключён",
            "disconnected": "Статус: не подключён",
            "account": "Аккаунт",
            "oauth_unavailable": "OAuth сейчас недоступен",
            "connect_hint": "Подключи PoE-аккаунт кнопкой ниже. После этого бот сможет читать профиль, персонажей, лиги и личный тайник.",
            "connected_hint": "Официальная привязка уже работает. Ниже можно обновить статус, сменить язык или отключить аккаунт.",
            "profile": "Профиль",
            "poe1_leagues": "POE1 лиги",
            "poe1_main": "Основная лига для stash",
            "poe1_chars": "POE1 персонажи",
            "poe2_chars": "POE2 персонажи",
            "live_error": "Ошибка live-данных",
        },
        "en": {
            "title": "Account",
            "connected": "Status: connected",
            "disconnected": "Status: not connected",
            "account": "Account",
            "oauth_unavailable": "OAuth is currently unavailable",
            "connect_hint": "Connect your PoE account below. After that, the bot can read your profile, characters, leagues, and personal stash.",
            "connected_hint": "Official account linking is active. You can refresh the status, change language, or disconnect below.",
            "profile": "Profile",
            "poe1_leagues": "POE1 leagues",
            "poe1_main": "Primary stash league",
            "poe1_chars": "POE1 characters",
            "poe2_chars": "POE2 characters",
            "live_error": "Live data error",
        },
        "fr": {
            "title": "Compte",
            "connected": "Statut : connecté",
            "disconnected": "Statut : non connecté",
            "account": "Compte",
            "oauth_unavailable": "OAuth est actuellement indisponible",
            "connect_hint": "Connecte ton compte PoE ci-dessous. Ensuite, le bot pourra lire ton profil, tes personnages, tes ligues et ton coffre personnel.",
            "connected_hint": "La liaison officielle est active. Tu peux actualiser le statut, changer de langue ou déconnecter le compte ci-dessous.",
            "profile": "Profil",
            "poe1_leagues": "Ligues POE1",
            "poe1_main": "Ligue principale pour le coffre",
            "poe1_chars": "Personnages POE1",
            "poe2_chars": "Personnages POE2",
            "live_error": "Erreur de données live",
        },
        "de": {
            "title": "Konto",
            "connected": "Status: verbunden",
            "disconnected": "Status: nicht verbunden",
            "account": "Konto",
            "oauth_unavailable": "OAuth ist derzeit nicht verfügbar",
            "connect_hint": "Verbinde unten dein PoE-Konto. Danach kann der Bot Profil, Charaktere, Ligen und den persönlichen Stash lesen.",
            "connected_hint": "Die offizielle Verknüpfung ist aktiv. Unten kannst du den Status aktualisieren, die Sprache ändern oder die Verbindung trennen.",
            "profile": "Profil",
            "poe1_leagues": "POE1-Ligen",
            "poe1_main": "Primäre Stash-Liga",
            "poe1_chars": "POE1-Charaktere",
            "poe2_chars": "POE2-Charaktere",
            "live_error": "Live-Datenfehler",
        },
    }
    trm = copy.get(locale, copy["en"])
    lines = [trm["title"]]
    if integration:
        lines.append(trm["connected"])
        if integration.external_account_name:
            lines.append(f"{trm['account']}: {integration.external_account_name}")
        if integration.scopes:
            lines.append(f"Scopes: {integration.scopes}")
    else:
        lines.append(trm["disconnected"])

    if snapshot:
        lines.append("")
        if snapshot.profile_name:
            lines.append(f"{trm['profile']}: {snapshot.profile_name}")
        lines.append(f"{trm['poe1_leagues']}: {len(snapshot.poe1_leagues)}")
        if snapshot.poe1_primary_league:
            lines.append(f"{trm['poe1_main']}: {snapshot.poe1_primary_league}")
        lines.append(f"{trm['poe1_chars']}: {snapshot.poe1_character_count}")
        lines.append(f"{trm['poe2_chars']}: {snapshot.poe2_character_count}")
        if getattr(snapshot, "poe1_stash_note", None):
            lines.append("")
            lines.append(snapshot.poe1_stash_note)

    if oauth_config_error:
        lines.append("")
        lines.append(f"{trm['oauth_unavailable']}: {oauth_config_error}")
    elif live_error:
        lines.append("")
        lines.append(f"{trm['live_error']}: {live_error}")
    elif integration:
        lines.append("")
        lines.append(trm["connected_hint"])
    else:
        lines.append("")
        lines.append(trm["connect_hint"])

    return "\n".join(lines)


def _stash_preview_text(tab) -> str:
    preview_items = tuple(item for item in tab.preview_items[:2] if item)
    return ", ".join(preview_items)


def _build_stash_takeaways(live, locale: str) -> tuple[str, ...]:
    copy = {
        "ru": {
            "liquid": "Открой {name}: {count} предметов{reason}. Это лучший кандидат на быструю продажу.",
            "liquid_preview": "Открой {name}: {count} предметов{reason}. Начни с него. Например: {preview}.",
            "dump": "Разбери {name}: {count} предметов в обычной вкладке, это похоже на dump-tab.",
            "dump_preview": "Разбери {name}: {count} предметов в обычной вкладке. Например: {preview}.",
            "dense": "Проверь {name}: вкладка очень плотная ({count} предметов), там легко пропустить что-то ценное.",
            "dense_preview": "Проверь {name}: вкладка очень плотная ({count} предметов). Например: {preview}.",
            "empty": "Есть {count} пустых вкладок: можно выделить одну под продажу, а вторую под сортировку.",
        },
        "en": {
            "liquid": "Open {name}: {count} items{reason}. This is your best quick-sale candidate.",
            "liquid_preview": "Open {name}: {count} items{reason}. Start there. For example: {preview}.",
            "dump": "Sort {name}: {count} items in a regular tab, so it looks like a dump tab.",
            "dump_preview": "Sort {name}: {count} items in a regular tab. For example: {preview}.",
            "dense": "Check {name}: it is very dense ({count} items), so valuable pieces are easy to miss.",
            "dense_preview": "Check {name}: it is very dense ({count} items). For example: {preview}.",
            "empty": "You have {count} empty tabs: keep one for selling and one for sorting.",
        },
        "fr": {
            "liquid": "Ouvre {name} : {count} objets{reason}. C'est le meilleur candidat pour une vente rapide.",
            "liquid_preview": "Ouvre {name} : {count} objets{reason}. Commence par lui. Par exemple : {preview}.",
            "dump": "Trie {name} : {count} objets dans un onglet normal, cela ressemble à un dump tab.",
            "dump_preview": "Trie {name} : {count} objets dans un onglet normal. Par exemple : {preview}.",
            "dense": "Vérifie {name} : l'onglet est très chargé ({count} objets), donc on peut y rater quelque chose de précieux.",
            "dense_preview": "Vérifie {name} : l'onglet est très chargé ({count} objets). Par exemple : {preview}.",
            "empty": "Tu as {count} onglets vides : garde-en un pour la vente et un pour le tri.",
        },
        "de": {
            "liquid": "Öffne {name}: {count} Items{reason}. Das ist dein bester Kandidat für einen schnellen Verkauf.",
            "liquid_preview": "Öffne {name}: {count} Items{reason}. Fang dort an. Zum Beispiel: {preview}.",
            "dump": "Sortiere {name}: {count} Items in einem normalen Tab, das sieht nach einem Dump-Tab aus.",
            "dump_preview": "Sortiere {name}: {count} Items in einem normalen Tab. Zum Beispiel: {preview}.",
            "dense": "Prüfe {name}: Der Tab ist sehr voll ({count} Items), dort übersieht man leicht etwas Wertvolles.",
            "dense_preview": "Prüfe {name}: Der Tab ist sehr voll ({count} Items). Zum Beispiel: {preview}.",
            "empty": "Du hast {count} leere Tabs: einen kannst du für Verkäufe und einen fürs Sortieren reservieren.",
        },
    }
    trm = copy.get(locale, copy["en"])
    takeaways: list[str] = []

    if live.liquid_tabs:
        tab = live.liquid_tabs[0]
        reason = f" ({tab.priority_reason})" if tab.priority_reason else ""
        preview = _stash_preview_text(tab)
        template = trm["liquid_preview"] if preview else trm["liquid"]
        takeaways.append(template.format(name=tab.name, count=tab.item_count, reason=reason, preview=preview))

    if live.dump_tabs:
        tab = live.dump_tabs[0]
        preview = _stash_preview_text(tab)
        template = trm["dump_preview"] if preview else trm["dump"]
        takeaways.append(template.format(name=tab.name, count=tab.item_count, preview=preview))
    elif live.dense_tabs:
        tab = live.dense_tabs[0]
        preview = _stash_preview_text(tab)
        template = trm["dense_preview"] if preview else trm["dense"]
        takeaways.append(template.format(name=tab.name, count=tab.item_count, preview=preview))

    if live.empty_tabs >= 2:
        takeaways.append(trm["empty"].format(count=live.empty_tabs))

    return tuple(takeaways[:3])


def _build_stash_tab_line(tab, include_reason: bool = False) -> str:
    line = f"- {tab.name}: {tab.item_count}"
    if include_reason and tab.priority_reason:
        line += f" ({tab.priority_reason})"
    preview = _stash_preview_text(tab)
    if preview:
        line += f" | {preview}"
    return line


def build_stash_text(summary, locale: str = DEFAULT_LOCALE) -> str:
    copy = {
        "ru": {
            "title": "Тайник",
            "connected": "PoE аккаунт: подключён",
            "not_connected": "PoE аккаунт: пока не подключён",
            "blocker": "OAuth blocker",
            "status": "Статус:",
            "live": "Live stash snapshot:",
            "tabs": "вкладок",
            "folders": "папок",
            "special": "спец-вкладок",
            "empty": "пустых вкладок",
            "items": "предметов в просмотренных вкладках",
            "sample": "Примеры вкладок",
            "takeaways": "Что делать первым",
            "sell": "Что можно продать первым",
            "source": "Источник оценки",
            "valuation_unavailable": "Оценка рыночной стоимости сейчас недоступна. Список sell-first появится после стабилизации источника цен.",
            "liquid": "Что проверить первым",
            "dense": "Самые плотные вкладки",
            "dump": "Что похоже на dump-разбор",
            "next_steps": "Следующие шаги:",
            "cached": "Показан недавний кэшированный снимок, чтобы не упираться в лимиты PoE API.",
            "partial": "Часть вкладок не успела обновиться: {count}. Данные могут быть неполными.",
            "footer": "Phase 6 теперь активна: официальный OAuth получен, и дальше мы переводим тайник из read-only readiness в реальный личный stash assistant.",
        },
        "en": {
            "title": "Stash",
            "connected": "PoE account: connected",
            "not_connected": "PoE account: not connected yet",
            "blocker": "OAuth blocker",
            "status": "Status:",
            "live": "Live stash snapshot:",
            "tabs": "tabs",
            "folders": "folders",
            "special": "special tabs",
            "empty": "empty tabs",
            "items": "items in reviewed tabs",
            "takeaways": "What to do first",
            "sample": "Sample tabs",
            "sell": "What to sell first",
            "source": "Valuation source",
            "valuation_unavailable": "Market valuation is currently unavailable. The sell-first list will appear once the pricing source is stable.",
            "liquid": "Check these first",
            "dense": "Densest tabs",
            "dump": "Likely dump tabs",
            "next_steps": "Next steps:",
            "cached": "Showing a recent cached snapshot to avoid hitting the PoE API rate limit.",
            "partial": "{count} tabs could not be refreshed in time. This snapshot may be incomplete.",
            "footer": "Phase 6 is now active: official OAuth is in place, and the next move is to turn stash readiness into a real personal stash assistant.",
        },
        "fr": {
            "title": "Coffre",
            "connected": "Compte PoE : connecté",
            "not_connected": "Compte PoE : pas encore connecté",
            "blocker": "Blocage OAuth",
            "status": "Statut :",
            "live": "Snapshot live du coffre :",
            "tabs": "onglets",
            "folders": "dossiers",
            "special": "onglets spéciaux",
            "empty": "onglets vides",
            "items": "objets dans les onglets analysés",
            "takeaways": "Par quoi commencer",
            "sample": "Exemples d'onglets",
            "sell": "À vendre en premier",
            "source": "Source d'estimation",
            "valuation_unavailable": "L'estimation du marché est indisponible pour le moment. La liste de vente prioritaire apparaîtra dès que la source de prix sera stable.",
            "liquid": "À vérifier en premier",
            "dense": "Onglets les plus chargés",
            "dump": "Onglets à trier",
            "next_steps": "Étapes suivantes :",
            "cached": "Affichage d'un snapshot récent mis en cache pour éviter la limite de l'API PoE.",
            "partial": "{count} onglets n'ont pas pu être actualisés à temps. Le snapshot peut être incomplet.",
            "footer": "La phase 6 est maintenant active : l'OAuth officiel est obtenu, et la suite consiste à transformer ce panneau en véritable assistant de coffre personnel.",
        },
        "de": {
            "title": "Stash",
            "connected": "PoE-Konto: verbunden",
            "not_connected": "PoE-Konto: noch nicht verbunden",
            "blocker": "OAuth-Blocker",
            "status": "Status:",
            "live": "Live-Stash-Snapshot:",
            "tabs": "Tabs",
            "folders": "Ordner",
            "special": "Spezial-Tabs",
            "empty": "leere Tabs",
            "items": "Items in geprüften Tabs",
            "takeaways": "Womit du anfangen solltest",
            "sample": "Beispiel-Tabs",
            "sell": "Das zuerst verkaufen",
            "source": "Bewertungsquelle",
            "valuation_unavailable": "Die Marktbewertung ist derzeit nicht verfügbar. Die Sell-first-Liste erscheint, sobald die Preisquelle stabil ist.",
            "liquid": "Das zuerst prüfen",
            "dense": "Dichteste Tabs",
            "dump": "Tabs zum Aussortieren",
            "next_steps": "Nächste Schritte:",
            "cached": "Es wird ein aktueller Cache-Snapshot angezeigt, damit wir nicht ins PoE-API-Limit laufen.",
            "partial": "{count} Tabs konnten nicht rechtzeitig aktualisiert werden. Dieser Snapshot kann unvollständig sein.",
            "footer": "Phase 6 ist jetzt aktiv: offizielles OAuth ist da, und als Nächstes bauen wir daraus einen echten persönlichen Stash-Assistenten.",
        },
    }
    trm = copy.get(locale, copy["en"])
    lines = [trm["title"], ""]

    if summary.account_connected:
        if summary.account_name:
            lines.append(f"{trm['connected']} ({summary.account_name})")
        else:
            lines.append(trm["connected"])
    else:
        lines.append(trm["not_connected"])

    if summary.approved_scopes:
        lines.append(f"Scopes: {' '.join(summary.approved_scopes)}")
    if summary.oauth_blocker:
        lines.append(f"{trm['blocker']}: {summary.oauth_blocker}")

    lines.append("")
    lines.append(trm["status"])
    for item in summary.statuses:
        lines.append(f"- {item.title}: {item.status}")
        lines.append(f"  {item.detail}")

    if summary.live_snapshot:
        live = summary.live_snapshot
        lines.append("")
        lines.append(f"{trm['live']} {live.league_name}")
        lines.append(f"- {live.total_tabs} {trm['tabs']}")
        lines.append(f"- {live.folder_tabs} {trm['folders']}")
        lines.append(f"- {live.special_tabs} {trm['special']}")
        lines.append(f"- {live.empty_tabs} {trm['empty']}")
        lines.append(f"- {live.total_items} {trm['items']}")
        if live.is_cached:
            lines.append(f"- {trm['cached']}")
        elif live.is_partial:
            lines.append(f"- {trm['partial'].format(count=live.failed_tabs)}")
        if live.sample_tabs:
            lines.append(f"- {trm['sample']}: {', '.join(live.sample_tabs)}")
        takeaways = _build_stash_takeaways(live, locale)
        if takeaways:
            lines.append("")
            lines.append(f"{trm['takeaways']}:")
            for takeaway in takeaways:
                lines.append(f"- {takeaway}")
        if summary.priced_candidates:
            lines.append("")
            lines.append(f"{trm['sell']}:")
            for candidate in summary.priced_candidates[:6]:
                unit_text = format_decimal(Decimal(str(candidate.unit_price_chaos)))
                total_text = format_decimal(Decimal(str(candidate.total_price_chaos)))
                lines.append(
                    f"- {candidate.item_name} x{candidate.quantity} [{candidate.tab_name}] ~ {total_text} chaos ({unit_text}c/ea)"
                )
            if summary.valuation_source:
                lines.append(f"- {trm['source']}: {summary.valuation_source}")
        elif live.total_items > 0:
            lines.append("")
            lines.append(trm["valuation_unavailable"])
        if live.liquid_tabs:
            lines.append("")
            lines.append(f"{trm['liquid']}:")
            for tab in live.liquid_tabs:
                lines.append(_build_stash_tab_line(tab, include_reason=True))
        if live.dense_tabs:
            lines.append("")
            lines.append(f"{trm['dense']}:")
            for tab in live.dense_tabs:
                lines.append(_build_stash_tab_line(tab))
        if live.dump_tabs:
            lines.append("")
            lines.append(f"{trm['dump']}:")
            for tab in live.dump_tabs:
                lines.append(_build_stash_tab_line(tab))
    elif summary.live_error:
        lines.append("")
        lines.append(f"{trm['live']} {summary.live_error}")

    lines.append("")
    lines.append(trm["next_steps"])
    for step in summary.next_steps:
        lines.append(f"- {step}")

    lines.append("")
    lines.append(trm["footer"])
    return "\n".join(lines)


def build_stash_guide_text(guide, locale: str = DEFAULT_LOCALE) -> str:
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
    footer = {
        "ru": "Это ручной playbook: уже полезно без OAuth, а потом мы наложим на него живой stash-scan и автоматические инсайты.",
        "en": "This is a manual playbook: useful even without OAuth today, and later we can layer live stash scans and automatic insights on top.",
        "fr": "Ceci est un playbook manuel : déjà utile sans OAuth aujourd'hui, et plus tard on pourra y superposer un scan vivant du coffre et des insights automatiques.",
        "de": "Das ist ein manuelles Playbook: schon heute ohne OAuth nützlich, und später können wir Live-Stash-Scans und automatische Insights darauf legen.",
    }.get(locale, "")
    lines.append(footer)
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
        f"Шаблон подключён · {result.template_name}",
        f"{game_label} / {league.name}",
        f"Стратегия: {result.strategy_name}",
        f"Создано: {result.created_count}",
        f"Обновлено или реактивировано: {result.updated_count}",
    ]

    if result.created_items:
        lines.append("")
        lines.append("Созданы:")
        lines.extend(f"- {item_name}" for item_name in result.created_items)

    if result.updated_items:
        lines.append("")
        lines.append("Обновлены / реактивированы:")
        lines.extend(f"- {item_name}" for item_name in result.updated_items)

    return "\n".join(lines)


def build_assistant_intro_text(locale: str = DEFAULT_LOCALE) -> str:
    return tr(locale, "assistant_intro")


def build_home_text(locale: str = DEFAULT_LOCALE) -> str:
    return (
        f"{tr(locale, 'welcome_title')}\n\n"
        f"{tr(locale, 'welcome_body')}\n\n"
        f"{tr(locale, 'welcome_features')}\n"
        f"- {tr(locale, 'welcome_feature_templates')}\n"
        f"- {tr(locale, 'welcome_feature_economy')}\n"
        f"- {tr(locale, 'welcome_feature_builds')}\n"
        f"- {tr(locale, 'welcome_feature_tracking')}\n"
        f"- {tr(locale, 'welcome_feature_account')}\n\n"
        f"{tr(locale, 'welcome_disclaimer')}"
    )


def build_menu_help_text(locale: str = DEFAULT_LOCALE) -> str:
    return (
        f"{tr(locale, 'help_title')}:\n\n"
        f"{tr(locale, 'help_line_menu')}\n"
        f"{tr(locale, 'help_line_add')}\n"
        f"{tr(locale, 'help_line_templates')}\n"
        f"{tr(locale, 'help_line_economy')}\n"
        f"{tr(locale, 'help_line_builds')}\n"
        f"{tr(locale, 'help_line_list')}\n"
        f"{tr(locale, 'help_line_alerts')}\n"
        f"{tr(locale, 'help_line_account')}\n"
        f"{tr(locale, 'help_line_stash')}\n"
        f"{tr(locale, 'help_line_stats')}\n"
        f"{tr(locale, 'help_line_settings')}"
    )


def build_templates_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_templates_title')}\n\n{tr(locale, 'section_templates_body')}"


def build_economy_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_economy_title')}\n\n{tr(locale, 'section_economy_body')}"


def build_builds_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_builds_title')}\n\n{tr(locale, 'section_builds_body')}"


def build_tracking_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_tracking_title')}\n\n{tr(locale, 'section_tracking_body')}"


def build_account_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_account_title')}\n\n{tr(locale, 'section_account_body')}"


def build_stash_section_text(locale: str = DEFAULT_LOCALE) -> str:
    return f"{tr(locale, 'section_stash_title')}\n\n{tr(locale, 'section_stash_body')}"


def build_tracking_result_text(item, action: str, locale: str = DEFAULT_LOCALE) -> str:
    lines = [f"{action} ? #{item.id} {item.item_name}"]
    if item.league:
        game_label = "POE 2" if item.league.realm == "poe2" else "POE 1"
        lines.append(f"{game_label} / {item.league.name}")
    if item.target_price is not None:
        lines.append(f"Threshold: {format_decimal(Decimal(item.target_price))} {item.target_currency}")
    if item.trade_url:
        lines.append("Source: trade URL")
    return "\n".join(lines)


def build_goal_prompt_text(game: str, locale: str = DEFAULT_LOCALE) -> str:
    game_label = BuildService.game_label(game)
    return tr(locale, "build_goal_prompt", game=game_label)


def build_budget_prompt_text(game: str, goal: str, locale: str = DEFAULT_LOCALE) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    return tr(locale, "build_budget_prompt", game=game_label, goal=goal_label)


def build_playstyle_prompt_text(game: str, goal: str, budget_tier: str, locale: str = DEFAULT_LOCALE) -> str:
    game_label = BuildService.game_label(game)
    goal_label = BuildService.goal_label(goal)
    budget_label = BuildService.budget_label(budget_tier)
    return tr(locale, "build_playstyle_prompt", game=game_label, goal=goal_label, budget=budget_label)


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
        *(
            ["Референсы: кнопки planner / guide / tree / atlas ниже."]
            if (recommendation.planner_url or recommendation.guide_url or recommendation.tree_url or recommendation.atlas_url)
            else []
        ),
        f"Примерный бюджет: {recommendation.budget_estimate}",
        f"Покупать в первую очередь: {', '.join(recommendation.buy_priority)}",
        f"Какие статы добирать: {', '.join(recommendation.stat_targets)}",
        f"Дерево / приоритеты прокачки: {', '.join(recommendation.tree_focus)}",
        f"Атлас / направление фарма: {', '.join(recommendation.atlas_focus)}",
        f"Что этим билдом фармить: {', '.join(recommendation.farm_mechanics)}",
        "Эндгейм-чеклист по слотам:",
        *[f"  - {entry}" for entry in recommendation.endgame_slot_checklist],
        f"Эндгейм-цели: {', '.join(recommendation.endgame_goals)}",
    ]

    if (
        recommendation.main_skill_setup
        or recommendation.utility_setup
        or recommendation.defensive_setup
        or recommendation.support_priorities
    ):
        lines.append("Gem setup:")
        if recommendation.main_skill_setup:
            lines.append(f"  - Main: {'; '.join(recommendation.main_skill_setup[:2])}")
        if recommendation.utility_setup:
            lines.append(f"  - Utility: {'; '.join(recommendation.utility_setup[:2])}")
        if recommendation.defensive_setup:
            lines.append(f"  - Defense: {'; '.join(recommendation.defensive_setup[:2])}")
        if recommendation.support_priorities:
            lines.append(f"  - Supports: {'; '.join(recommendation.support_priorities[:2])}")

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


async def load_account_panel(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> tuple[str, object]:
    snapshot = None
    live_error: str | None = None
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        integration = await IntegrationService(session).get_by_type(user, IntegrationType.poe_oauth)
        locale = normalize_locale(user.language or telegram_locale or DEFAULT_LOCALE)
        if integration:
            try:
                snapshot = await PoeAccountApiService(session).get_account_snapshot(user)
            except PoeAccountError as exc:
                live_error = str(exc)

    oauth_service = PoeOAuthService()
    connect_url: str | None = None
    oauth_config_error: str | None = None
    try:
        connect_url = oauth_service.build_connect_url(telegram_id=telegram_id)
    except PoeOAuthConfigError as exc:
        oauth_config_error = str(exc)

    text = build_account_text(
        integration=integration,
        oauth_config_error=oauth_config_error,
        locale=locale,
        snapshot=snapshot,
        live_error=live_error,
    )
    keyboard = account_keyboard(connect_url=connect_url, is_connected=integration is not None, locale=locale)
    return text, keyboard


async def load_stash_panel(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        summary = await StashService(session).get_panel_summary(user)
        locale = normalize_locale(user.language or telegram_locale or DEFAULT_LOCALE)

    connect_url = None
    if summary.oauth_available and not summary.account_connected:
        oauth_service = PoeOAuthService()
        try:
            connect_url = oauth_service.build_connect_url(telegram_id=telegram_id)
        except PoeOAuthConfigError:
            connect_url = None

    return build_stash_text(summary, locale), stash_keyboard(connect_url=connect_url, account_connected=summary.account_connected, locale=locale)


async def load_tracking_panel(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        items = await TrackingService(session).list_items(user)
        locale = normalize_locale(user.language or telegram_locale or DEFAULT_LOCALE)

    if not items:
        empty_text = (
            "No active tracking yet. Use /add to create your first watcher."
            if locale != 'ru'
            else "Активного трекинга пока нет. Добавь первый вотчер через /add."
        )
        return empty_text, menu_section_keyboard((tr(locale, 'add_tracking'), 'menu:add'), locale=locale)
    return build_tracking_list_text(items), with_home_button(tracking_actions_keyboard(items, locale=locale), locale=locale)


async def load_alerts_panel(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        items = await TrackingService(session).list_paused_price_alerts(user)
        locale = normalize_locale(user.language or telegram_locale or DEFAULT_LOCALE)

    if not items:
        empty_text = (
            "No triggered price alerts yet. When an alert fires, it will appear here so you can restart it quickly."
            if locale != 'ru'
            else "Сработавших price alerts пока нет. Когда alert сработает, он появится здесь, и его можно будет быстро перезапустить."
        )
        return empty_text, menu_section_keyboard((tr(locale, 'open_economy'), 'menu:economy'), locale=locale)
    return build_paused_alerts_text(items), with_home_button(paused_alerts_keyboard(items, locale=locale), locale=locale)


async def load_economy_panel(telegram_id: int, username: str | None, telegram_locale: str | None = None) -> tuple[str, object]:
    async with session_scope() as session:
        user = await ensure_user(session, telegram_id, username)
        summaries, overview = await EconomyService(session).get_user_economy_dashboard(user)
        locale = normalize_locale(user.language or telegram_locale or DEFAULT_LOCALE)

    return build_economy_text(summaries, overview), menu_section_keyboard(
        ("Refresh economy" if locale != 'ru' else "Обновить экономику", 'menu:economy'),
        ("Open alerts" if locale != 'ru' else "Открыть alerts", 'menu:alerts'),
        locale=locale,
    )


async def answer_home_screen(message: Message) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, message.from_user.id, message.from_user.username)
    locale = normalize_locale(user.language or message.from_user.language_code or DEFAULT_LOCALE)
    if not user.language:
        await message.answer(tr(locale, 'start_language_first'), reply_markup=language_keyboard(locale, back_callback='menu:home'))
        return
    await message.answer(build_home_text(locale), reply_markup=home_menu_keyboard(locale))


async def edit_home_screen(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(build_home_text(locale), reply_markup=home_menu_keyboard(locale))
    await callback.answer()


async def begin_add_wizard(message: Message, state: FSMContext) -> None:
    locale = await load_user_locale(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await state.clear()
    await state.set_state(AddTrackingStates.choosing_mode)
    await show_wizard_message(
        state=state,
        bot=message.bot,
        chat_id=message.chat.id,
        text=f"{tr(locale, 'wizard_new_tracking')}\n\n{tr(locale, 'wizard_step_source')}",
        reply_markup=add_entry_keyboard(locale),
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
    action_text = "Обновлён трекинг" if result.action == "updated" else "Добавлен трекинг"
    locale = normalize_locale(user.language) if user.language else DEFAULT_LOCALE

    await finish_wizard(
        state=state,
        bot=bot,
        chat_id=chat_id,
        text=build_tracking_result_text(item, action_text, locale),
        reply_markup=with_home_button(tracking_actions_keyboard([item], locale), locale=locale),
    )


@router.message(Command("start"))
async def start(message: Message) -> None:
    await answer_home_screen(message)


@router.message(Command("menu"))
async def menu(message: Message) -> None:
    await answer_home_screen(message)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    locale = await load_user_locale(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(
        build_menu_help_text(locale),
        reply_markup=menu_section_keyboard((tr(locale, "open_menu"), "menu:home"), locale=locale),
    )


@router.callback_query(F.data == "menu:home")
async def menu_home(callback: CallbackQuery) -> None:
    await edit_home_screen(callback)


@router.callback_query(F.data == "menu:help")
async def menu_help(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_menu_help_text(locale),
            reply_markup=menu_section_keyboard((tr(locale, "home"), "menu:home"), include_home=False, locale=locale),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:templates")
async def menu_templates(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_templates_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "open_templates"), "menu:templates:open"),
                (tr(locale, "manual_tracking"), "menu:add"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:economy")
async def menu_economy(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_economy_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "open_economy_dashboard"), "menu:economy:open"),
                (tr(locale, "open_alerts"), "menu:alerts:open"),
                (tr(locale, "market_templates"), "menu:templates:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:builds")
async def menu_builds(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_builds_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "pick_build"), "menu:builds:open"),
                (tr(locale, "open_templates"), "menu:templates:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:tracking")
async def menu_tracking(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_tracking_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "active_tracking"), "menu:tracking:open"),
                (tr(locale, "add_tracking"), "menu:add"),
                (tr(locale, "open_alerts"), "menu:alerts:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:alerts")
async def menu_alerts(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            f"{tr(locale, 'alerts_section_title')}\n\n{tr(locale, 'alerts_section_body')}",
            reply_markup=menu_section_keyboard(
                (tr(locale, "open_alerts"), "menu:alerts:open"),
                (tr(locale, "open_economy"), "menu:economy:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:account")
async def menu_account(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_account_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "open_account_panel"), "menu:account:open"),
                (tr(locale, "open_stash"), "menu:stash:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:stash")
async def menu_stash(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_stash_section_text(locale),
            reply_markup=menu_section_keyboard(
                (tr(locale, "open_stash_panel"), "menu:stash:open"),
                (tr(locale, "open_account"), "menu:account:open"),
                locale=locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:templates:open")
async def menu_templates_open(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            f"{tr(locale, 'templates')}:\n{tr(locale, 'friendly_templates_hint')}",
            reply_markup=with_home_button(template_browser_game_keyboard(locale), locale=locale),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:economy:open")
async def menu_economy_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_economy_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:builds:open")
async def menu_builds_open(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_assistant_intro_text(locale),
            reply_markup=with_home_button(build_game_keyboard(locale), locale=locale),
        )
    await callback.answer()


@router.callback_query(F.data == "menu:tracking:open")
async def menu_tracking_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_tracking_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:alerts:open")
async def menu_alerts_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_alerts_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:account:open")
async def menu_account_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:stash:open")
async def menu_stash_open(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "menu:add")
async def menu_add(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.message:
        await begin_add_wizard(callback.message, state)
    await callback.answer()


@router.message(Command("account"))
async def account(message: Message) -> None:
    text, keyboard = await load_account_panel(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("stash"))
async def stash(message: Message) -> None:
    text, keyboard = await load_stash_panel(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("builds"))
async def builds(message: Message) -> None:
    locale = await load_user_locale(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(build_assistant_intro_text(locale), reply_markup=with_home_button(build_game_keyboard(locale), locale=locale))


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

    action_text = "Обновлён трекинг" if result.action == "updated" else "Добавлен трекинг"
    locale = normalize_locale(user.language) if user.language else normalize_locale(message.from_user.language_code)
    await message.answer(
        build_tracking_result_text(result.item, action_text, locale),
        reply_markup=with_home_button(tracking_actions_keyboard([result.item], locale), locale=locale),
    )


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
        await callback.message.edit_text(
            "Активного трекинга пока нет.",
            reply_markup=menu_section_keyboard(("Добавить трекинг", "menu:add")),
        )
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=with_home_button(tracking_actions_keyboard(items)),
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
        await callback.message.edit_text(
            "Активного трекинга пока нет.",
            reply_markup=menu_section_keyboard(("Добавить трекинг", "menu:add")),
        )
        return

    await callback.message.edit_text(
        build_tracking_list_text(items),
        reply_markup=with_home_button(tracking_actions_keyboard(items)),
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
        reply_markup=with_home_button(tracking_actions_keyboard(items)),
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
        await callback.message.edit_text(
            "Сработавших alerts на паузе больше нет. Всё снова активно.",
            reply_markup=menu_section_keyboard(("Открыть экономику", "menu:economy:open")),
        )
        return

    await callback.message.edit_text(
        build_paused_alerts_text(items),
        reply_markup=with_home_button(paused_alerts_keyboard(items)),
    )


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
        await callback.message.edit_text(
            "Сработавших alerts на паузе больше нет. Всё снова активно.",
            reply_markup=menu_section_keyboard(("Открыть экономику", "menu:economy:open")),
        )
        return

    await callback.message.edit_text(
        build_paused_alerts_text(items),
        reply_markup=with_home_button(paused_alerts_keyboard(items)),
    )


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
        await callback.message.edit_text(
            "Сработавших alerts на паузе больше нет. Всё снова активно.",
            reply_markup=menu_section_keyboard(("Открыть экономику", "menu:economy:open")),
        )
        return

    await callback.message.edit_text(
        build_paused_alerts_text(items),
        reply_markup=with_home_button(paused_alerts_keyboard(items)),
    )


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
        await callback.message.edit_text(
            "Сработавших alerts на паузе больше нет.",
            reply_markup=menu_section_keyboard(("Открыть экономику", "menu:economy:open")),
        )
        return

    await callback.message.edit_text(
        build_paused_alerts_text(items),
        reply_markup=with_home_button(paused_alerts_keyboard(items)),
    )


@router.callback_query(F.data == "account:refresh")
async def refresh_account_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "account:disconnect")
async def disconnect_account(callback: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        disconnected = await IntegrationService(session).disconnect(user, IntegrationType.poe_oauth)

    if not disconnected:
        await callback.answer("PoE аккаунт уже не подключён", show_alert=True)
        return

    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "stash:refresh")
async def refresh_stash_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "stash:back:panel")
async def stash_back_to_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_stash_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("stash:guide:"))
async def stash_open_guide(callback: CallbackQuery) -> None:
    slug = callback.data.rsplit(":", 1)[1]
    guide = StashService.get_guide(slug)
    if guide is None:
        await callback.answer("Этот stash-playbook не найден", show_alert=True)
        return
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(build_stash_guide_text(guide, locale), reply_markup=stash_guide_keyboard(locale))


@router.callback_query(F.data == "stash:account")
async def stash_open_account_panel(callback: CallbackQuery) -> None:
    text, keyboard = await load_account_panel(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(F.data == "builds:back:game")
async def builds_back_to_game(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_assistant_intro_text(locale),
            reply_markup=with_home_button(build_game_keyboard(locale), locale=locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:game:"))
async def builds_choose_goal(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(build_goal_prompt_text(game, locale), reply_markup=build_goal_keyboard(game, locale))
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:goal:"))
async def builds_back_to_goal(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(build_goal_prompt_text(game, locale), reply_markup=build_goal_keyboard(game, locale))
    await callback.answer()


@router.callback_query(F.data.startswith("builds:goal:"))
async def builds_choose_budget(callback: CallbackQuery) -> None:
    _, _, game, goal = callback.data.split(":")
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_budget_prompt_text(game, goal, locale),
            reply_markup=build_budget_keyboard(game, goal, locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:budget:"))
async def builds_back_to_budget(callback: CallbackQuery) -> None:
    _, _, _, game, goal = callback.data.split(":")
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_budget_prompt_text(game, goal, locale),
            reply_markup=build_budget_keyboard(game, goal, locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:budget:"))
async def builds_choose_playstyle(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier = callback.data.split(":")
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_playstyle_prompt_text(game, goal, budget_tier, locale),
            reply_markup=build_playstyle_keyboard(game, goal, budget_tier, locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:playstyle:"))
async def builds_back_to_playstyle(callback: CallbackQuery) -> None:
    _, _, _, game, goal, budget_tier = callback.data.split(":")
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            build_playstyle_prompt_text(game, goal, budget_tier, locale),
            reply_markup=build_playstyle_keyboard(game, goal, budget_tier, locale),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:back:list:"))
async def builds_back_to_list(callback: CallbackQuery) -> None:
    _, _, _, game, goal, budget_tier, playstyle = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
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
                locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:playstyle:"))
async def builds_show_recommendations(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier, playstyle = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
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
                locale,
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("builds:detail:"))
async def builds_show_detail(callback: CallbackQuery) -> None:
    _, _, game, goal, budget_tier, playstyle, index_str = callback.data.split(":")
    recommendations = BuildService().recommend(game=game, goal=goal, budget_tier=budget_tier, playstyle=playstyle)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
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
                locale,
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
    text, keyboard = await load_economy_panel(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    async with session_scope() as session:
        await ensure_user(session, message.from_user.id, message.from_user.username)
    locale = await load_user_locale(message.from_user.id, message.from_user.username, message.from_user.language_code)

    await message.answer(
        f"{tr(locale, 'templates')}:\n{tr(locale, 'friendly_templates_hint')}",
        reply_markup=with_home_button(template_browser_game_keyboard(locale), locale=locale),
    )


@router.callback_query(F.data == "templates:choose_game")
async def templates_choose_game(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.message.edit_text(
        f"{tr(locale, 'templates')}:\n{tr(locale, 'friendly_templates_hint')}",
        reply_markup=with_home_button(template_browser_game_keyboard(locale), locale=locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:game:"))
async def templates_for_game(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]

    async with session_scope() as session:
        goals = TemplateService(session).list_goals()

    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        tr(locale, "templates_for_game", game=game_label),
        reply_markup=template_goal_keyboard(game, goals, locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:goals:"))
async def templates_back_to_goals(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]
    async with session_scope() as session:
        goals = TemplateService(session).list_goals()

    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        tr(locale, "templates_for_game", game=game_label),
        reply_markup=template_goal_keyboard(game, goals, locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:goal:"))
async def templates_for_goal(callback: CallbackQuery) -> None:
    _, _, game, goal_key = callback.data.split(":")

    async with session_scope() as session:
        service = TemplateService(session)
        templates = await service.list_public_for_goal(game, goal_key)
        goal = service.get_goal(goal_key)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not templates:
        await callback.answer(tr(locale, "templates_not_found"), show_alert=True)
        return

    goal_title = goal.title if goal else "Под эту цель"
    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        tr(locale, "templates_for_goal", goal=goal_title, game=game_label),
        reply_markup=templates_keyboard(
            templates,
            game=game,
            back_callback=f"templates:goals:{game}",
            locale=locale,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("templates:all:"))
async def templates_show_all_for_game(callback: CallbackQuery) -> None:
    game = callback.data.rsplit(":", 1)[1]

    async with session_scope() as session:
        templates = await TemplateService(session).list_public_for_game(game)

    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if not templates:
        await callback.answer(tr(locale, "templates_not_found_game"), show_alert=True)
        return

    game_label = "POE 2" if game == "poe2" else "POE 1"
    await callback.message.edit_text(
        tr(locale, "all_templates_for_game", game=game_label),
        reply_markup=templates_keyboard(
            templates,
            game=game,
            back_callback=f"templates:goals:{game}",
            locale=locale,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_select:"))
async def choose_template_from_game_list(callback: CallbackQuery) -> None:
    _, game, template_id_raw = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game, locale),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^template:\d+$"))
async def activate_template(callback: CallbackQuery) -> None:
    template_id = int(callback.data.split(":", 1)[1])

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        tr(locale, "template_game_pick", name=template.name),
        reply_markup=template_game_keyboard(template.id, locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_game:"))
async def choose_template_game(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game, locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_strategy:"))
async def choose_template_strategy(callback: CallbackQuery) -> None:
    _, template_id_raw, game, strategy_key = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        service = TemplateService(session)
        template = await service.get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    strategy, resolved_items = service.resolve_items(template, strategy_key=strategy_key)
    await callback.message.edit_text(
        build_template_preview_text(template, game, strategy, resolved_items),
        reply_markup=template_strategy_keyboard(
            template.id,
            game,
            service.list_strategies(template),
            strategy.key,
            locale,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_strategy_league:"))
async def choose_template_league_for_strategy(callback: CallbackQuery) -> None:
    _, template_id_raw, game, strategy_key = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)
        service = TemplateService(session)
        template = await service.get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    strategy = service.get_strategy(template, strategy_key)
    await callback.message.edit_text(
        tr(locale, "template_strategy_pick", name=template.name, game=("POE 2" if game == "poe2" else "POE 1"), strategy=strategy.title),
        reply_markup=template_league_keyboard(template.id, leagues, game, strategy_key, locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_pick_league:"))
async def choose_template_league_after_preview(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        leagues = await LeagueService(session).list_selection_options(game)
        template = await TemplateService(session).get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        tr(locale, "template_league_pick", name=template.name, game=("POE 2" if game == "poe2" else "POE 1")),
        reply_markup=template_league_keyboard(template.id, leagues, game, "balanced", locale),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_back:"))
async def template_back_to_game(callback: CallbackQuery) -> None:
    _, template_id_raw, game = callback.data.split(":")
    template_id = int(template_id_raw)

    async with session_scope() as session:
        template = await TemplateService(session).get_public_by_id(template_id)
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)

    if not template:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        build_template_preview_text(template, game),
        reply_markup=template_preview_keyboard(template.id, game, locale),
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
        locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
        if not league:
            await callback.answer(tr(locale, "league_not_found"), show_alert=True)
            return

        result = await TemplateService(session).activate(
            user=user,
            template_group_id=template_id,
            league_name=league.name,
            game=league.realm,
            strategy_key=strategy_key,
        )

    if not result:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        build_template_activation_text(result, league),
        reply_markup=menu_section_keyboard(
            (tr(locale, "open_tracking"), "menu:tracking:open"),
            (tr(locale, "home"), "menu:home"),
            include_home=False,
            locale=locale,
        ),
    )
    await callback.answer(tr(locale, "template_connected"))


@router.callback_query(F.data.startswith("template_league:"))
async def activate_template_for_league(callback: CallbackQuery) -> None:
    _, template_id_raw, league_id_raw = callback.data.split(":")
    template_id = int(template_id_raw)
    league_id = int(league_id_raw)

    async with session_scope() as session:
        user = await ensure_user(session, callback.from_user.id, callback.from_user.username)
        league = await LeagueService(session).get_by_id(league_id)
        locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
        if not league:
            await callback.answer(tr(locale, "league_not_found"), show_alert=True)
            return

        result = await TemplateService(session).activate(
            user=user,
            template_group_id=template_id,
            league_name=league.name,
            game=league.realm,
        )

    if not result:
        await callback.answer(tr(locale, "template_not_found"), show_alert=True)
        return

    await callback.message.edit_text(
        build_template_activation_text(result, league),
        reply_markup=menu_section_keyboard(
            (tr(locale, "open_tracking"), "menu:tracking:open"),
            (tr(locale, "home"), "menu:home"),
            include_home=False,
            locale=locale,
        ),
    )
    await callback.answer(tr(locale, "template_connected"))


@router.callback_query(F.data == "template:cancel")
async def cancel_template_activation(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    await callback.message.edit_text(
        tr(locale, "template_cancelled_text"),
        reply_markup=menu_section_keyboard((tr(locale, "home"), "menu:home"), include_home=False, locale=locale),
    )
    await callback.answer(tr(locale, "template_cancelled_short"))


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    locale = await load_user_locale(message.from_user.id, message.from_user.username, message.from_user.language_code)
    text, _ = await load_account_panel(message.from_user.id, message.from_user.username, message.from_user.language_code)
    await message.answer(
        f"{tr(locale, 'settings')}\n"
        f"{tr(locale, 'settings_intro')}\n\n"
        f"{tr(locale, 'current_language', language=LANGUAGE_NAMES[locale])}\n"
        f"{tr(locale, 'settings_default_league')}\n\n"
        f"{text}\n\n"
        f"{tr(locale, 'settings_account_hint')}",
        reply_markup=menu_section_keyboard(
            (tr(locale, "choose_language"), "settings:language_menu"),
            (tr(locale, "settings_open_account"), "menu:account:open"),
            (tr(locale, "settings_open_stash"), "menu:stash:open"),
            locale=locale,
        ),
    )


@router.callback_query(F.data == "settings:language_menu")
async def settings_language_menu(callback: CallbackQuery) -> None:
    locale = await load_user_locale(callback.from_user.id, callback.from_user.username, callback.from_user.language_code)
    if callback.message:
        await callback.message.edit_text(
            f"{tr(locale, 'language_settings_title')}\n\n{tr(locale, 'language_settings_hint')}",
            reply_markup=language_keyboard(locale, back_callback="menu:home"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:language:"))
async def settings_change_language(callback: CallbackQuery) -> None:
    locale = normalize_locale(callback.data.rsplit(":", 1)[1])
    async with session_scope() as session:
        await ensure_user(session, callback.from_user.id, callback.from_user.username)
        await UserService(session).set_language(callback.from_user.id, locale)
    if callback.message:
        await callback.message.edit_text(
            f"{tr(locale, 'language_changed_text', language=LANGUAGE_NAMES[locale])}\n\n{tr(locale, 'settings_saved_hint')}",
            reply_markup=home_menu_keyboard(locale),
        )
    await callback.answer(tr(locale, "language_saved"))
