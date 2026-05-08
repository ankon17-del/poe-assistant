import asyncio
import logging

from aiogram import Bot

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.integrations.source_registry import TrackingSourceRegistry
from app.services.telegram_notifier import TelegramNotifier
from app.workers.tracking_worker import TrackingWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
    notifier = TelegramNotifier(bot) if bot else None

    try:
        while True:
            async with async_session_factory() as session:
                worker = TrackingWorker(
                    session=session,
                    source_registry=TrackingSourceRegistry(),
                    notifier=notifier,
                )
                await worker.run_once()
                await session.commit()

            await asyncio.sleep(settings.tracking_poll_interval_seconds)
    finally:
        if bot:
            await bot.session.close()
        logger.info("Tracking worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
