import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


async def run_bot() -> None:
    setup_logging()
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    logger.info("Starting Telegram bot polling")
    await dispatcher.start_polling(bot)

