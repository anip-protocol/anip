"""Newline-delimited JSON framing for ANIP stdio transport."""
import json
import asyncio
from typing import Any


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    """Read one newline-delimited JSON message. Returns None on EOF."""
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.strip())


async def write_message(writer: asyncio.StreamWriter, message: dict[str, Any]) -> None:
    """Write one newline-delimited JSON message."""
    data = json.dumps(message, separators=(",", ":")) + "\n"
    writer.write(data.encode())
    await writer.drain()
