"""Generated ANIP stdio entrypoint."""
from __future__ import annotations

import asyncio

from anip_stdio import serve_stdio

from .app import create_service


async def main() -> None:
    await serve_stdio(create_service())


if __name__ == '__main__':
    asyncio.run(main())
