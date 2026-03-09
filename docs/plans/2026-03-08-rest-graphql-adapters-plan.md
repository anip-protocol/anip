# REST/OpenAPI & GraphQL Adapters — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build 4 adapters (rest-py, rest-ts, graphql-py, graphql-ts) that auto-discover any ANIP service and expose it through standard REST/OpenAPI and GraphQL surfaces.

**Architecture:** Each adapter follows the same 3-stage pattern as MCP adapters: discover → translate → serve. Discovery and invocation modules are reused from MCP adapters' proven patterns. Translation modules convert ANIP capabilities into REST routes + OpenAPI spec or GraphQL schema + resolvers.

**Tech Stack:**
- Python REST: FastAPI (auto-generates OpenAPI), httpx, pyyaml
- TypeScript REST: Hono, openapi3-ts, @hono/swagger-ui
- Python GraphQL: FastAPI, ariadne, httpx, pyyaml
- TypeScript GraphQL: Hono, graphql (graphql-js), @hono/graphql-server

---

## Phase 1: REST Python Adapter (`adapters/rest-py/`)

### Task 1: Project scaffolding

**Files:**
- Create: `adapters/rest-py/pyproject.toml`
- Create: `adapters/rest-py/anip_rest_adapter/__init__.py`
- Create: `adapters/rest-py/adapter.example.yaml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-rest-adapter"
version = "0.1.0"
description = "Generic REST/OpenAPI adapter for any ANIP-compliant service"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
]

[project.scripts]
anip-rest-adapter = "anip_rest_adapter.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 2: Create __init__.py**

```python
```

(Empty file — package marker only.)

**Step 3: Create adapter.example.yaml**

```yaml
anip_service_url: "http://localhost:8000"
port: 3001

delegation:
  issuer: "human:user@example.com"
  scope: ["travel.search", "travel.book:max_$500"]
  token_ttl_minutes: 60

# Optional: override default ANIP-style routes
routes:
  search_flights:
    path: "/flights/search"
    method: "GET"
  book_flight:
    path: "/flights/book"
    method: "POST"
```

**Step 4: Commit**

```bash
git add adapters/rest-py/pyproject.toml adapters/rest-py/anip_rest_adapter/__init__.py adapters/rest-py/adapter.example.yaml
git commit -m "feat(rest-py): scaffold REST adapter project"
```

---

### Task 2: Config module

**Files:**
- Create: `adapters/rest-py/anip_rest_adapter/config.py`
- Create: `adapters/rest-py/test_adapter.py` (start test file)

**Step 1: Write the failing test**

Add to `adapters/rest-py/test_adapter.py`:

```python
"""Integration tests for the REST adapter."""

import asyncio
import sys


async def test_config():
    from anip_rest_adapter.config import load_config

    config = load_config()
    assert config.anip_service_url == "http://localhost:8000"
    assert config.port == 3001
    assert config.delegation.issuer == "human:user@example.com"
    print("   Config: defaults loaded correctly")

    print("1. Config tests passed")


if __name__ == "__main__":
    asyncio.run(test_config())
```

**Step 2: Run test to verify it fails**

Run: `cd adapters/rest-py && pip install -e . && python test_adapter.py`
Expected: FAIL with "ModuleNotFoundError: No module named 'anip_rest_adapter.config'"

**Step 3: Write the config module**

Create `adapters/rest-py/anip_rest_adapter/config.py`:

```python
"""Adapter configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DelegationConfig:
    """Delegation token configuration."""

    issuer: str = "human:user@example.com"
    scope: list[str] = field(default_factory=lambda: ["*"])
    token_ttl_minutes: int = 60


@dataclass
class RouteOverride:
    """Custom route for a capability."""

    path: str
    method: str  # "GET" or "POST"


@dataclass
class AdapterConfig:
    """Full REST adapter configuration."""

    anip_service_url: str = "http://localhost:8000"
    port: int = 3001
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    routes: dict[str, RouteOverride] = field(default_factory=dict)


def load_config(config_path: str | None = None) -> AdapterConfig:
    """Load config from YAML file or environment variables.

    Priority: explicit path > ANIP_ADAPTER_CONFIG env var > ./adapter.yaml > defaults
    """
    if config_path is None:
        config_path = os.environ.get("ANIP_ADAPTER_CONFIG")
    if config_path is None:
        default_path = Path("adapter.yaml")
        if default_path.exists():
            config_path = str(default_path)

    if config_path is None:
        return AdapterConfig(
            anip_service_url=os.environ.get(
                "ANIP_SERVICE_URL", "http://localhost:8000"
            ),
            port=int(os.environ.get("ANIP_ADAPTER_PORT", "3001")),
            delegation=DelegationConfig(
                issuer=os.environ.get("ANIP_ISSUER", "human:user@example.com"),
                scope=os.environ.get("ANIP_SCOPE", "*").split(","),
            ),
        )

    with open(config_path) as f:
        data = yaml.safe_load(f)

    delegation_data = data.get("delegation", {})
    delegation = DelegationConfig(
        issuer=delegation_data.get("issuer", "human:user@example.com"),
        scope=delegation_data.get("scope", ["*"]),
        token_ttl_minutes=delegation_data.get("token_ttl_minutes", 60),
    )

    routes = {}
    for cap_name, route_data in data.get("routes", {}).items():
        routes[cap_name] = RouteOverride(
            path=route_data["path"],
            method=route_data.get("method", "POST").upper(),
        )

    return AdapterConfig(
        anip_service_url=data.get("anip_service_url", "http://localhost:8000"),
        port=data.get("port", 3001),
        delegation=delegation,
        routes=routes,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd adapters/rest-py && pip install -e . && python test_adapter.py`
Expected: "1. Config tests passed"

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/config.py adapters/rest-py/test_adapter.py
git commit -m "feat(rest-py): add config module with YAML + env support"
```

---

### Task 3: Discovery module (reuse MCP pattern)

**Files:**
- Create: `adapters/rest-py/anip_rest_adapter/discovery.py`

**Step 1: Write the failing test**

Append to `adapters/rest-py/test_adapter.py`:

```python
async def test_discovery(url: str):
    from anip_rest_adapter.discovery import discover_service

    service = await discover_service(url)
    assert service.protocol == "ANIP/0.1"
    assert len(service.capabilities) >= 2
    assert "search_flights" in service.capabilities
    assert "book_flight" in service.capabilities

    cap = service.capabilities["search_flights"]
    assert cap.side_effect == "read"
    assert cap.minimum_scope == ["travel.search"]

    print(f"   Discovered {len(service.capabilities)} capabilities")
    print("2. Discovery tests passed")
```

Update `__main__`:

```python
if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_config())
    asyncio.run(test_discovery(url))
```

**Step 2: Run test to verify it fails**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: FAIL with "ModuleNotFoundError: No module named 'anip_rest_adapter.discovery'"

**Step 3: Write the discovery module**

Create `adapters/rest-py/anip_rest_adapter/discovery.py` — this is identical to `adapters/mcp-py/anip_mcp_bridge/discovery.py`:

```python
"""ANIP service discovery and manifest fetching."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass
class ANIPCapability:
    """A discovered ANIP capability with full metadata."""

    name: str
    description: str
    side_effect: str
    rollback_window: str | None
    minimum_scope: list[str]
    financial: bool
    contract_version: str
    inputs: list[dict]
    output: dict
    cost: dict | None
    requires: list[dict]


@dataclass
class ANIPService:
    """A discovered ANIP service."""

    base_url: str
    protocol: str
    compliance: str
    endpoints: dict[str, str]
    capabilities: dict[str, ANIPCapability]
    profiles: dict[str, str] = field(default_factory=dict)


async def discover_service(anip_url: str) -> ANIPService:
    """Discover an ANIP service from its base URL."""
    async with httpx.AsyncClient(timeout=30) as client:
        discovery_url = f"{anip_url.rstrip('/')}/.well-known/anip"
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        discovery = resp.json()["anip_discovery"]

        base_url = discovery["base_url"]
        endpoints = discovery["endpoints"]

        manifest_url = _resolve_url(base_url, endpoints["manifest"])
        resp = await client.get(manifest_url)
        resp.raise_for_status()
        manifest = resp.json()

        capabilities = {}
        for name, cap in manifest["capabilities"].items():
            capabilities[name] = ANIPCapability(
                name=name,
                description=cap["description"],
                side_effect=cap["side_effect"]["type"],
                rollback_window=cap["side_effect"].get("rollback_window"),
                minimum_scope=cap.get("minimum_scope", cap.get("required_scope", [])),
                financial=cap.get("cost", {}).get("financial") is not None,
                contract_version=cap.get("contract_version", "1.0"),
                inputs=cap.get("inputs", []),
                output=cap.get("output", {}),
                cost=cap.get("cost"),
                requires=cap.get("requires", []),
            )

        resolved_endpoints = {
            k: _resolve_url(base_url, v) for k, v in endpoints.items()
        }

        return ANIPService(
            base_url=base_url,
            protocol=discovery["protocol"],
            compliance=discovery.get("compliance", "anip-compliant"),
            endpoints=resolved_endpoints,
            capabilities=capabilities,
            profiles=discovery.get("profile", {}),
        )


def _resolve_url(base_url: str, path: str) -> str:
    """Resolve a relative endpoint path against the base URL."""
    if path.startswith("http"):
        return path
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
```

**Step 4: Run test to verify it passes**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: "2. Discovery tests passed"

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/discovery.py adapters/rest-py/test_adapter.py
git commit -m "feat(rest-py): add discovery module (reuses MCP adapter pattern)"
```

---

### Task 4: Invocation module (reuse MCP pattern)

**Files:**
- Create: `adapters/rest-py/anip_rest_adapter/invocation.py`

**Step 1: Write the failing test**

Append to `adapters/rest-py/test_adapter.py`:

```python
async def test_invocation(url: str):
    from anip_rest_adapter.discovery import discover_service
    from anip_rest_adapter.invocation import ANIPInvoker

    service = await discover_service(url)
    invoker = ANIPInvoker(
        service=service,
        issuer="human:test@example.com",
        scope=["travel.search", "travel.book:max_$500"],
    )
    await invoker.setup()

    result = await invoker.invoke("search_flights", {
        "origin": "SEA",
        "destination": "SFO",
        "date": "2026-03-10",
    })
    assert result["success"] is True
    assert "result" in result
    print(f"   search_flights: success={result['success']}")

    result = await invoker.invoke("book_flight", {
        "flight_number": "AA100",
        "date": "2026-03-10",
        "passengers": 1,
    })
    assert result["success"] is True
    print(f"   book_flight: success={result['success']}")

    print("3. Invocation tests passed")
```

Update `__main__`:
```python
if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_config())
    asyncio.run(test_discovery(url))
    asyncio.run(test_invocation(url))
```

