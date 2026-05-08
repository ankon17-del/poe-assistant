import logging

from aiogram import Bot

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_sale_notification(self, telegram_id: int, message: str) -> None:
        try:
            await self.bot.send_message(chat_id=telegram_id, text=message)
        except Exception:
            logger.exception("Failed to send Telegram notification to %s", telegram_id)
