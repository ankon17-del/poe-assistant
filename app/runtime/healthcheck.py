from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def _healthcheck_handler(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    *,
    service_name: str,
) -> None:
    try:
        request_line = await reader.readline()
        path = "/"
        if request_line:
            parts = request_line.decode("ascii", errors="ignore").split()
            if len(parts) >= 2:
                path = parts[1]

        while True:
            line = await reader.readline()
            if not line or line in {b"\r\n", b"\n"}:
                break

        if path == "/health":
            body = f'{{"status":"ok","service":"{service_name}"}}'.encode("ascii")
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


async def start_healthcheck_server(service_name: str, port: int) -> asyncio.AbstractServer:
    server = await asyncio.start_server(
        lambda reader, writer: _healthcheck_handler(reader, writer, service_name=service_name),
        "0.0.0.0",
        port,
    )
    logger.info("%s healthcheck server listening on port %s", service_name.capitalize(), port)
    return server
