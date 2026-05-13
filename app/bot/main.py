import asyncio
import logging
import os
import socket

from aiohttp import ThreadedResolver
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, MenuButtonCommands

from app.bot.handlers import router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.runtime.healthcheck import start_healthcheck_server

logger = logging.getLogger(__name__)


async def configure_bot_menu(bot: Bot) -> None:
    commands = [
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
    ]
    await bot.set_my_commands(commands)
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
