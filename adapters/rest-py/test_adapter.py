"""Integration tests for the ANIP REST adapter.

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
    from anip_rest_adapter.config import AdapterConfig, load_config

    cfg = AdapterConfig()
    _assert(cfg.anip_service_url == "http://localhost:8000", "default service URL")
    _assert(cfg.port == 3001, "default port")
    _assert(cfg.routes == {}, "default routes empty")


# ---------------------------------------------------------------------------
# 2. Discovery
# ---------------------------------------------------------------------------

async def test_discovery(anip_url: str) -> None:
    print("\n--- Discovery ---")
    from anip_rest_adapter.discovery import discover_service

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
# 3. Invocation
# ---------------------------------------------------------------------------

async def test_invocation(anip_url: str) -> None:
    print("\n--- Invocation ---")
    from anip_rest_adapter.discovery import discover_service
    from anip_rest_adapter.invocation import ANIPInvoker, CredentialError

    service = await discover_service(anip_url)
    invoker = ANIPInvoker(service=service)

    # API-key path: search flights
    result = await invoker.invoke(
        "search_flights",
        {
            "origin": "SEA",
            "destination": "SFO",
            "date": "2026-03-10",
            "passengers": 1,
        },
        api_key="demo-human-key",
    )
    _assert(isinstance(result, dict), "search_flights returns dict")
    _assert(result.get("success") is True, "search_flights succeeds")
    _assert("result" in result, "search_flights has result")

    # API-key path: book flight
    result = await invoker.invoke(
        "book_flight",
        {
            "flight_number": "AA100",
            "date": "2026-03-10",
            "passengers": 1,
        },
        api_key="demo-human-key",
    )
    _assert(isinstance(result, dict), "book_flight returns dict")
    _assert("success" in result, "book_flight has success key")

    # Token path: pre-issue a token, then invoke with it
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            service.endpoints["tokens"],
            json={
                "subject": "adapter:anip-rest-adapter",
                "scope": ["*"],
                "capability": "search_flights",
            },
            headers={"Authorization": "Bearer demo-human-key"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        _assert(token_data.get("issued") is True, "token issued for token-path test")
        jwt_str = token_data["token"]

    result = await invoker.invoke(
        "search_flights",
        {
            "origin": "SEA",
            "destination": "SFO",
            "date": "2026-03-10",
            "passengers": 1,
        },
        token=jwt_str,
    )
    _assert(isinstance(result, dict), "token-path search_flights returns dict")
    _assert(result.get("success") is True, "token-path search_flights succeeds")

    # No credentials raises CredentialError
    try:
        await invoker.invoke(
            "search_flights",
            {"origin": "SEA", "destination": "SFO", "date": "2026-03-10", "passengers": 1},
        )
        _fail("no-creds raises CredentialError", "no exception raised")
    except CredentialError:
        _ok("no-creds raises CredentialError")
    except Exception as e:
        _fail("no-creds raises CredentialError", f"wrong exception: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 4. Translation
# ---------------------------------------------------------------------------

async def test_translation(anip_url: str) -> None:
    print("\n--- Translation ---")
    from anip_rest_adapter.discovery import discover_service
    from anip_rest_adapter.translation import generate_openapi_spec, generate_routes

    service = await discover_service(anip_url)

    # Route generation
    routes = generate_routes(service)
    _assert("search_flights" in routes, "search_flights route generated")
    _assert("book_flight" in routes, "book_flight route generated")

    sf_route = routes["search_flights"]
    _assert(sf_route.method == "GET", "search_flights is GET (read)")
    _assert(sf_route.path == "/api/search_flights", "search_flights default path")

    bf_route = routes["book_flight"]
    _assert(bf_route.method == "POST", "book_flight is POST (write)")
    _assert(bf_route.path == "/api/book_flight", "book_flight default path")

    # OpenAPI spec
    spec = generate_openapi_spec(service, routes)
    _assert(spec["openapi"] == "3.1.0", "OpenAPI 3.1.0")
    _assert("/api/search_flights" in spec["paths"], "spec has search_flights path")
    _assert("/api/book_flight" in spec["paths"], "spec has book_flight path")

    sf_op = spec["paths"]["/api/search_flights"]["get"]
    _assert("x-anip-side-effect" in sf_op, "search_flights has x-anip-side-effect")
    _assert(sf_op["x-anip-side-effect"] == "read", "x-anip-side-effect is read")
    _assert("x-anip-financial" in sf_op, "search_flights has x-anip-financial")
    _assert(sf_op["x-anip-financial"] is False, "x-anip-financial is False")
    _assert("x-anip-minimum-scope" in sf_op, "has x-anip-minimum-scope")
    _assert("x-anip-contract-version" in sf_op, "has x-anip-contract-version")
    _assert("parameters" in sf_op, "GET has query parameters")

    bf_op = spec["paths"]["/api/book_flight"]["post"]
    _assert(bf_op["x-anip-financial"] is True, "book_flight x-anip-financial is True")
    _assert("x-anip-requires" in bf_op, "book_flight has x-anip-requires")
    _assert("requestBody" in bf_op, "POST has requestBody")

    # ANIPResponse schema
    _assert("ANIPResponse" in spec["components"]["schemas"], "ANIPResponse schema present")

    # Route overrides
    from anip_rest_adapter.config import RouteOverride

    overrides = {
        "search_flights": RouteOverride(path="/api/flights/search", method="GET"),
    }
    routes2 = generate_routes(service, overrides)
    _assert(
        routes2["search_flights"].path == "/api/flights/search",
        "route override path applied",
    )


# ---------------------------------------------------------------------------
# 5. Full server (httpx ASGITransport)
# ---------------------------------------------------------------------------

async def test_server(anip_url: str) -> None:
    print("\n--- Server (ASGI) ---")
    from anip_rest_adapter.config import AdapterConfig
    from anip_rest_adapter.server import build_app

    config = AdapterConfig(anip_service_url=anip_url)
    app = await build_app(config)

    # Pre-issue a signed token outside the ASGI transport block
    from anip_rest_adapter.discovery import discover_service

    service = await discover_service(anip_url)
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            service.endpoints["tokens"],
            json={
                "subject": "adapter:anip-rest-adapter",
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
        # OpenAPI spec endpoint
        resp = await client.get("/openapi.json")
        _assert(resp.status_code == 200, "GET /openapi.json returns 200")
        spec = resp.json()
        _assert(spec["openapi"] == "3.1.0", "served spec is 3.1.0")
        _assert("/api/search_flights" in spec["paths"], "spec paths include search_flights")

        # 401 test: no credentials
        resp = await client.get(
            "/api/search_flights",
            params={
                "origin": "SEA",
                "destination": "SFO",
                "date": "2026-03-10",
                "passengers": "1",
            },
        )
        _assert(resp.status_code == 401, "GET without credentials returns 401")

        # API-key path: GET search_flights
        resp = await client.get(
            "/api/search_flights",
            params={
                "origin": "SEA",
                "destination": "SFO",
                "date": "2026-03-10",
                "passengers": "1",
            },
            headers={"X-ANIP-API-Key": "demo-human-key"},
        )
        _assert(resp.status_code == 200, "GET /api/search_flights with API key returns 200")
        data = resp.json()
        _assert(data.get("success") is True, "search_flights response success (api-key)")
        _assert("result" in data, "search_flights response has result (api-key)")

        # Token path: GET search_flights
        resp = await client.get(
            "/api/search_flights",
            params={
                "origin": "SEA",
                "destination": "SFO",
                "date": "2026-03-10",
                "passengers": "1",
            },
            headers={"X-ANIP-Token": signed_token},
        )
        _assert(resp.status_code == 200, "GET /api/search_flights with token returns 200")
        data = resp.json()
        _assert(data.get("success") is True, "search_flights response success (token)")

        # POST book_flight with API key — first search for a real flight
        search_resp = await client.get(
            "/api/search_flights",
            params={
                "origin": "SEA",
                "destination": "SFO",
                "date": "2026-03-10",
                "passengers": "1",
            },
            headers={"X-ANIP-API-Key": "demo-human-key"},
        )
        flights = search_resp.json().get("result", {}).get("flights", [])
        flight_number = flights[0]["flight_number"] if flights else "UA100"

        resp = await client.post(
            "/api/book_flight",
            json={
                "flight_number": flight_number,
                "date": "2026-03-10",
                "passengers": 1,
            },
            headers={"X-ANIP-API-Key": "demo-human-key"},
        )
        _assert(resp.status_code == 200, "POST /api/book_flight returns 200")
        data = resp.json()
        _assert("success" in data, "book_flight response has success key")

        # Docs endpoint is available
        resp = await client.get("/docs")
        _assert(resp.status_code == 200, "GET /docs returns 200")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_adapter.py <anip-service-url>")
        print("Example: python test_adapter.py http://localhost:9100")
        sys.exit(1)

    anip_url = sys.argv[1]
    print(f"Testing ANIP REST adapter against {anip_url}")

    # 1. Config (sync)
    test_config_defaults()

    # 2-5. Async tests
    asyncio.run(_run_async_tests(anip_url))

    # Summary
    print(f"\n{'='*50}")
    print(f"Results: {_pass_count} passed, {_fail_count} failed")
    if _fail_count > 0:
        sys.exit(1)
    print("All tests passed!")


async def _run_async_tests(anip_url: str) -> None:
    await test_discovery(anip_url)
    await test_invocation(anip_url)
    await test_translation(anip_url)
    await test_server(anip_url)


if __name__ == "__main__":
    main()
