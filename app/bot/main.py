import asyncio
import logging
import os
import socket

from aiohttp import ThreadedResolver
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, MenuButtonCommands

from app.bot.handlers import router
from app.bot.i18n import SUPPORTED_LOCALES
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.runtime.healthcheck import start_healthcheck_server

logger = logging.getLogger(__name__)


def _command_sets() -> dict[str, list[BotCommand]]:
    return {
        "ru": [
            BotCommand(command="menu", description="Главное меню"),
            BotCommand(command="add", description="Добавить трекинг"),
            BotCommand(command="templates", description="Готовые шаблоны"),
            BotCommand(command="economy", description="Экономика и alerts"),
            BotCommand(command="builds", description="Подобрать билд"),
            BotCommand(command="list", description="Активный трекинг"),
            BotCommand(command="alerts", description="Сработавшие alerts"),
            BotCommand(command="account", description="PoE аккаунт"),
            BotCommand(command="stash", description="Тайник"),
            BotCommand(command="help", description="Помощь"),
            BotCommand(command="settings", description="Настройки"),
        ],
        "en": [
            BotCommand(command="menu", description="Main menu"),
            BotCommand(command="add", description="Add tracking"),
            BotCommand(command="templates", description="Ready-made templates"),
            BotCommand(command="economy", description="Economy and alerts"),
            BotCommand(command="builds", description="Find a build"),
            BotCommand(command="list", description="Active tracking"),
            BotCommand(command="alerts", description="Triggered alerts"),
            BotCommand(command="account", description="PoE account"),
            BotCommand(command="stash", description="Stash panel"),
            BotCommand(command="help", description="Help"),
            BotCommand(command="settings", description="Settings"),
        ],
        "fr": [
            BotCommand(command="menu", description="Menu principal"),
            BotCommand(command="add", description="Ajouter un suivi"),
            BotCommand(command="templates", description="Templates prêts"),
            BotCommand(command="economy", description="Économie et alertes"),
            BotCommand(command="builds", description="Choisir un build"),
            BotCommand(command="list", description="Suivi actif"),
            BotCommand(command="alerts", description="Alertes déclenchées"),
            BotCommand(command="account", description="Compte PoE"),
            BotCommand(command="stash", description="Panneau coffre"),
            BotCommand(command="help", description="Aide"),
            BotCommand(command="settings", description="Paramètres"),
        ],
        "de": [
            BotCommand(command="menu", description="Hauptmenü"),
            BotCommand(command="add", description="Tracking hinzufügen"),
            BotCommand(command="templates", description="Fertige Templates"),
            BotCommand(command="economy", description="Ökonomie und Alerts"),
            BotCommand(command="builds", description="Build finden"),
            BotCommand(command="list", description="Aktives Tracking"),
            BotCommand(command="alerts", description="Ausgelöste Alerts"),
            BotCommand(command="account", description="PoE-Konto"),
            BotCommand(command="stash", description="Stash-Panel"),
            BotCommand(command="help", description="Hilfe"),
            BotCommand(command="settings", description="Einstellungen"),
        ],
    }


async def configure_bot_menu(bot: Bot) -> None:
    command_sets = _command_sets()
    await bot.set_my_commands(command_sets["ru"])
    for locale in SUPPORTED_LOCALES:
        await bot.set_my_commands(command_sets[locale], language_code=locale)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def run_bot() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    session = AiohttpSession()
    session._connector_init["resolver"] = ThreadedResolver()
    session._connector_init["family"] = socket.AF_INET

    bot = Bot(token=settings.telegram_bot_token, session=session)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await configure_bot_menu(bot)
    port = int(os.getenv("PORT", "8080"))
    health_server = await start_healthcheck_server("bot", port)

    logger.info("Starting Telegram bot polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        health_server.close()
        await health_server.wait_closed()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