**Step 2: Run test to verify it fails**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: FAIL with "ModuleNotFoundError: No module named 'anip_rest_adapter.invocation'"

**Step 3: Write the invocation module**

Create `adapters/rest-py/anip_rest_adapter/invocation.py`:

```python
"""ANIP capability invocation for the REST adapter.

Unlike the MCP adapter which returns translated strings, the REST adapter
returns raw ANIP response dicts for direct JSON serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from .discovery import ANIPService


class ANIPInvoker:
    """Invokes ANIP capabilities, returning raw response dicts."""

    def __init__(
        self,
        service: ANIPService,
        issuer: str,
        scope: list[str],
        token_ttl_minutes: int = 60,
    ):
        self.service = service
        self.issuer = issuer
        self.scope = scope
        self.token_ttl_minutes = token_ttl_minutes
        self._root_token_id: str | None = None

    async def setup(self) -> None:
        """Register the root delegation token with the ANIP service."""
        self._root_token_id = f"rest-adapter-{uuid.uuid4().hex[:12]}"
        root_token = {
            "token_id": self._root_token_id,
            "issuer": self.issuer,
            "subject": "adapter:anip-rest-adapter",
            "scope": self.scope,
            "purpose": {
                "capability": "*",
                "parameters": {},
                "task_id": f"rest-session-{uuid.uuid4().hex[:8]}",
            },
            "parent": None,
            "expires": (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.token_ttl_minutes)
            ).isoformat(),
            "constraints": {
                "max_delegation_depth": 2,
                "concurrent_branches": "allowed",
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.service.endpoints["tokens"], json=root_token
            )
            resp.raise_for_status()

    async def invoke(
        self, capability_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke an ANIP capability and return the raw response dict."""
        cap_token_id = f"rest-{capability_name}-{uuid.uuid4().hex[:8]}"

        capability = self.service.capabilities.get(capability_name)
        cap_scope = self.scope
        if capability:
            needed = capability.minimum_scope
            cap_scope = [
                s for s in self.scope if s.split(":")[0] in needed or s in needed
            ]
            if not cap_scope:
                cap_scope = self.scope

        cap_token = {
            "token_id": cap_token_id,
            "issuer": "adapter:anip-rest-adapter",
            "subject": "adapter:anip-rest-adapter",
            "scope": cap_scope,
            "purpose": {
                "capability": capability_name,
                "parameters": arguments,
                "task_id": f"rest-invoke-{uuid.uuid4().hex[:8]}",
            },
            "parent": self._root_token_id,
            "expires": (
                datetime.now(timezone.utc)
                + timedelta(minutes=self.token_ttl_minutes)
            ).isoformat(),
            "constraints": {
                "max_delegation_depth": 2,
                "concurrent_branches": "allowed",
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.service.endpoints["tokens"], json=cap_token
            )
            resp.raise_for_status()

            invoke_url = self.service.endpoints["invoke"].replace(
                "{capability}", capability_name
            )
            resp = await client.post(
                invoke_url,
                json={
                    "delegation_token": cap_token,
                    "parameters": arguments,
                },
            )
            resp.raise_for_status()
            return resp.json()
```

**Step 4: Run test to verify it passes**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: "3. Invocation tests passed"

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/invocation.py adapters/rest-py/test_adapter.py
git commit -m "feat(rest-py): add invocation module (returns raw dicts for REST)"
```

---

### Task 5: Translation module (ANIP → REST routes + OpenAPI)

**Files:**
- Create: `adapters/rest-py/anip_rest_adapter/translation.py`

**Step 1: Write the failing test**

Append to `adapters/rest-py/test_adapter.py`:

```python
async def test_translation(url: str):
    from anip_rest_adapter.discovery import discover_service
    from anip_rest_adapter.translation import (
        generate_openapi_spec,
        generate_routes,
    )

    service = await discover_service(url)
    routes = generate_routes(service, route_overrides={})

    # Default routes: POST /api/{capability_name}, except read → GET
    search_route = routes["search_flights"]
    assert search_route.method == "GET"
    assert search_route.path == "/api/search_flights"

    book_route = routes["book_flight"]
    assert book_route.method == "POST"
    assert book_route.path == "/api/book_flight"

    # OpenAPI spec
    spec = generate_openapi_spec(service, routes)
    assert spec["openapi"] == "3.1.0"
    assert "/api/search_flights" in spec["paths"]
    assert "/api/book_flight" in spec["paths"]

    # Check x-anip-* extensions
    book_op = spec["paths"]["/api/book_flight"]["post"]
    assert book_op["x-anip-side-effect"] == "irreversible"
    assert book_op["x-anip-financial"] is True
    assert "x-anip-cost" in book_op

    print(f"   Routes: {len(routes)} generated")
    print(f"   OpenAPI paths: {list(spec['paths'].keys())}")
    print("4. Translation tests passed")
```

Update `__main__`:
```python
if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_config())
    asyncio.run(test_discovery(url))
    asyncio.run(test_invocation(url))
    asyncio.run(test_translation(url))
```

**Step 2: Run test to verify it fails**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: FAIL with "ModuleNotFoundError: No module named 'anip_rest_adapter.translation'"

**Step 3: Write the translation module**

Create `adapters/rest-py/anip_rest_adapter/translation.py`:

```python
"""ANIP → REST/OpenAPI translation layer.

Generates REST routes and OpenAPI 3.1 spec from ANIP capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import RouteOverride
from .discovery import ANIPCapability, ANIPService

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


@dataclass
class RESTRoute:
    """A generated REST route for an ANIP capability."""

    capability_name: str
    path: str
    method: str  # "GET" or "POST"
    capability: ANIPCapability


def generate_routes(
    service: ANIPService,
    route_overrides: dict[str, RouteOverride],
) -> dict[str, RESTRoute]:
    """Generate REST routes from ANIP capabilities.

    Default: POST /api/{name} for everything, GET for read capabilities.
    Overridable per-capability via config.
    """
    routes = {}
    for name, cap in service.capabilities.items():
        if name in route_overrides:
            override = route_overrides[name]
            routes[name] = RESTRoute(
                capability_name=name,
                path=override.path,
                method=override.method.upper(),
                capability=cap,
            )
        else:
            method = "GET" if cap.side_effect == "read" else "POST"
            routes[name] = RESTRoute(
                capability_name=name,
                path=f"/api/{name}",
                method=method,
                capability=cap,
            )
    return routes


def _build_parameters(cap: ANIPCapability) -> list[dict[str, Any]]:
    """Build OpenAPI parameters (for GET query params)."""
    params = []
    for inp in cap.inputs:
        param: dict[str, Any] = {
            "name": inp["name"],
            "in": "query",
            "required": inp.get("required", True),
            "schema": {"type": _TYPE_MAP.get(inp.get("type", "string"), "string")},
        }
        if inp.get("description"):
            param["description"] = inp["description"]
        if inp.get("type") == "date":
            param["schema"]["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            param["schema"]["default"] = inp["default"]
        params.append(param)
    return params


def _build_request_body(cap: ANIPCapability) -> dict[str, Any]:
    """Build OpenAPI requestBody (for POST JSON body)."""
    properties = {}
    required = []
    for inp in cap.inputs:
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        prop: dict[str, Any] = {"type": json_type}
        if inp.get("description"):
            prop["description"] = inp["description"]
        if inp.get("type") == "date":
            prop["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            prop["default"] = inp["default"]
        properties[inp["name"]] = prop
        if inp.get("required", True):
            required.append(inp["name"])

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required

    return {
        "required": True,
        "content": {"application/json": {"schema": schema}},
    }


def _build_anip_extensions(cap: ANIPCapability) -> dict[str, Any]:
    """Build x-anip-* OpenAPI extensions for a capability."""
    extensions: dict[str, Any] = {
        "x-anip-side-effect": cap.side_effect,
        "x-anip-minimum-scope": cap.minimum_scope,
        "x-anip-contract-version": cap.contract_version,
        "x-anip-financial": cap.financial,
    }

    if cap.rollback_window is not None:
        extensions["x-anip-rollback-window"] = cap.rollback_window

    if cap.cost:
        extensions["x-anip-cost"] = cap.cost

    if cap.requires:
        prereqs = [r.get("capability", r) for r in cap.requires]
        extensions["x-anip-requires"] = prereqs

    return extensions


def generate_openapi_spec(
    service: ANIPService,
    routes: dict[str, RESTRoute],
) -> dict[str, Any]:
    """Generate a complete OpenAPI 3.1 spec from ANIP capabilities."""
    paths: dict[str, Any] = {}

    for name, route in routes.items():
        cap = route.capability
        operation: dict[str, Any] = {
            "operationId": name,
            "summary": cap.description,
            "tags": ["ANIP Capabilities"],
            "responses": {
                "200": {
                    "description": "Successful invocation",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ANIPResponse"},
                        }
                    },
                },
                "400": {"description": "Invalid parameters"},
                "401": {"description": "Delegation expired"},
                "403": {"description": "Insufficient authority or budget exceeded"},
                "404": {"description": "Unknown capability"},
            },
        }

        if route.method == "GET":
            operation["parameters"] = _build_parameters(cap)
        else:
            operation["requestBody"] = _build_request_body(cap)

        # Add x-anip-* extensions
        operation.update(_build_anip_extensions(cap))

        paths[route.path] = {route.method.lower(): operation}

    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"ANIP REST Adapter — {service.base_url}",
            "version": service.compliance,
            "description": (
                "Auto-generated REST API from an ANIP service. "
                "x-anip-* extensions preserve ANIP metadata."
            ),
        },
        "paths": paths,
        "components": {
            "schemas": {
                "ANIPResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "result": {"type": "object"},
                        "cost_actual": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "financial": {
                                    "type": "object",
                                    "properties": {
                                        "amount": {"type": "number"},
                                        "currency": {"type": "string"},
                                    },
                                },
                                "variance_from_estimate": {"type": "string"},
                            },
                        },
                        "failure": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "type": {"type": "string"},
                                "detail": {"type": "string"},
                                "resolution": {
                                    "type": "object",
                                    "properties": {
                                        "action": {"type": "string"},
                                        "requires": {"type": "string"},
                                        "grantable_by": {"type": "string"},
                                    },
                                },
                                "retry": {"type": "boolean"},
                            },
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["success"],
                },
            },
        },
    }
```

**Step 4: Run test to verify it passes**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: "4. Translation tests passed"

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/translation.py adapters/rest-py/test_adapter.py
git commit -m "feat(rest-py): add translation module (routes + OpenAPI generation)"
```

---

### Task 6: Server module (FastAPI app)

**Files:**
- Create: `adapters/rest-py/anip_rest_adapter/server.py`

**Step 1: Write the failing test**

Append to `adapters/rest-py/test_adapter.py`:

```python
async def test_server(url: str):
    """Test the full server by starting it and making HTTP requests."""
    from anip_rest_adapter.config import AdapterConfig, DelegationConfig
    from anip_rest_adapter.server import build_app

    config = AdapterConfig(
        anip_service_url=url,
        port=3099,
        delegation=DelegationConfig(
            issuer="human:test@example.com",
            scope=["travel.search", "travel.book:max_$500"],
        ),
    )
    app = await build_app(config)

    # Use httpx to test the FastAPI app directly (TestClient-style)
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # OpenAPI spec
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        assert "paths" in spec
        print("   GET /openapi.json: OK")

        # Search flights (GET)
        resp = await client.get(
            "/api/search_flights",
            params={"origin": "SEA", "destination": "SFO", "date": "2026-03-10"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        print(f"   GET /api/search_flights: success={data['success']}")

        # Book flight (POST)
        resp = await client.post(
            "/api/book_flight",
            json={"flight_number": "AA100", "date": "2026-03-10", "passengers": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        print(f"   POST /api/book_flight: success={data['success']}")

    print("5. Server tests passed")
```

Update `__main__`:
```python
if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_config())
    asyncio.run(test_discovery(url))
    asyncio.run(test_invocation(url))
    asyncio.run(test_translation(url))
    asyncio.run(test_server(url))
```

**Step 2: Run test to verify it fails**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: FAIL with "ModuleNotFoundError: No module named 'anip_rest_adapter.server'"

**Step 3: Write the server module**

Create `adapters/rest-py/anip_rest_adapter/server.py`:

```python
"""ANIP REST Adapter Server.

