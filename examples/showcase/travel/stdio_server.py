#!/usr/bin/env python3
"""Run the travel showcase service in ANIP stdio mode.

Usage:
    python stdio_server.py

    # Or from an agent:
    echo '{"jsonrpc":"2.0","id":1,"method":"anip.discovery","params":{}}' | python stdio_server.py
"""
import asyncio
import os
import sys

# Add the showcase dir to path so capabilities can be imported
sys.path.insert(0, os.path.dirname(__file__))

from anip_service import ANIPService  # noqa: E402
from anip_stdio import serve_stdio  # noqa: E402
from capabilities import search_flights, check_availability, book_flight, cancel_booking  # noqa: E402

API_KEYS = {
    "demo-human-key": "human:samir@example.com",
    "demo-agent-key": "agent:demo-agent",
}

service = ANIPService(
    service_id="anip-travel-showcase",
    capabilities=[search_flights, check_availability, book_flight, cancel_booking],
    storage=os.getenv("ANIP_STORAGE", ":memory:"),
    trust=os.getenv("ANIP_TRUST_LEVEL", "signed"),
    key_path=os.getenv("ANIP_KEY_PATH", "./anip-keys"),
    authenticate=lambda bearer: API_KEYS.get(bearer),
)

asyncio.run(serve_stdio(service))
