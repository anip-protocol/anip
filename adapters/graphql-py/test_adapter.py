"""Integration tests for the ANIP GraphQL adapter.

Usage:
    python test_adapter.py http://localhost:9100
"""

from __future__ import annotations

import asyncio
import sys

import httpx

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

_pass_count = 0
_fail_count = 0


def _ok(label: str) -> None:
    global _pass_count
    _pass_count += 1
    print(f"  PASS  {label}")


def _fail(label: str, detail: str = "") -> None:
    global _fail_count
    _fail_count += 1
    msg = f"  FAIL  {label}"
    if detail:
        msg += f"  — {detail}"
    print(msg)


def _assert(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        _ok(label)
    else:
        _fail(label, detail)


# ---------------------------------------------------------------------------
# 1. Config defaults
# ---------------------------------------------------------------------------

def test_config_defaults() -> None:
    print("\n--- Config defaults ---")
    from anip_graphql_adapter.config import AdapterConfig

    cfg = AdapterConfig()
    _assert(cfg.anip_service_url == "http://localhost:8000", "default service URL")
    _assert(cfg.port == 3002, "default port")
    _assert(cfg.graphql.path == "/graphql", "default graphql path")
    _assert(cfg.graphql.playground is True, "default playground enabled")
    _assert(cfg.graphql.introspection is True, "default introspection enabled")


# ---------------------------------------------------------------------------
# 2. Discovery
# ---------------------------------------------------------------------------

async def test_discovery(anip_url: str) -> None:
    print("\n--- Discovery ---")
    from anip_graphql_adapter.discovery import discover_service

    service = await discover_service(anip_url)
    _assert(service.base_url != "", "base_url populated")
    _assert(service.protocol != "", "protocol populated")
    _assert(len(service.capabilities) > 0, "capabilities discovered")
    _assert("search_flights" in service.capabilities, "search_flights found")
    _assert("book_flight" in service.capabilities, "book_flight found")

    sf = service.capabilities["search_flights"]
    _assert(sf.side_effect == "read", "search_flights is read")
    _assert(sf.financial is False, "search_flights not financial")

    bf = service.capabilities["book_flight"]
    _assert(bf.side_effect in ("write", "irreversible"), "book_flight has side effect")
    _assert(bf.financial is True, "book_flight is financial")
    _assert(len(bf.requires) > 0, "book_flight has prerequisites")


# ---------------------------------------------------------------------------
# 3. Schema generation
# ---------------------------------------------------------------------------

async def test_schema_generation(anip_url: str) -> None:
    print("\n--- Schema generation ---")
    from anip_graphql_adapter.discovery import discover_service
    from anip_graphql_adapter.translation import generate_schema

    service = await discover_service(anip_url)
    sdl = generate_schema(service)

    # Directives present
    _assert("directive @anipSideEffect" in sdl, "SDL has @anipSideEffect directive")
    _assert("directive @anipCost" in sdl, "SDL has @anipCost directive")
    _assert("directive @anipRequires" in sdl, "SDL has @anipRequires directive")
    _assert("directive @anipScope" in sdl, "SDL has @anipScope directive")

    # Shared types
    _assert("scalar JSON" in sdl, "SDL has JSON scalar")
    _assert("type CostActual" in sdl, "SDL has CostActual type")
    _assert("type ANIPFailure" in sdl, "SDL has ANIPFailure type")
    _assert("type Resolution" in sdl, "SDL has Resolution type")

    # Query and Mutation
    _assert("type Query" in sdl, "SDL has Query type")
    _assert("type Mutation" in sdl, "SDL has Mutation type")

    # camelCase names
    _assert("searchFlights" in sdl, "SDL uses camelCase searchFlights")
    _assert("bookFlight" in sdl, "SDL uses camelCase bookFlight")

    # Result types (PascalCase)
    _assert("SearchFlightsResult" in sdl, "SDL has SearchFlightsResult type")
    _assert("BookFlightResult" in sdl, "SDL has BookFlightResult type")

    # searchFlights is in Query (read), bookFlight is in Mutation
    # Find the Query block and check searchFlights is there
    query_block = sdl[sdl.index("type Query"):sdl.index("}", sdl.index("type Query")) + 1]
    _assert("searchFlights" in query_block, "searchFlights is in Query type")

    mutation_block = sdl[sdl.index("type Mutation"):sdl.index("}", sdl.index("type Mutation")) + 1]
    _assert("bookFlight" in mutation_block, "bookFlight is in Mutation type")

    # Directives applied to fields
    _assert("@anipSideEffect" in sdl.split("type Query")[1], "fields have @anipSideEffect")


# ---------------------------------------------------------------------------
# 4. Full server (httpx ASGITransport)
# ---------------------------------------------------------------------------

async def test_server(anip_url: str) -> None:
    print("\n--- Server (ASGI) ---")
    from anip_graphql_adapter.config import AdapterConfig
    from anip_graphql_adapter.server import build_app

    config = AdapterConfig(anip_service_url=anip_url)
    app = await build_app(config)

    # Pre-issue a signed token outside the ASGI transport block
    from anip_graphql_adapter.discovery import discover_service

    service = await discover_service(anip_url)
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            service.endpoints["tokens"],
            json={
                "subject": "adapter:anip-graphql-adapter",
                "scope": ["*"],
                "capability": "search_flights",
            },
            headers={"Authorization": "Bearer demo-human-key"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        signed_token = token_data["token"]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /schema.graphql returns SDL
        resp = await client.get("/schema.graphql")
        _assert(resp.status_code == 200, "GET /schema.graphql returns 200")
        sdl = resp.text
        _assert("type Query" in sdl, "schema.graphql contains Query type")
        _assert("directive @anipSideEffect" in sdl, "schema.graphql has directives")

        # Missing credentials test: POST /graphql without auth headers
        resp = await client.post(
            "/graphql/",
            json={
                "query": """
                    query {
                        searchFlights(
                            origin: "SEA"
                            destination: "SFO"
                            date: "2026-03-10"
                        ) {
                            success
                            result
                            failure {
                                type
                                detail
                            }
                        }
                    }
                """,
            },
        )
        _assert(resp.status_code == 200, "POST /graphql without creds returns 200 (GraphQL layer)")
        data = resp.json()
        search_data = data.get("data", {}).get("searchFlights", {})
        _assert(search_data.get("success") is False, "no-creds searchFlights success is false")
        _assert(
            search_data.get("failure", {}).get("type") == "missing_credentials",
            f"no-creds failure type is missing_credentials: {search_data.get('failure')}",
        )

        # API-key path: POST /graphql with X-ANIP-API-Key header
        resp = await client.post(
            "/graphql/",
            json={
                "query": """
                    query {
                        searchFlights(
                            origin: "SEA"
                            destination: "SFO"
                            date: "2026-03-10"
                        ) {
                            success
                            result
                        }
                    }
                """,
            },
            headers={"X-ANIP-API-Key": "demo-human-key"},
        )
        _assert(resp.status_code == 200, "POST /graphql searchFlights with API key returns 200")
        data = resp.json()
        _assert("errors" not in data or data["errors"] is None,
                f"searchFlights has no errors (api-key): {data.get('errors')}")
        search_data = data.get("data", {}).get("searchFlights", {})
        _assert(search_data.get("success") is True, "searchFlights success is true (api-key)")
        _assert(search_data.get("result") is not None, "searchFlights has result (api-key)")

        # Token path: POST /graphql with X-ANIP-Token header
        resp = await client.post(
            "/graphql/",
            json={
                "query": """
                    query {
                        searchFlights(
                            origin: "SEA"
                            destination: "SFO"
                            date: "2026-03-10"
                        ) {
                            success
                            result
                        }
                    }
                """,
            },
            headers={"X-ANIP-Token": signed_token},
        )
        _assert(resp.status_code == 200, "POST /graphql searchFlights with token returns 200")
        data = resp.json()
        _assert("errors" not in data or data["errors"] is None,
                f"searchFlights has no errors (token): {data.get('errors')}")
        search_data = data.get("data", {}).get("searchFlights", {})
        _assert(search_data.get("success") is True, "searchFlights success is true (token)")

        # POST /graphql with mutation { bookFlight(...) { success result costActual { ... } } }
        resp = await client.post(
            "/graphql/",
            json={
                "query": """
                    mutation {
                        bookFlight(
                            flightNumber: "AA100"
                            date: "2026-03-10"
                            passengers: 1
                        ) {
                            success
                            result
                            costActual {
                                financial {
                                    amount
                                    currency
                                }
                                varianceFromEstimate
                            }
                        }
                    }
                """,
            },
            headers={"X-ANIP-API-Key": "demo-human-key"},
        )
        _assert(resp.status_code == 200, "POST /graphql bookFlight returns 200")
        data = resp.json()
        _assert("errors" not in data or data["errors"] is None,
                f"bookFlight has no errors: {data.get('errors')}")
        book_data = data.get("data", {}).get("bookFlight", {})
        _assert("success" in book_data, "bookFlight has success key")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_adapter.py <anip-service-url>")
        print("Example: python test_adapter.py http://localhost:9100")
        sys.exit(1)

    anip_url = sys.argv[1]
    print(f"Testing ANIP GraphQL adapter against {anip_url}")

    # 1. Config (sync)
    test_config_defaults()

    # 2-4. Async tests
    asyncio.run(_run_async_tests(anip_url))

    # Summary
    print(f"\n{'='*50}")
    print(f"Results: {_pass_count} passed, {_fail_count} failed")
    if _fail_count > 0:
        sys.exit(1)
    print("All tests passed!")


async def _run_async_tests(anip_url: str) -> None:
    await test_discovery(anip_url)
    await test_schema_generation(anip_url)
    await test_server(anip_url)


if __name__ == "__main__":
    main()
