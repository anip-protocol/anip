"""Quick integration test — verify the bridge discovers and translates correctly."""

import asyncio
import sys

from anip_mcp_bridge.discovery import discover_service
from anip_mcp_bridge.invocation import ANIPInvoker
from anip_mcp_bridge.translation import capability_to_input_schema, enrich_description


async def test_bridge(url: str):
    print(f"Testing bridge against {url}\n")

    # 1. Discovery
    print("1. Discovering service...")
    service = await discover_service(url)
    print(f"   Protocol: {service.protocol}")
    print(f"   Compliance: {service.compliance}")
    print(f"   Capabilities: {list(service.capabilities.keys())}")

    # 2. Translation
    print("\n2. Translating capabilities to MCP tools...")
    for name, cap in service.capabilities.items():
        schema = capability_to_input_schema(cap)
        desc = enrich_description(cap)
        print(f"\n   Tool: {name}")
        print(f"   Description: {desc}")
        print(f"   Input schema properties: {list(schema.get('properties', {}).keys())}")
        print(f"   Required: {schema.get('required', [])}")

    # 3. Invocation
    print("\n3. Testing invocation...")
    invoker = ANIPInvoker(
        service=service,
        scope=["travel.search", "travel.book:max_$500"],
        api_key="demo-human-key",
    )
    print("   Invoker ready")

    # Search flights
    result = await invoker.invoke("search_flights", {
        "origin": "SEA",
        "destination": "SFO",
        "date": "2026-03-10",
    })
    print(f"\n   search_flights result:\n   {result[:200]}...")

    # Book flight
    result = await invoker.invoke("book_flight", {
        "flight_number": "AA100",
        "date": "2026-03-10",
        "passengers": 1,
    })
    print(f"\n   book_flight result:\n   {result[:300]}")

    print("\n--- All tests passed ---")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_bridge(url))