Discovers any ANIP service and exposes it as REST endpoints
with auto-generated OpenAPI spec.

Usage:
    anip-rest-adapter --config adapter.yaml
    ANIP_SERVICE_URL=http://localhost:8000 anip-rest-adapter
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import AdapterConfig, load_config
from .discovery import ANIPService, discover_service
from .invocation import ANIPInvoker
from .translation import generate_openapi_spec, generate_routes

logger = logging.getLogger("anip-rest-adapter")

# Failure type → HTTP status code mapping
_FAILURE_STATUS_MAP = {
    "unknown_capability": 404,
    "insufficient_authority": 403,
    "budget_exceeded": 403,
    "purpose_mismatch": 403,
    "invalid_parameters": 400,
    "delegation_expired": 401,
}


async def build_app(config: AdapterConfig) -> FastAPI:
    """Discover ANIP service and build FastAPI app with generated routes."""
    service = await discover_service(config.anip_service_url)
    logger.info(
        "Discovered %s (%s) with %d capabilities",
        service.base_url,
        service.compliance,
        len(service.capabilities),
    )

    invoker = ANIPInvoker(
        service=service,
        issuer=config.delegation.issuer,
        scope=config.delegation.scope,
        token_ttl_minutes=config.delegation.token_ttl_minutes,
    )
    await invoker.setup()
    logger.info("Delegation token registered")

    routes = generate_routes(service, config.routes)
    openapi_spec = generate_openapi_spec(service, routes)

    app = FastAPI(
        title=f"ANIP REST Adapter — {service.base_url}",
        version="0.1.0",
        docs_url="/docs",
        openapi_url=None,  # We serve our own OpenAPI spec
    )

    @app.get("/openapi.json")
    async def get_openapi():
        return openapi_spec

    # Generate route handlers
    for name, route in routes.items():
        _register_route(app, route.path, route.method, name, route.capability, invoker)

    return app


def _register_route(
    app: FastAPI,
    path: str,
    method: str,
    capability_name: str,
    capability: Any,
    invoker: ANIPInvoker,
) -> None:
    """Register a single route handler for an ANIP capability."""

    if method == "GET":

        @app.api_route(path, methods=["GET"], name=capability_name)
        async def handle_get(request: Request, _name=capability_name, _cap=capability):
            params = dict(request.query_params)
            # Convert integer params
            for inp in _cap.inputs:
                if inp.get("type") == "integer" and inp["name"] in params:
                    params[inp["name"]] = int(params[inp["name"]])
            return await _invoke_and_respond(_name, _cap, params, invoker)

    else:

        @app.api_route(path, methods=["POST"], name=capability_name)
        async def handle_post(request: Request, _name=capability_name, _cap=capability):
            body = await request.json()
            return await _invoke_and_respond(_name, _cap, body, invoker)


async def _invoke_and_respond(
    capability_name: str,
    capability: Any,
    arguments: dict[str, Any],
    invoker: ANIPInvoker,
) -> JSONResponse:
    """Invoke ANIP capability and translate response to REST."""
    try:
        result = await invoker.invoke(capability_name, arguments)
    except Exception as e:
        logger.exception("ANIP invocation failed for %s", capability_name)
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "failure": {
                    "type": "adapter_error",
                    "detail": str(e),
                    "retry": True,
                },
            },
        )

    # Build response with warnings
    response: dict[str, Any] = {
        "success": result.get("success", False),
        "result": result.get("result"),
    }

    if result.get("cost_actual"):
        response["cost_actual"] = result["cost_actual"]

    warnings = []
    if capability.side_effect == "irreversible":
        warnings.append("IRREVERSIBLE: this action cannot be undone")
    if capability.financial:
        warnings.append("FINANCIAL: this action involves real charges")
    if warnings:
        response["warnings"] = warnings

    if result.get("success"):
        return JSONResponse(status_code=200, content=response)

    # Map ANIP failure to HTTP status
    failure = result.get("failure", {})
    response["failure"] = failure
    status = _FAILURE_STATUS_MAP.get(failure.get("type", ""), 500)
    return JSONResponse(status_code=status, content=response)


def main() -> None:
    """Entry point for the adapter CLI."""
    parser = argparse.ArgumentParser(
        description="ANIP REST Adapter: expose any ANIP service as REST/OpenAPI"
    )
    parser.add_argument("--config", "-c", help="Path to adapter.yaml config file")
    parser.add_argument("--url", "-u", help="ANIP service URL (overrides config)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    config = load_config(args.config)
    if args.url:
        config.anip_service_url = args.url

    import asyncio

    app = asyncio.run(build_app(config))
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd adapters/rest-py && python test_adapter.py http://localhost:9100`
Expected: "5. Server tests passed"

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/server.py adapters/rest-py/test_adapter.py
git commit -m "feat(rest-py): add FastAPI server with auto-generated routes + OpenAPI"
```

---

### Task 7: README

**Files:**
- Create: `adapters/rest-py/README.md`

**Step 1: Write README**

```markdown
# ANIP REST/OpenAPI Adapter (Python)

A generic adapter that discovers any ANIP-compliant service and exposes its
capabilities as REST endpoints with auto-generated OpenAPI 3.1 spec.

**This is a reference adapter, not a production architecture.** The same
translation logic can be embedded as middleware directly in the ANIP service,
eliminating the second process. This adapter proves interoperability; the
SDK/middleware approach is the production deployment path.

## Quick Start

```bash
pip install -e .
ANIP_SERVICE_URL=http://localhost:8000 anip-rest-adapter
```

The adapter auto-discovers the ANIP service, generates REST routes and an
OpenAPI spec, and starts serving on port 3001.

## Endpoints

Default (zero config):
- `GET /api/search_flights` — read capabilities become GET with query params
- `POST /api/book_flight` — write/irreversible become POST with JSON body
- `GET /openapi.json` — auto-generated OpenAPI 3.1 spec
- `GET /docs` — Swagger UI

With path overrides (via `adapter.yaml`):
- `GET /flights/search` → search_flights
- `POST /flights/book` → book_flight

## ANIP Metadata

The OpenAPI spec includes `x-anip-*` extensions on each operation:
- `x-anip-side-effect` — read, write, irreversible, transactional
- `x-anip-minimum-scope` — required delegation scopes
- `x-anip-financial` — whether the operation involves charges
- `x-anip-cost` — cost estimate details
- `x-anip-requires` — prerequisite capabilities
- `x-anip-rollback-window` — reversibility window
- `x-anip-contract-version` — ANIP contract version

## Configuration

Via `adapter.yaml` or environment variables:

| Env Variable | Default | Description |
|---|---|---|
| `ANIP_SERVICE_URL` | `http://localhost:8000` | ANIP service to proxy |
| `ANIP_ADAPTER_PORT` | `3001` | Port to serve on |
| `ANIP_ISSUER` | `human:user@example.com` | Delegation issuer |
| `ANIP_SCOPE` | `*` | Comma-separated scopes |

## Testing

```bash
python test_adapter.py http://localhost:8000
```

## Translation Loss

| ANIP Primitive | REST Adapter | What's Lost |
|---|---|---|
| Capability Declaration | Full — endpoint + OpenAPI | Nothing |
| Side-effect Typing | `x-anip-side-effect` extension | Standard clients don't read extensions |
| Delegation Chain | Simplified — single identity | Multi-hop, concurrent branches |
| Permission Discovery | Absent | Can't query before calling |
| Failure Semantics | HTTP status + ANIPFailure body | Status codes conflate failure types |
| Cost Signaling | `x-anip-cost` + `cost_actual` | Standard clients don't read extensions |
| Capability Graph | Absent | Not discoverable from spec |
| State & Session | Absent | No continuity |
| Observability | Absent | No audit access |
```

**Step 2: Commit**

```bash
git add adapters/rest-py/README.md
git commit -m "docs(rest-py): add README with usage, config, and translation loss"
```

---

## Phase 2: REST TypeScript Adapter (`adapters/rest-ts/`)

### Task 8: Project scaffolding

**Files:**
- Create: `adapters/rest-ts/package.json`
- Create: `adapters/rest-ts/tsconfig.json`
- Create: `adapters/rest-ts/adapter.example.yaml`

**Step 1: Create package.json**

```json
{
  "name": "anip-rest-adapter-ts",
  "version": "0.1.0",
  "description": "Generic REST/OpenAPI adapter for any ANIP-compliant service (TypeScript)",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "dev": "tsx src/index.ts",
    "start": "node dist/index.js",
    "test": "tsx test-adapter.ts"
  },
  "dependencies": {
    "hono": "^4.6.0",
    "@hono/node-server": "^1.13.0",
    "@hono/swagger-ui": "^0.4.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "tsx": "^4.15.0",
    "@types/node": "^22.0.0"
  }
}
```

**Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "declaration": true
  },
  "include": ["src/**/*.ts"]
}
```

**Step 3: Create adapter.example.yaml** (same as Python version)

```yaml
anip_service_url: "http://localhost:8000"
port: 3001

delegation:
  issuer: "human:user@example.com"
  scope: ["travel.search", "travel.book:max_$500"]
  token_ttl_minutes: 60

routes:
  search_flights:
    path: "/flights/search"
    method: "GET"
  book_flight:
    path: "/flights/book"
    method: "POST"
```

