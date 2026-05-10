import asyncio
import logging
import os
import socket

from aiohttp import ThreadedResolver
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from app.bot.handlers import router
from app.core.config import get_settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


async def _healthcheck_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        request_line = await reader.readline()
        path = "/"
        if request_line:
            parts = request_line.decode("ascii", errors="ignore").split()
            if len(parts) >= 2:
                path = parts[1]

        # Drain the remaining headers.
        while True:
            line = await reader.readline()
            if not line or line in {b"\r\n", b"\n"}:
                break

        if path == "/health":
            body = b'{"status":"ok","service":"bot"}'
            status = b"200 OK"
        else:
            body = b"not found"
            status = b"404 Not Found"

        response = (
            b"HTTP/1.1 "
            + status
            + b"\r\nContent-Type: application/json\r\nContent-Length: "
            + str(len(body)).encode("ascii")
            + b"\r\nConnection: close\r\n\r\n"
            + body
        )
        writer.write(response)
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


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
    port = int(os.getenv("PORT", "8080"))
    health_server = await asyncio.start_server(_healthcheck_handler, "0.0.0.0", port)

    logger.info("Bot healthcheck server listening on port %s", port)
    logger.info("Starting Telegram bot polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        health_server.close()
        await health_server.wait_closed()
