import asyncio
import logging
import os

from aiogram import Bot

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import async_session_factory
from app.integrations.source_registry import TrackingSourceRegistry
from app.runtime.healthcheck import start_healthcheck_server
from app.services.telegram_notifier import TelegramNotifier
from app.workers.tracking_worker import TrackingWorker

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_settings()
    bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
    notifier = TelegramNotifier(bot) if bot else None
    port = int(os.getenv("PORT", "8080"))
    health_server = await start_healthcheck_server("worker", port)

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
        health_server.close()
        await health_server.wait_closed()
        if bot:
            await bot.session.close()
        logger.info("Tracking worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