**Step 4: Install dependencies and commit**

```bash
cd adapters/rest-ts && npm install
git add adapters/rest-ts/package.json adapters/rest-ts/tsconfig.json adapters/rest-ts/adapter.example.yaml
git commit -m "feat(rest-ts): scaffold REST adapter project"
```

---

### Task 9: Config module (TypeScript)

**Files:**
- Create: `adapters/rest-ts/src/config.ts`

**Step 1: Write config.ts**

```typescript
/**
 * Adapter configuration — from environment variables or defaults.
 */

export interface RouteOverride {
  path: string;
  method: string;
}

export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
  routes: Record<string, RouteOverride>;
}

export function loadConfig(): AdapterConfig {
  return {
    anipServiceUrl: process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
    port: Number(process.env.ANIP_ADAPTER_PORT ?? "3001"),
    issuer: process.env.ANIP_ISSUER ?? "human:user@example.com",
    scope: (process.env.ANIP_SCOPE ?? "*").split(","),
    tokenTtlMinutes: Number(process.env.ANIP_TOKEN_TTL ?? "60"),
    routes: {},
  };
}
```

**Step 2: Commit**

```bash
git add adapters/rest-ts/src/config.ts
git commit -m "feat(rest-ts): add config module"
```

---

### Task 10: Discovery module (TypeScript, reuse from mcp-ts)

**Files:**
- Create: `adapters/rest-ts/src/discovery.ts`

**Step 1: Write discovery.ts**

Copy from `adapters/mcp-ts/src/discovery.ts` — identical code:

```typescript
/**
 * ANIP service discovery and manifest fetching.
 */

export interface ANIPCapability {
  name: string;
  description: string;
  sideEffect: string;
  rollbackWindow: string | null;
  minimumScope: string[];
  financial: boolean;
  contractVersion: string;
  inputs: Array<{
    name: string;
    type: string;
    required?: boolean;
    default?: unknown;
    description?: string;
  }>;
  output: { type: string; fields: string[] };
  cost: Record<string, unknown> | null;
  requires: Array<{ capability: string; reason: string }>;
}

export interface ANIPService {
  baseUrl: string;
  protocol: string;
  compliance: string;
  endpoints: Record<string, string>;
  capabilities: Map<string, ANIPCapability>;
}

export async function discoverService(anipUrl: string): Promise<ANIPService> {
  const discoveryUrl = `${anipUrl.replace(/\/$/, "")}/.well-known/anip`;
  const discoveryResp = await fetch(discoveryUrl);
  if (!discoveryResp.ok) {
    throw new Error(`Discovery failed: ${discoveryResp.status} ${discoveryResp.statusText}`);
  }
  const { anip_discovery: discovery } = (await discoveryResp.json()) as {
    anip_discovery: Record<string, unknown>;
  };

  const baseUrl = discovery.base_url as string;
  const endpoints = discovery.endpoints as Record<string, string>;

  const manifestUrl = resolveUrl(baseUrl, endpoints.manifest);
  const manifestResp = await fetch(manifestUrl);
  if (!manifestResp.ok) {
    throw new Error(`Manifest fetch failed: ${manifestResp.status} ${manifestResp.statusText}`);
  }
  const manifest = (await manifestResp.json()) as {
    capabilities: Record<string, Record<string, unknown>>;
  };

  const capabilities = new Map<string, ANIPCapability>();
  for (const [name, cap] of Object.entries(manifest.capabilities)) {
    const sideEffect = cap.side_effect as { type: string; rollback_window?: string };
    const minimumScope = cap.minimum_scope as string[];
    capabilities.set(name, {
      name,
      description: cap.description as string,
      sideEffect: sideEffect.type,
      rollbackWindow: sideEffect.rollback_window ?? null,
      minimumScope,
      financial: (cap.cost as Record<string, unknown>)?.financial != null,
      contractVersion: (cap.contract_version as string) ?? "1.0",
      inputs: (cap.inputs as ANIPCapability["inputs"]) ?? [],
      output: (cap.output as ANIPCapability["output"]) ?? { type: "unknown", fields: [] },
      cost: (cap.cost as Record<string, unknown>) ?? null,
      requires: (cap.requires as Array<{ capability: string; reason: string }>) ?? [],
    });
  }

  const resolvedEndpoints: Record<string, string> = {};
  for (const [k, v] of Object.entries(endpoints)) {
    resolvedEndpoints[k] = resolveUrl(baseUrl, v);
  }

  return {
    baseUrl,
    protocol: discovery.protocol as string,
    compliance: (discovery.compliance as string) ?? "anip-compliant",
    endpoints: resolvedEndpoints,
    capabilities,
  };
}

function resolveUrl(baseUrl: string, path: string): string {
  if (path.startsWith("http")) return path;
  return `${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}
```

**Step 2: Commit**

```bash
git add adapters/rest-ts/src/discovery.ts
git commit -m "feat(rest-ts): add discovery module (reuses MCP adapter pattern)"
```

---

### Task 11: Invocation module (TypeScript)

**Files:**
- Create: `adapters/rest-ts/src/invocation.ts`

**Step 1: Write invocation.ts**

```typescript
/**
 * ANIP capability invocation for the REST adapter.
 * Returns raw response objects for direct JSON serialization.
 */

import type { ANIPService } from "./discovery.js";

interface DelegationConfig {
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
}

export class ANIPInvoker {
  private service: ANIPService;
  private config: DelegationConfig;
  private rootTokenId: string | null = null;

  constructor(service: ANIPService, config: DelegationConfig) {
    this.service = service;
    this.config = config;
  }

  async setup(): Promise<void> {
    this.rootTokenId = `rest-adapter-${randomHex(12)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

    const rootToken = {
      token_id: this.rootTokenId,
      issuer: this.config.issuer,
      subject: "adapter:anip-rest-adapter-ts",
      scope: this.config.scope,
      purpose: {
        capability: "*",
        parameters: {},
        task_id: `rest-session-${randomHex(8)}`,
      },
      parent: null,
      expires,
      constraints: {
        max_delegation_depth: 2,
        concurrent_branches: "allowed",
      },
    };

    const resp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rootToken),
    });
    if (!resp.ok) {
      throw new Error(`Token registration failed: ${resp.status}`);
    }
  }

  async invoke(
    capabilityName: string,
    args: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    const capTokenId = `rest-${capabilityName}-${randomHex(8)}`;
    const expires = new Date(
      Date.now() + this.config.tokenTtlMinutes * 60 * 1000
    ).toISOString();

    const capability = this.service.capabilities.get(capabilityName);
    let capScope = this.config.scope;
    if (capability) {
      const needed = new Set(capability.minimumScope);
      const narrowed = this.config.scope.filter((s) => {
        const base = s.split(":")[0];
        return needed.has(base) || needed.has(s);
      });
      if (narrowed.length > 0) {
        capScope = narrowed;
      }
    }

    const capToken = {
      token_id: capTokenId,
      issuer: "adapter:anip-rest-adapter-ts",
      subject: "adapter:anip-rest-adapter-ts",
      scope: capScope,
      purpose: {
        capability: capabilityName,
        parameters: args,
        task_id: `rest-invoke-${randomHex(8)}`,
      },
      parent: this.rootTokenId,
      expires,
      constraints: {
        max_delegation_depth: 2,
        concurrent_branches: "allowed",
      },
    };

    const tokenResp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(capToken),
    });
    if (!tokenResp.ok) {
      throw new Error(`Token registration failed: ${tokenResp.status}`);
    }

    const invokeUrl = this.service.endpoints.invoke.replace(
      "{capability}",
      capabilityName
    );
    const invokeResp = await fetch(invokeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        delegation_token: capToken,
        parameters: args,
      }),
    });
    if (!invokeResp.ok) {
      throw new Error(`Invocation failed: ${invokeResp.status}`);
    }

    return (await invokeResp.json()) as Record<string, unknown>;
  }
}

function randomHex(length: number): string {
  const chars = "0123456789abcdef";
  let result = "";
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * 16)];
  }
  return result;
}
```

**Step 2: Commit**

```bash
git add adapters/rest-ts/src/invocation.ts
git commit -m "feat(rest-ts): add invocation module (returns raw response objects)"
```

---

### Task 12: Translation module (TypeScript)

**Files:**
- Create: `adapters/rest-ts/src/translation.ts`

**Step 1: Write translation.ts**

```typescript
/**
 * ANIP → REST/OpenAPI translation layer.
 * Generates routes and OpenAPI 3.1 spec from ANIP capabilities.
 */

import type { ANIPCapability, ANIPService } from "./discovery.js";
import type { RouteOverride } from "./config.js";

const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface RESTRoute {
  capabilityName: string;
  path: string;
  method: string;
  capability: ANIPCapability;
}

export function generateRoutes(
  service: ANIPService,
  routeOverrides: Record<string, RouteOverride>
): Map<string, RESTRoute> {
  const routes = new Map<string, RESTRoute>();

  for (const [name, cap] of service.capabilities) {
    if (name in routeOverrides) {
      const override = routeOverrides[name];
      routes.set(name, {
        capabilityName: name,
        path: override.path,
        method: override.method.toUpperCase(),
        capability: cap,
      });
    } else {
      const method = cap.sideEffect === "read" ? "GET" : "POST";
      routes.set(name, {
        capabilityName: name,
        path: `/api/${name}`,
        method,
        capability: cap,
      });
    }
  }

  return routes;
}

function buildParameters(cap: ANIPCapability): Record<string, unknown>[] {
  return cap.inputs.map((inp) => {
    const param: Record<string, unknown> = {
      name: inp.name,
      in: "query",
      required: inp.required ?? true,
      schema: { type: TYPE_MAP[inp.type ?? "string"] ?? "string" },
    };
    if (inp.description) param.description = inp.description;
    if (inp.type === "date") {
      (param.schema as Record<string, unknown>).format = "date";
    }
    if (inp.default !== undefined && inp.default !== null) {
      (param.schema as Record<string, unknown>).default = inp.default;
    }
    return param;
  });
}

function buildRequestBody(cap: ANIPCapability): Record<string, unknown> {
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  for (const inp of cap.inputs) {
    const prop: Record<string, unknown> = {
      type: TYPE_MAP[inp.type ?? "string"] ?? "string",
    };
    if (inp.description) prop.description = inp.description;
    if (inp.type === "date") prop.format = "date";
    if (inp.default !== undefined && inp.default !== null) {
      prop.default = inp.default;
    }
    properties[inp.name] = prop;
    if (inp.required ?? true) required.push(inp.name);
  }

  const schema: Record<string, unknown> = { type: "object", properties };
  if (required.length > 0) schema.required = required;

  return {
    required: true,
    content: { "application/json": { schema } },
  };
}

function buildAnipExtensions(cap: ANIPCapability): Record<string, unknown> {
  const ext: Record<string, unknown> = {
    "x-anip-side-effect": cap.sideEffect,
    "x-anip-minimum-scope": cap.minimumScope,
    "x-anip-contract-version": cap.contractVersion,
    "x-anip-financial": cap.financial,
  };

  if (cap.rollbackWindow !== null) {
    ext["x-anip-rollback-window"] = cap.rollbackWindow;
  }
  if (cap.cost) ext["x-anip-cost"] = cap.cost;
  if (cap.requires.length > 0) {
    ext["x-anip-requires"] = cap.requires.map((r) => r.capability);
  }

  return ext;
}

export function generateOpenAPISpec(
  service: ANIPService,
  routes: Map<string, RESTRoute>
): Record<string, unknown> {
  const paths: Record<string, Record<string, unknown>> = {};

  for (const [name, route] of routes) {
    const cap = route.capability;
    const operation: Record<string, unknown> = {
      operationId: name,
      summary: cap.description,
      tags: ["ANIP Capabilities"],
      responses: {
        "200": {
          description: "Successful invocation",
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/ANIPResponse" },
            },
          },
        },
        "400": { description: "Invalid parameters" },
        "401": { description: "Delegation expired" },
        "403": { description: "Insufficient authority or budget exceeded" },
        "404": { description: "Unknown capability" },
      },
    };

    if (route.method === "GET") {
      operation.parameters = buildParameters(cap);
    } else {
      operation.requestBody = buildRequestBody(cap);
    }

    Object.assign(operation, buildAnipExtensions(cap));
    paths[route.path] = { [route.method.toLowerCase()]: operation };
  }

  return {
    openapi: "3.1.0",
    info: {
      title: `ANIP REST Adapter — ${service.baseUrl}`,
      version: service.compliance,
      description:
        "Auto-generated REST API from an ANIP service. x-anip-* extensions preserve ANIP metadata.",
    },
    paths,
    components: {
      schemas: {
        ANIPResponse: {
          type: "object",
          properties: {
            success: { type: "boolean" },
            result: { type: "object" },
            cost_actual: { type: "object", nullable: true },
            failure: { type: "object", nullable: true },
            warnings: { type: "array", items: { type: "string" } },
          },
          required: ["success"],
        },
      },
    },
  };
}
```

**Step 2: Commit**

```bash
git add adapters/rest-ts/src/translation.ts
git commit -m "feat(rest-ts): add translation module (routes + OpenAPI generation)"
```

---

### Task 13: Server module (Hono app) + test

**Files:**
- Create: `adapters/rest-ts/src/index.ts`
- Create: `adapters/rest-ts/test-adapter.ts`

**Step 1: Write index.ts**

```typescript
/**
 * ANIP REST Adapter Server (TypeScript).
 *
 * Discovers any ANIP service and exposes it as REST endpoints
 * with auto-generated OpenAPI spec.
 */

import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { loadConfig } from "./config.js";
import { discoverService, type ANIPCapability } from "./discovery.js";
import { ANIPInvoker } from "./invocation.js";
import { generateRoutes, generateOpenAPISpec } from "./translation.js";

const FAILURE_STATUS_MAP: Record<string, number> = {
  unknown_capability: 404,
  insufficient_authority: 403,
  budget_exceeded: 403,
  purpose_mismatch: 403,
  invalid_parameters: 400,
  delegation_expired: 401,
};

async function main() {
  const config = loadConfig();
  console.error(`[anip-rest-adapter] Discovering ANIP service at ${config.anipServiceUrl}`);

  const service = await discoverService(config.anipServiceUrl);
  console.error(
    `[anip-rest-adapter] Discovered ${service.capabilities.size} capabilities`
  );

  const invoker = new ANIPInvoker(service, {
    issuer: config.issuer,
    scope: config.scope,
    tokenTtlMinutes: config.tokenTtlMinutes,
  });
  await invoker.setup();
  console.error("[anip-rest-adapter] Delegation token registered");

  const routes = generateRoutes(service, config.routes);
  const openApiSpec = generateOpenAPISpec(service, routes);

  const app = new Hono();

  // OpenAPI spec endpoint
  app.get("/openapi.json", (c) => c.json(openApiSpec));

  // Register capability routes
  for (const [name, route] of routes) {
    const cap = route.capability;

    if (route.method === "GET") {
      app.get(route.path, async (c) => {
        const params: Record<string, unknown> = {};
        for (const inp of cap.inputs) {
          const val = c.req.query(inp.name);
          if (val !== undefined) {
            params[inp.name] =
              inp.type === "integer" ? parseInt(val, 10) : val;
          }
        }
        return invokeAndRespond(c, name, cap, params, invoker);
      });
    } else {
      app.post(route.path, async (c) => {
        const body = await c.req.json();
        return invokeAndRespond(c, name, cap, body, invoker);
      });
    }
  }

  const port = config.port;
  console.error(`[anip-rest-adapter] Serving on http://localhost:${port}`);
  serve({ fetch: app.fetch, port });
}

async function invokeAndRespond(
  c: { json: (data: unknown, status?: number) => Response },
  capabilityName: string,
  capability: ANIPCapability,
  args: Record<string, unknown>,
  invoker: ANIPInvoker
): Promise<Response> {
  let result: Record<string, unknown>;
  try {
    result = await invoker.invoke(capabilityName, args);
  } catch (err) {
    console.error(`[anip-rest-adapter] Invocation failed for ${capabilityName}:`, err);
    return c.json(
      {
        success: false,
        failure: {
          type: "adapter_error",
          detail: String(err),
          retry: true,
        },
      },
      502
    );
  }

  const response: Record<string, unknown> = {
    success: result.success ?? false,
    result: result.result ?? null,
  };

  if (result.cost_actual) {
    response.cost_actual = result.cost_actual;
  }

  const warnings: string[] = [];
  if (capability.sideEffect === "irreversible") {
    warnings.push("IRREVERSIBLE: this action cannot be undone");
  }
  if (capability.financial) {
    warnings.push("FINANCIAL: this action involves real charges");
  }
  if (warnings.length > 0) {
    response.warnings = warnings;
  }

  if (result.success) {
    return c.json(response, 200);
  }

  const failure = result.failure as Record<string, unknown> | undefined;
  response.failure = failure;
  const status = FAILURE_STATUS_MAP[(failure?.type as string) ?? ""] ?? 500;
  return c.json(response, status);
}

main().catch((err) => {
  console.error("[anip-rest-adapter] Fatal:", err);
  process.exit(1);
});
```

**Step 2: Write test-adapter.ts**

```typescript
/**
 * Integration test for the REST adapter.
 */

import { discoverService } from "./src/discovery.js";
import { ANIPInvoker } from "./src/invocation.js";
import { generateRoutes, generateOpenAPISpec } from "./src/translation.js";

const url = process.argv[2] ?? "http://localhost:9100";

async function main() {
  console.log(`Testing REST adapter against ${url}\n`);

  // 1. Discovery
  console.log("1. Discovering service...");
  const service = await discoverService(url);
  console.log(`   Protocol: ${service.protocol}`);
  console.log(`   Capabilities: ${Array.from(service.capabilities.keys()).join(", ")}`);

  // 2. Translation
  console.log("\n2. Translating to REST routes...");
  const routes = generateRoutes(service, {});
  for (const [name, route] of routes) {
    console.log(`   ${route.method} ${route.path} → ${name}`);
  }

  // 3. OpenAPI
  console.log("\n3. Generating OpenAPI spec...");
  const spec = generateOpenAPISpec(service, routes);
  const paths = Object.keys((spec as Record<string, unknown>).paths as Record<string, unknown>);
  console.log(`   Paths: ${paths.join(", ")}`);
  console.log(`   OpenAPI version: ${(spec as Record<string, unknown>).openapi}`);

  // 4. Invocation
  console.log("\n4. Testing invocation...");
  const invoker = new ANIPInvoker(service, {
    issuer: "human:test@example.com",
    scope: ["travel.search", "travel.book:max_$500"],
    tokenTtlMinutes: 60,
  });
  await invoker.setup();
  console.log("   Root token registered");

  const searchResult = await invoker.invoke("search_flights", {
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
  });
  console.log(`   search_flights: success=${searchResult.success}`);

  const bookResult = await invoker.invoke("book_flight", {
    flight_number: "AA100",
    date: "2026-03-10",
    passengers: 1,
  });
  console.log(`   book_flight: success=${bookResult.success}`);

  console.log("\n--- All tests passed ---");
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
```

**Step 3: Commit**

```bash
git add adapters/rest-ts/src/index.ts adapters/rest-ts/test-adapter.ts
git commit -m "feat(rest-ts): add Hono server + integration test"
```

---

### Task 14: REST-TS README + run tests

**Files:**
- Create: `adapters/rest-ts/README.md`

**Step 1: Write README** (similar to Python version, adjusted for TypeScript)

**Step 2: Run integration test**

Run: `cd adapters/rest-ts && npm install && npx tsx test-adapter.ts http://localhost:9100`
Expected: "All tests passed"

**Step 3: Commit**

```bash
git add adapters/rest-ts/README.md
git commit -m "docs(rest-ts): add README"
```

---

## Phase 3: GraphQL Python Adapter (`adapters/graphql-py/`)

### Task 15: Project scaffolding

**Files:**
- Create: `adapters/graphql-py/pyproject.toml`
- Create: `adapters/graphql-py/anip_graphql_adapter/__init__.py`
- Create: `adapters/graphql-py/adapter.example.yaml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-graphql-adapter"
version = "0.1.0"
description = "Generic GraphQL adapter for any ANIP-compliant service"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
    "ariadne>=0.23.0",
]

[project.scripts]
anip-graphql-adapter = "anip_graphql_adapter.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 2: Create adapter.example.yaml**

```yaml
anip_service_url: "http://localhost:8000"
port: 3002

delegation:
  issuer: "human:user@example.com"
  scope: ["travel.search", "travel.book:max_$500"]
  token_ttl_minutes: 60

graphql:
  path: "/graphql"
  playground: true
  introspection: true
```

**Step 3: Create __init__.py and commit**

```bash
git add adapters/graphql-py/pyproject.toml adapters/graphql-py/anip_graphql_adapter/__init__.py adapters/graphql-py/adapter.example.yaml
git commit -m "feat(graphql-py): scaffold GraphQL adapter project"
```

---

### Task 16: Config module (GraphQL-specific)

**Files:**
- Create: `adapters/graphql-py/anip_graphql_adapter/config.py`

**Step 1: Write config module**

```python
"""Adapter configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DelegationConfig:
    issuer: str = "human:user@example.com"
    scope: list[str] = field(default_factory=lambda: ["*"])
    token_ttl_minutes: int = 60


@dataclass
class GraphQLConfig:
    path: str = "/graphql"
    playground: bool = True
    introspection: bool = True


@dataclass
class AdapterConfig:
    anip_service_url: str = "http://localhost:8000"
    port: int = 3002
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    graphql: GraphQLConfig = field(default_factory=GraphQLConfig)


def load_config(config_path: str | None = None) -> AdapterConfig:
    if config_path is None:
        config_path = os.environ.get("ANIP_ADAPTER_CONFIG")
    if config_path is None:
        default_path = Path("adapter.yaml")
        if default_path.exists():
            config_path = str(default_path)

    if config_path is None:
        return AdapterConfig(
            anip_service_url=os.environ.get("ANIP_SERVICE_URL", "http://localhost:8000"),
            port=int(os.environ.get("ANIP_ADAPTER_PORT", "3002")),
            delegation=DelegationConfig(
                issuer=os.environ.get("ANIP_ISSUER", "human:user@example.com"),
                scope=os.environ.get("ANIP_SCOPE", "*").split(","),
            ),
        )

    with open(config_path) as f:
        data = yaml.safe_load(f)

    delegation_data = data.get("delegation", {})
    graphql_data = data.get("graphql", {})

    return AdapterConfig(
        anip_service_url=data.get("anip_service_url", "http://localhost:8000"),
        port=data.get("port", 3002),
        delegation=DelegationConfig(
            issuer=delegation_data.get("issuer", "human:user@example.com"),
            scope=delegation_data.get("scope", ["*"]),
            token_ttl_minutes=delegation_data.get("token_ttl_minutes", 60),
        ),
        graphql=GraphQLConfig(
            path=graphql_data.get("path", "/graphql"),
            playground=graphql_data.get("playground", True),
            introspection=graphql_data.get("introspection", True),
        ),
    )
```

**Step 2: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/config.py
git commit -m "feat(graphql-py): add config module with GraphQL-specific options"
```

---

### Task 17: Discovery + Invocation modules (reuse)

**Files:**
- Create: `adapters/graphql-py/anip_graphql_adapter/discovery.py` (same as rest-py)
- Create: `adapters/graphql-py/anip_graphql_adapter/invocation.py` (same as rest-py, adapter name changed)

**Step 1: Copy discovery.py from rest-py** (identical)

**Step 2: Write invocation.py** (identical to rest-py but with "graphql-adapter" in token IDs)

Change token ID prefixes:
- `rest-adapter-` → `graphql-adapter-`
- `adapter:anip-rest-adapter` → `adapter:anip-graphql-adapter`
- `rest-session-` → `graphql-session-`
- `rest-invoke-` → `graphql-invoke-`
- `rest-{cap}-` → `graphql-{cap}-`

**Step 3: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/discovery.py adapters/graphql-py/anip_graphql_adapter/invocation.py
git commit -m "feat(graphql-py): add discovery + invocation modules"
```

---

### Task 18: Translation module (ANIP → GraphQL schema)

**Files:**
- Create: `adapters/graphql-py/anip_graphql_adapter/translation.py`

**Step 1: Write translation.py**

```python
"""ANIP → GraphQL translation layer.

Generates GraphQL schema (SDL) with custom directives from ANIP capabilities.
"""

from __future__ import annotations

from .discovery import ANIPCapability, ANIPService

_TYPE_MAP = {
    "string": "String",
    "integer": "Int",
    "number": "Float",
    "boolean": "Boolean",
    "date": "String",
    "airport_code": "String",
}


def _to_camel_case(snake: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _build_args(cap: ANIPCapability) -> str:
    """Build GraphQL argument list for a capability."""
    args = []
    for inp in cap.inputs:
        gql_type = _TYPE_MAP.get(inp.get("type", "string"), "String")
        required = inp.get("required", True)
        suffix = "!" if required else ""
        default = inp.get("default")
        default_str = ""
        if default is not None:
            if isinstance(default, int):
                default_str = f" = {default}"
            elif isinstance(default, str):
                default_str = f' = "{default}"'
            elif isinstance(default, bool):
                default_str = f" = {'true' if default else 'false'}"
        args.append(f"{_to_camel_case(inp['name'])}: {gql_type}{suffix}{default_str}")
    return ", ".join(args)


def _build_directives(cap: ANIPCapability) -> str:
    """Build custom ANIP directives for a field."""
    parts = []

    # @anipSideEffect
    se = f'@anipSideEffect(type: "{cap.side_effect}"'
    if cap.rollback_window is not None:
        se += f', rollbackWindow: "{cap.rollback_window}"'
    se += ")"
    parts.append(se)

    # @anipScope
    if cap.minimum_scope:
        scopes = ", ".join(f'"{s}"' for s in cap.minimum_scope)
        parts.append(f"@anipScope(scopes: [{scopes}])")

    # @anipCost
    if cap.cost:
        cost_parts = [f'certainty: "{cap.cost.get("certainty", "unknown")}"']
        financial = cap.cost.get("financial", {})
        if financial:
            if financial.get("currency"):
                cost_parts.append(f'currency: "{financial["currency"]}"')
            if financial.get("range_min") is not None:
                cost_parts.append(f'rangeMin: {financial["range_min"]}')
            if financial.get("range_max") is not None:
                cost_parts.append(f'rangeMax: {financial["range_max"]}')
        parts.append(f"@anipCost({', '.join(cost_parts)})")

    # @anipRequires
    if cap.requires:
        caps = ", ".join(
            f'"{_to_camel_case(r.get("capability", r))}"' for r in cap.requires
        )
        parts.append(f"@anipRequires(capabilities: [{caps}])")

    return "\n    ".join(parts)


def generate_schema(service: ANIPService) -> str:
    """Generate complete GraphQL SDL from ANIP capabilities."""
    queries = []
    mutations = []
    result_types = []

    for name, cap in service.capabilities.items():
        camel_name = _to_camel_case(name)
        result_type = f"{camel_name[0].upper()}{camel_name[1:]}Result"
        args = _build_args(cap)
        directives = _build_directives(cap)

        field_def = f"  {camel_name}({args}): {result_type}\n    {directives}"

        if cap.side_effect == "read":
            queries.append(field_def)
        else:
            mutations.append(field_def)

        result_types.append(
            f"type {result_type} {{\n"
            f"  success: Boolean!\n"
            f"  result: JSON\n"
            f"  costActual: CostActual\n"
            f"  failure: ANIPFailure\n"
            f"}}"
        )

    schema_parts = [
        # Directives
        'directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION',
        'directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION',
        'directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION',
        'directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION',
        '',
        # Scalar
        'scalar JSON',
        '',
        # Shared types
        'type CostActual {\n  financial: FinancialCost\n  varianceFromEstimate: String\n}',
        '',
        'type FinancialCost {\n  amount: Float\n  currency: String\n}',
        '',
        'type ANIPFailure {\n  type: String!\n  detail: String!\n  resolution: Resolution\n  retry: Boolean!\n}',
        '',
        'type Resolution {\n  action: String!\n  requires: String\n  grantableBy: String\n}',
        '',
    ]

    # Result types
    schema_parts.extend(result_types)
    schema_parts.append('')

    # Query type
    if queries:
        schema_parts.append("type Query {")
        schema_parts.extend(queries)
        schema_parts.append("}")
    else:
        schema_parts.append("type Query {\n  _empty: String\n}")
    schema_parts.append('')

    # Mutation type
    if mutations:
        schema_parts.append("type Mutation {")
        schema_parts.extend(mutations)
        schema_parts.append("}")

    return "\n".join(schema_parts)
```

**Step 2: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/translation.py
git commit -m "feat(graphql-py): add translation module (ANIP → GraphQL SDL)"
```

---

### Task 19: Server module (FastAPI + Ariadne)

**Files:**
- Create: `adapters/graphql-py/anip_graphql_adapter/server.py`

**Step 1: Write server.py**

```python
"""ANIP GraphQL Adapter Server.

Discovers any ANIP service and exposes it as a GraphQL endpoint
with custom @anip* directives.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

import uvicorn
from ariadne import (
    QueryType,
    MutationType,
    ScalarType,
    make_executable_schema,
)
from ariadne.asgi import GraphQL
from fastapi import FastAPI

from .config import AdapterConfig, load_config
from .discovery import ANIPService, discover_service
from .invocation import ANIPInvoker
from .translation import generate_schema, _to_camel_case

logger = logging.getLogger("anip-graphql-adapter")

json_scalar = ScalarType("JSON")


@json_scalar.serializer
def serialize_json(value: Any) -> Any:
    return value


@json_scalar.value_parser
def parse_json(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _build_resolver(
    capability_name: str, invoker: ANIPInvoker
):
    """Build a resolver function for an ANIP capability."""

    async def resolver(_obj: Any, _info: Any, **kwargs: Any) -> dict[str, Any]:
        # Convert camelCase kwargs back to snake_case for ANIP
        args = {}
        for key, value in kwargs.items():
            # Simple camelCase → snake_case
            snake_key = ""
            for c in key:
                if c.isupper():
                    snake_key += "_" + c.lower()
                else:
                    snake_key += c
            args[snake_key] = value

        result = await invoker.invoke(capability_name, args)

        response: dict[str, Any] = {
            "success": result.get("success", False),
            "result": result.get("result"),
            "failure": None,
            "costActual": None,
        }

        if result.get("cost_actual"):
            cost = result["cost_actual"]
            response["costActual"] = {
                "financial": cost.get("financial"),
                "varianceFromEstimate": cost.get("variance_from_estimate"),
            }

        if not result.get("success"):
            failure = result.get("failure", {})
            response["failure"] = {
                "type": failure.get("type", "unknown"),
                "detail": failure.get("detail", "no detail"),
                "retry": failure.get("retry", False),
                "resolution": None,
            }
            resolution = failure.get("resolution")
            if resolution:
                response["failure"]["resolution"] = {
                    "action": resolution.get("action", ""),
                    "requires": resolution.get("requires"),
                    "grantableBy": resolution.get("grantable_by"),
                }

        return response

    return resolver


async def build_app(config: AdapterConfig) -> FastAPI:
    """Discover ANIP service and build FastAPI + GraphQL app."""
    service = await discover_service(config.anip_service_url)
    logger.info(
        "Discovered %s with %d capabilities",
        service.base_url,
        len(service.capabilities),
    )

    invoker = ANIPInvoker(
        service=service,
        issuer=config.delegation.issuer,
        scope=config.delegation.scope,
        token_ttl_minutes=config.delegation.token_ttl_minutes,
    )
    await invoker.setup()
    logger.info("Delegation token registered")

    # Generate schema
    schema_sdl = generate_schema(service)
    logger.debug("Generated schema:\n%s", schema_sdl)

    # Build resolvers
    query = QueryType()
    mutation = MutationType()

    for name, cap in service.capabilities.items():
        camel_name = _to_camel_case(name)
        resolver = _build_resolver(name, invoker)

        if cap.side_effect == "read":
            query.set_field(camel_name, resolver)
        else:
            mutation.set_field(camel_name, resolver)

    bindables = [query, mutation, json_scalar]
    schema = make_executable_schema(schema_sdl, *bindables)

    app = FastAPI(
        title=f"ANIP GraphQL Adapter — {service.base_url}",
        version="0.1.0",
    )

    graphql_app = GraphQL(
        schema,
        debug=True,
        introspection=config.graphql.introspection,
    )

    app.mount(config.graphql.path, graphql_app)

    # Also serve schema SDL
    @app.get("/schema.graphql")
    async def get_schema():
        return schema_sdl

    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ANIP GraphQL Adapter: expose any ANIP service as GraphQL"
    )
    parser.add_argument("--config", "-c", help="Path to adapter.yaml config file")
    parser.add_argument("--url", "-u", help="ANIP service URL (overrides config)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(name)s %(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    config = load_config(args.config)
    if args.url:
        config.anip_service_url = args.url

    import asyncio

    app = asyncio.run(build_app(config))
    uvicorn.run(app, host="0.0.0.0", port=config.port)


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/server.py
git commit -m "feat(graphql-py): add FastAPI + Ariadne server with auto-generated resolvers"
```

---

### Task 20: Integration test (GraphQL Python)

**Files:**
- Create: `adapters/graphql-py/test_adapter.py`

**Step 1: Write test**

```python
"""Integration tests for the GraphQL adapter."""

import asyncio
import json
import sys

from anip_graphql_adapter.config import AdapterConfig, DelegationConfig
from anip_graphql_adapter.discovery import discover_service
from anip_graphql_adapter.translation import generate_schema, _to_camel_case


async def test_adapter(url: str):
    print(f"Testing GraphQL adapter against {url}\n")

    # 1. Discovery
    print("1. Discovering service...")
    service = await discover_service(url)
    print(f"   Protocol: {service.protocol}")
    print(f"   Capabilities: {list(service.capabilities.keys())}")

    # 2. Schema generation
    print("\n2. Generating GraphQL schema...")
    schema_sdl = generate_schema(service)
    print(f"   Schema length: {len(schema_sdl)} chars")
    assert "type Query" in schema_sdl
    assert "type Mutation" in schema_sdl
    assert "searchFlights" in schema_sdl
    assert "bookFlight" in schema_sdl
    assert "@anipSideEffect" in schema_sdl
    assert "@anipScope" in schema_sdl
    print("   Schema contains Query, Mutation, directives")

    # 3. Server test via httpx
    print("\n3. Testing server...")
    from anip_graphql_adapter.server import build_app
    from httpx import ASGITransport, AsyncClient

    config = AdapterConfig(
        anip_service_url=url,
        port=3099,
        delegation=DelegationConfig(
            issuer="human:test@example.com",
            scope=["travel.search", "travel.book:max_$500"],
        ),
    )
    app = await build_app(config)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Schema endpoint
        resp = await client.get("/schema.graphql")
        assert resp.status_code == 200
        print("   GET /schema.graphql: OK")

        # Search flights (Query)
        query = """
        query {
            searchFlights(origin: "SEA", destination: "SFO", date: "2026-03-10") {
                success
                result
                costActual { financial { amount currency } }
            }
        }
        """
        resp = await client.post(
            "/graphql",
            json={"query": query},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["data"]["searchFlights"]["success"] is True
        print(f"   searchFlights: success={data['data']['searchFlights']['success']}")

        # Book flight (Mutation)
        mutation = """
        mutation {
            bookFlight(flightNumber: "AA100", date: "2026-03-10", passengers: 1) {
                success
                result
                costActual { financial { amount currency } varianceFromEstimate }
                failure { type detail retry }
            }
        }
        """
        resp = await client.post(
            "/graphql",
            json={"query": mutation},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert data["data"]["bookFlight"]["success"] is True
        print(f"   bookFlight: success={data['data']['bookFlight']['success']}")

    print("\n--- All tests passed ---")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100"
    asyncio.run(test_adapter(url))
```

**Step 2: Run test**

Run: `cd adapters/graphql-py && pip install -e . && python test_adapter.py http://localhost:9100`
Expected: "All tests passed"

**Step 3: Commit**

```bash
git add adapters/graphql-py/test_adapter.py
git commit -m "feat(graphql-py): add integration test"
```

---

### Task 21: GraphQL-PY README

**Files:**
- Create: `adapters/graphql-py/README.md`

**Step 1: Write README** (analogous to REST-PY but for GraphQL)

**Step 2: Commit**

```bash
git add adapters/graphql-py/README.md
git commit -m "docs(graphql-py): add README"
```

---

## Phase 4: GraphQL TypeScript Adapter (`adapters/graphql-ts/`)

### Task 22: Project scaffolding

**Files:**
- Create: `adapters/graphql-ts/package.json`
- Create: `adapters/graphql-ts/tsconfig.json`
- Create: `adapters/graphql-ts/adapter.example.yaml`

**Step 1: Create package.json**

```json
{
  "name": "anip-graphql-adapter-ts",
  "version": "0.1.0",
  "description": "Generic GraphQL adapter for any ANIP-compliant service (TypeScript)",
  "type": "module",
  "scripts": {
    "build": "tsc",
    "dev": "tsx src/index.ts",
    "start": "node dist/index.js",
    "test": "tsx test-adapter.ts"
  },
  "dependencies": {
    "hono": "^4.6.0",
    "@hono/node-server": "^1.13.0",
    "graphql": "^16.9.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "tsx": "^4.15.0",
    "@types/node": "^22.0.0"
  }
}
```

**Step 2: Create tsconfig.json** (same as rest-ts)

**Step 3: Create adapter.example.yaml and commit**

```bash
cd adapters/graphql-ts && npm install
git add adapters/graphql-ts/package.json adapters/graphql-ts/tsconfig.json adapters/graphql-ts/adapter.example.yaml
git commit -m "feat(graphql-ts): scaffold GraphQL adapter project"
```

---

### Task 23: Config + Discovery + Invocation (TypeScript)

**Files:**
- Create: `adapters/graphql-ts/src/config.ts`
- Create: `adapters/graphql-ts/src/discovery.ts` (same as rest-ts)
- Create: `adapters/graphql-ts/src/invocation.ts` (same pattern, "graphql-adapter" prefix)

**Step 1: Write config.ts**

```typescript
export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  issuer: string;
  scope: string[];
  tokenTtlMinutes: number;
  graphqlPath: string;
}

export function loadConfig(): AdapterConfig {
  return {
    anipServiceUrl: process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
    port: Number(process.env.ANIP_ADAPTER_PORT ?? "3002"),
    issuer: process.env.ANIP_ISSUER ?? "human:user@example.com",
    scope: (process.env.ANIP_SCOPE ?? "*").split(","),
    tokenTtlMinutes: Number(process.env.ANIP_TOKEN_TTL ?? "60"),
    graphqlPath: process.env.ANIP_GRAPHQL_PATH ?? "/graphql",
  };
}
```

**Step 2: Copy discovery.ts from rest-ts (identical)**

**Step 3: Write invocation.ts** (same as rest-ts but with "graphql-adapter" prefix in token IDs)

**Step 4: Commit**

```bash
git add adapters/graphql-ts/src/config.ts adapters/graphql-ts/src/discovery.ts adapters/graphql-ts/src/invocation.ts
git commit -m "feat(graphql-ts): add config, discovery, invocation modules"
```

---

### Task 24: Translation module (TypeScript GraphQL)

**Files:**
- Create: `adapters/graphql-ts/src/translation.ts`

**Step 1: Write translation.ts**

```typescript
/**
 * ANIP → GraphQL translation layer.
 * Generates GraphQL schema string from ANIP capabilities.
 */

import type { ANIPCapability, ANIPService } from "./discovery.js";

const TYPE_MAP: Record<string, string> = {
  string: "String",
  integer: "Int",
  number: "Float",
  boolean: "Boolean",
  date: "String",
  airport_code: "String",
};

export function toCamelCase(snake: string): string {
  const parts = snake.split("_");
  return parts[0] + parts.slice(1).map((p) => p[0].toUpperCase() + p.slice(1)).join("");
}

function toSnakeCase(camel: string): string {
  return camel.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

export { toSnakeCase };

function buildArgs(cap: ANIPCapability): string {
  return cap.inputs
    .map((inp) => {
      const gqlType = TYPE_MAP[inp.type ?? "string"] ?? "String";
      const required = inp.required ?? true;
      const suffix = required ? "!" : "";
      let defaultStr = "";
      if (inp.default !== undefined && inp.default !== null) {
        if (typeof inp.default === "number") defaultStr = ` = ${inp.default}`;
        else if (typeof inp.default === "string") defaultStr = ` = "${inp.default}"`;
        else if (typeof inp.default === "boolean") defaultStr = ` = ${inp.default}`;
      }
      return `${toCamelCase(inp.name)}: ${gqlType}${suffix}${defaultStr}`;
    })
    .join(", ");
}

function buildDirectives(cap: ANIPCapability): string {
  const parts: string[] = [];

  let se = `@anipSideEffect(type: "${cap.sideEffect}"`;
  if (cap.rollbackWindow !== null) {
    se += `, rollbackWindow: "${cap.rollbackWindow}"`;
  }
  se += ")";
  parts.push(se);

  if (cap.minimumScope.length > 0) {
    const scopes = cap.minimumScope.map((s) => `"${s}"`).join(", ");
    parts.push(`@anipScope(scopes: [${scopes}])`);
  }

  if (cap.cost) {
    const costParts: string[] = [`certainty: "${(cap.cost as Record<string, unknown>).certainty ?? "unknown"}"`];
    const financial = (cap.cost as Record<string, Record<string, unknown>>).financial;
    if (financial) {
      if (financial.currency) costParts.push(`currency: "${financial.currency}"`);
      if (financial.range_min !== undefined) costParts.push(`rangeMin: ${financial.range_min}`);
      if (financial.range_max !== undefined) costParts.push(`rangeMax: ${financial.range_max}`);
    }
    parts.push(`@anipCost(${costParts.join(", ")})`);
  }

  if (cap.requires.length > 0) {
    const caps = cap.requires.map((r) => `"${toCamelCase(r.capability)}"`).join(", ");
    parts.push(`@anipRequires(capabilities: [${caps}])`);
  }

  return parts.join("\n    ");
}

export function generateSchema(service: ANIPService): string {
  const queries: string[] = [];
  const mutations: string[] = [];
  const resultTypes: string[] = [];

  for (const [name, cap] of service.capabilities) {
    const camelName = toCamelCase(name);
    const resultType = camelName[0].toUpperCase() + camelName.slice(1) + "Result";
    const args = buildArgs(cap);
    const directives = buildDirectives(cap);

    const fieldDef = `  ${camelName}(${args}): ${resultType}\n    ${directives}`;

    if (cap.sideEffect === "read") {
      queries.push(fieldDef);
    } else {
      mutations.push(fieldDef);
    }

    resultTypes.push(
      `type ${resultType} {\n  success: Boolean!\n  result: JSON\n  costActual: CostActual\n  failure: ANIPFailure\n}`
    );
  }

  const parts = [
    'directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION',
    'directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION',
    'directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION',
    'directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION',
    '',
    'scalar JSON',
    '',
    'type CostActual {\n  financial: FinancialCost\n  varianceFromEstimate: String\n}',
    '',
    'type FinancialCost {\n  amount: Float\n  currency: String\n}',
    '',
    'type ANIPFailure {\n  type: String!\n  detail: String!\n  resolution: Resolution\n  retry: Boolean!\n}',
    '',
    'type Resolution {\n  action: String!\n  requires: String\n  grantableBy: String\n}',
    '',
    ...resultTypes,
    '',
    queries.length > 0
      ? `type Query {\n${queries.join("\n")}\n}`
      : 'type Query {\n  _empty: String\n}',
    '',
    ...(mutations.length > 0 ? [`type Mutation {\n${mutations.join("\n")}\n}`] : []),
  ];

  return parts.join("\n");
}
```

**Step 2: Commit**

```bash
git add adapters/graphql-ts/src/translation.ts
git commit -m "feat(graphql-ts): add translation module (ANIP → GraphQL SDL)"
```

---

### Task 25: Server module (Hono + graphql-js)

**Files:**
- Create: `adapters/graphql-ts/src/index.ts`

**Step 1: Write index.ts**

```typescript
/**
 * ANIP GraphQL Adapter Server (TypeScript).
 */

import { Hono } from "hono";
import { serve } from "@hono/node-server";
import { buildSchema, graphql } from "graphql";
import { loadConfig } from "./config.js";
import { discoverService } from "./discovery.js";
import { ANIPInvoker } from "./invocation.js";
import { generateSchema, toCamelCase, toSnakeCase } from "./translation.js";

async function main() {
  const config = loadConfig();
  console.error(`[anip-graphql-adapter] Discovering ANIP service at ${config.anipServiceUrl}`);

  const service = await discoverService(config.anipServiceUrl);
  console.error(`[anip-graphql-adapter] Discovered ${service.capabilities.size} capabilities`);

  const invoker = new ANIPInvoker(service, {
    issuer: config.issuer,
    scope: config.scope,
    tokenTtlMinutes: config.tokenTtlMinutes,
  });
  await invoker.setup();
  console.error("[anip-graphql-adapter] Delegation token registered");

  const schemaSdl = generateSchema(service);
  const schema = buildSchema(schemaSdl);

  // Build root resolvers
  const rootValue: Record<string, unknown> = {};

  for (const [name, _cap] of service.capabilities) {
    const camelName = toCamelCase(name);
    rootValue[camelName] = async (args: Record<string, unknown>) => {
      // Convert camelCase args back to snake_case
      const snakeArgs: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(args)) {
        snakeArgs[toSnakeCase(key)] = val;
      }

      const result = await invoker.invoke(name, snakeArgs);

      const response: Record<string, unknown> = {
        success: result.success ?? false,
        result: result.result ?? null,
        costActual: null,
        failure: null,
      };

      if (result.cost_actual) {
        const cost = result.cost_actual as Record<string, unknown>;
        response.costActual = {
          financial: cost.financial ?? null,
          varianceFromEstimate: (cost as Record<string, unknown>).variance_from_estimate ?? null,
        };
      }

      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        response.failure = {
          type: failure?.type ?? "unknown",
          detail: failure?.detail ?? "no detail",
          retry: failure?.retry ?? false,
          resolution: null,
        };
        const resolution = failure?.resolution as Record<string, unknown> | undefined;
        if (resolution) {
          (response.failure as Record<string, unknown>).resolution = {
            action: resolution.action ?? "",
            requires: resolution.requires ?? null,
            grantableBy: resolution.grantable_by ?? null,
          };
        }
      }

      return response;
    };
  }

  const app = new Hono();

  // GraphQL endpoint
  app.post(config.graphqlPath, async (c) => {
    const body = await c.req.json();
    const { query, variables, operationName } = body;

    const result = await graphql({
      schema,
      source: query,
      rootValue,
      variableValues: variables,
      operationName,
    });

    return c.json(result);
  });

  // GET for GraphQL Playground / introspection
  app.get(config.graphqlPath, async (c) => {
    const query = c.req.query("query");
    if (query) {
      const result = await graphql({ schema, source: query, rootValue });
      return c.json(result);
    }
    // Return simple playground HTML
    return c.html(`<!DOCTYPE html>
<html>
<head><title>ANIP GraphQL Adapter</title></head>
<body>
<h1>ANIP GraphQL Adapter</h1>
<p>POST queries to ${config.graphqlPath}</p>
<p><a href="/schema.graphql">View Schema</a></p>
</body>
</html>`);
  });

  // Schema SDL endpoint
  app.get("/schema.graphql", (c) => {
    return c.text(schemaSdl);
  });

  const port = config.port;
  console.error(`[anip-graphql-adapter] Serving on http://localhost:${port}`);
  serve({ fetch: app.fetch, port });
}

main().catch((err) => {
  console.error("[anip-graphql-adapter] Fatal:", err);
  process.exit(1);
});
```

**Step 2: Commit**

```bash
git add adapters/graphql-ts/src/index.ts
git commit -m "feat(graphql-ts): add Hono + graphql-js server"
```

---

### Task 26: Integration test (GraphQL TypeScript)

**Files:**
- Create: `adapters/graphql-ts/test-adapter.ts`

**Step 1: Write test-adapter.ts**

```typescript
import { discoverService } from "./src/discovery.js";
import { ANIPInvoker } from "./src/invocation.js";
import { generateSchema, toCamelCase } from "./src/translation.js";

const url = process.argv[2] ?? "http://localhost:9100";

async function main() {
  console.log(`Testing GraphQL adapter against ${url}\n`);

  // 1. Discovery
  console.log("1. Discovering service...");
  const service = await discoverService(url);
  console.log(`   Capabilities: ${Array.from(service.capabilities.keys()).join(", ")}`);

  // 2. Schema generation
  console.log("\n2. Generating GraphQL schema...");
  const schema = generateSchema(service);
  console.log(`   Schema length: ${schema.length} chars`);

  if (!schema.includes("type Query")) throw new Error("Missing Query type");
  if (!schema.includes("type Mutation")) throw new Error("Missing Mutation type");
  if (!schema.includes("searchFlights")) throw new Error("Missing searchFlights");
  if (!schema.includes("bookFlight")) throw new Error("Missing bookFlight");
  if (!schema.includes("@anipSideEffect")) throw new Error("Missing directive");
  console.log("   Schema valid: Query, Mutation, directives present");

  // 3. Invocation
  console.log("\n3. Testing invocation...");
  const invoker = new ANIPInvoker(service, {
    issuer: "human:test@example.com",
    scope: ["travel.search", "travel.book:max_$500"],
    tokenTtlMinutes: 60,
  });
  await invoker.setup();

  const searchResult = await invoker.invoke("search_flights", {
    origin: "SEA",
    destination: "SFO",
    date: "2026-03-10",
  });
  console.log(`   search_flights: success=${searchResult.success}`);

  const bookResult = await invoker.invoke("book_flight", {
    flight_number: "AA100",
    date: "2026-03-10",
    passengers: 1,
  });
  console.log(`   book_flight: success=${bookResult.success}`);

  console.log("\n--- All tests passed ---");
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
```

**Step 2: Run test**

Run: `cd adapters/graphql-ts && npm install && npx tsx test-adapter.ts http://localhost:9100`
Expected: "All tests passed"

**Step 3: Commit**

```bash
git add adapters/graphql-ts/test-adapter.ts
git commit -m "feat(graphql-ts): add integration test"
```

---

### Task 27: GraphQL-TS README

**Files:**
- Create: `adapters/graphql-ts/README.md`

**Step 1: Write README**

**Step 2: Commit**

```bash
git add adapters/graphql-ts/README.md
git commit -m "docs(graphql-ts): add README"
```

---

## Phase 5: Cross-Validation & README Updates

### Task 28: Cross-validate all 4 adapters against both ANIP servers

**Step 1: Run each adapter's test against Python ANIP server (port 9100)**

```bash
cd adapters/rest-py && python test_adapter.py http://localhost:9100
cd adapters/rest-ts && npx tsx test-adapter.ts http://localhost:9100
cd adapters/graphql-py && python test_adapter.py http://localhost:9100
cd adapters/graphql-ts && npx tsx test-adapter.ts http://localhost:9100
```

Expected: All pass.

**Step 2: Run each adapter's test against TypeScript ANIP server (port 8001)**

```bash
cd adapters/rest-py && python test_adapter.py http://localhost:8001
cd adapters/rest-ts && npx tsx test-adapter.ts http://localhost:8001
cd adapters/graphql-py && python test_adapter.py http://localhost:8001
cd adapters/graphql-ts && npx tsx test-adapter.ts http://localhost:8001
```

Expected: All 8 combinations pass (4 adapters × 2 servers).

---

### Task 29: Update project README

**Files:**
- Modify: `README.md`

**Step 1: Add REST and GraphQL adapter entries to the "What exists today" section**

Add after the MCP adapter lines:
```markdown
- [REST/OpenAPI adapter — Python](adapters/rest-py/) — expose ANIP as REST with auto-generated OpenAPI spec
- [REST/OpenAPI adapter — TypeScript](adapters/rest-ts/) — same adapter, TypeScript/Hono implementation
- [GraphQL adapter — Python](adapters/graphql-py/) — expose ANIP as GraphQL with custom @anip* directives
- [GraphQL adapter — TypeScript](adapters/graphql-ts/) — same adapter, TypeScript/Hono implementation
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add REST/OpenAPI and GraphQL adapters to README"
```

---

### Task 30: Final integration commit

**Step 1: Run full cross-validation one more time**

**Step 2: Create PR with all changes**

```bash
git push -u origin feat/rest-graphql-adapters
gh pr create --title "feat: REST/OpenAPI + GraphQL adapters (Python + TypeScript)" --body "..."
```
