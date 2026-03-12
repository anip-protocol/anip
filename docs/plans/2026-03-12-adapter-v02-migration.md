# REST/GraphQL Adapter v0.2 Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all four REST/GraphQL adapters from v0.1 declaration mode (adapter-constructed tokens) to v0.2 signed mode (caller-provided credentials), making them stateless protocol bridges.

**Architecture:** Adapters become credential pass-through bridges. Callers provide either a signed ANIP delegation token (`X-ANIP-Token: <token>`) or an API key (`X-ANIP-API-Key: <key>`). Token takes precedence. The adapter forwards credentials to the ANIP server — it holds no tokens, no standing authority, no root delegation chain.

**Tech Stack:** Python (FastAPI, httpx, Ariadne), TypeScript (Hono, graphql-js), ANIP v0.2 signed token protocol

**Reference implementations:** The MCP adapters (already migrated) serve as the pattern:
- Python: `adapters/mcp-py/anip_mcp_bridge/invocation.py` — shows API-key issuance flow
- TypeScript: `adapters/mcp-ts/src/invocation.ts` — shows API-key issuance flow + `{"issued": false}` handling

**Important design notes:**

1. **Header choice:** We use `X-ANIP-Token` (NOT `Authorization: Bearer`) for ANIP delegation tokens. This avoids collisions with upstream auth middleware or API gateways that may already use `Authorization: Bearer` for their own JWTs. `X-ANIP-API-Key` is used for the convenience path.

2. **API-key path authority semantics:** The API-key convenience path issues tokens scoped to `capability.minimum_scope`, which is the broadest scope the capability accepts. This may be wider than what a pre-issued token would express (e.g., `travel.book` vs `travel.book:max_$200`). Callers who need fine-grained constraints (budget limits, task-specific purpose binding) MUST use the token path with a pre-issued delegation token. The API-key path is explicitly documented as a "maximum authority for this capability" convenience — not a replacement for proper delegation.

3. **API-key path audit identity:** In API-key mode, issued tokens use adapter-specific subjects (e.g., `adapter:anip-rest-adapter`). The audit `subject` field will show the adapter identity, while `root_principal` correctly reflects the human authenticated by the API key. This means the convenience path does NOT preserve full caller identity in the subject — only `root_principal` traces back to the caller. Callers who need subject-level identity attribution must use the token path.

---

## Task 1: Rewrite REST-PY `invocation.py` — Remove Token Construction, Add Credential Pass-Through

**Files:**
- Modify: `adapters/rest-py/anip_rest_adapter/invocation.py` (complete rewrite)
- Modify: `adapters/rest-py/anip_rest_adapter/server.py:72-80` (invoker setup)
- Modify: `adapters/rest-py/anip_rest_adapter/server.py:103-134` (route handlers — pass request headers)

**Step 1: Rewrite `invocation.py`**

Replace the entire `ANIPInvoker` class. Remove `setup()`, root token registration, capability token construction, scope narrowing, token TTL. Replace with two credential paths.

```python
"""ANIP capability invocation from REST requests.

Passes caller-provided credentials (delegation token or API key)
through to the ANIP service. The adapter holds no tokens of its own.
"""

from __future__ import annotations

from typing import Any

import httpx

from .discovery import ANIPService


class CredentialError(Exception):
    """Raised when no valid credentials are provided."""


class IssuanceError(Exception):
    """Raised when API-key token issuance is denied."""

    def __init__(self, error: str):
        self.error = error
        super().__init__(f"Token issuance denied: {error}")


class ANIPInvoker:
    """Invokes ANIP capabilities by forwarding caller credentials.

    Supports two credential modes:
    1. Delegation token (preferred): caller provides a signed ANIP token
    2. API key (convenience): caller provides an API key, adapter requests
       a short-lived token scoped to the specific capability
    """

    def __init__(self, service: ANIPService):
        self.service = service

    async def invoke(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        *,
        token: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Invoke an ANIP capability using caller-provided credentials.

        Args:
            capability_name: The ANIP capability to invoke.
            arguments: Parameters for the capability.
            token: A signed ANIP delegation token (preferred).
            api_key: An ANIP API key for adapter-mediated issuance.

        Returns:
            The raw ANIP response dict.

        Raises:
            CredentialError: If neither token nor api_key is provided.
            IssuanceError: If API-key token issuance is denied.
        """
        if token is not None:
            return await self._invoke_with_token(capability_name, arguments, token)
        elif api_key is not None:
            return await self._invoke_with_api_key(capability_name, arguments, api_key)
        else:
            raise CredentialError(
                "No credentials provided. Include either "
                "'X-ANIP-Token: <anip-token>' or "
                "'X-ANIP-API-Key: <key>' header."
            )

    async def _invoke_with_token(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        token: str,
    ) -> dict[str, Any]:
        """Invoke directly with a caller-provided signed token."""
        invoke_url = self.service.endpoints["invoke"].replace(
            "{capability}", capability_name
        )
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                invoke_url,
                json={
                    "token": token,
                    "parameters": arguments,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def _invoke_with_api_key(
        self,
        capability_name: str,
        arguments: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Request a capability token via API key, then invoke."""
        # Determine narrow scope for this capability
        capability = self.service.capabilities.get(capability_name)
        cap_scope = ["*"]
        if capability and capability.minimum_scope:
            cap_scope = capability.minimum_scope

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Request a signed token
            token_resp = await client.post(
                self.service.endpoints["tokens"],
                json={
                    "subject": "adapter:anip-rest-adapter",
                    "scope": cap_scope,
                    "capability": capability_name,
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            if not token_data.get("issued"):
                raise IssuanceError(token_data.get("error", "unknown error"))

            jwt_str = token_data["token"]

            # Step 2: Invoke with the signed token
            invoke_url = self.service.endpoints["invoke"].replace(
                "{capability}", capability_name
            )
            resp = await client.post(
                invoke_url,
                json={
                    "token": jwt_str,
                    "parameters": arguments,
                },
            )
            resp.raise_for_status()
            return resp.json()
```

**Step 2: Update `server.py` — invoker setup and route handlers**

In `build_app()`, replace the invoker setup (lines 72-80) with:

```python
    # Step 2: Set up the invoker (stateless — no token registration)
    invoker = ANIPInvoker(service=service)
    logger.info("Invoker ready (pass-through mode)")
```

Update `_register_route()` to extract credentials from request headers and pass them to `invoke()`:

```python
def _register_route(
    app: FastAPI,
    route: RESTRoute,
    invoker: ANIPInvoker,
) -> None:
    """Register a single REST route for an ANIP capability."""
    cap = route.capability

    if route.method == "GET":

        @app.get(route.path, name=route.capability_name)
        async def handle_get(
            request: Request,
            _cap_name: str = route.capability_name,
            _cap: Any = cap,
        ) -> JSONResponse:
            arguments = dict(request.query_params)
            arguments = _convert_param_types(arguments, _cap)
            token, api_key = _extract_credentials(request)
            return await _invoke_and_respond(
                invoker, _cap_name, arguments, _cap,
                token=token, api_key=api_key,
            )

    else:

        @app.post(route.path, name=route.capability_name)
        async def handle_post(
            request: Request,
            _cap_name: str = route.capability_name,
            _cap: Any = cap,
        ) -> JSONResponse:
            body = await request.json()
            token, api_key = _extract_credentials(request)
            return await _invoke_and_respond(
                invoker, _cap_name, body, _cap,
                token=token, api_key=api_key,
            )
```

Add the credential extraction helper and update `_invoke_and_respond`:

```python
def _extract_credentials(request: Request) -> tuple[str | None, str | None]:
    """Extract ANIP credentials from request headers.

    Returns (token, api_key). Token takes precedence if both are present.
    """
    token: str | None = None
    api_key: str | None = None

    token = request.headers.get("x-anip-token")
    api_key = request.headers.get("x-anip-api-key")

    return token, api_key


async def _invoke_and_respond(
    invoker: ANIPInvoker,
    capability_name: str,
    arguments: dict[str, Any],
    cap: Any,
    *,
    token: str | None = None,
    api_key: str | None = None,
) -> JSONResponse:
    """Invoke an ANIP capability and map the response to HTTP status codes."""
    from .invocation import CredentialError, IssuanceError

    try:
        result = await invoker.invoke(
            capability_name, arguments,
            token=token, api_key=api_key,
        )
    except CredentialError as e:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "failure": {
                    "type": "missing_credentials",
                    "detail": str(e),
                    "retry": False,
                },
            },
        )
    except IssuanceError as e:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "failure": {
                    "type": "token_issuance_denied",
                    "detail": e.error,
                    "retry": False,
                },
            },
        )
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

    # ... rest of response building stays the same (lines 189-214)
```

**Step 3: Verify the changes compile**

Run: `cd adapters/rest-py && python -c "from anip_rest_adapter.invocation import ANIPInvoker; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/invocation.py adapters/rest-py/anip_rest_adapter/server.py
git commit -m "feat(rest-py): migrate invocation to v0.2 credential pass-through

Remove root token registration and per-request token construction.
Add two credential paths: direct delegation token and API-key issuance.
Adapter is now a stateless protocol bridge."
```

---

## Task 2: Update REST-PY Config — Remove Delegation Fields

**Files:**
- Modify: `adapters/rest-py/anip_rest_adapter/config.py`
- Modify: `adapters/rest-py/adapter.example.yaml`

**Step 1: Simplify config**

Remove the `DelegationConfig` dataclass entirely. Remove `delegation` field from `AdapterConfig`. Remove all delegation-related config loading (issuer, scope, token_ttl_minutes env vars, YAML parsing).

In `config.py`, the result should be:

```python
"""Adapter configuration — load from YAML or environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RouteOverride:
    """Override for a capability's REST route."""

    path: str
    method: str


@dataclass
class AdapterConfig:
    """Full adapter configuration."""

    anip_service_url: str = "http://localhost:8000"
    port: int = 3001
    routes: dict[str, RouteOverride] = field(default_factory=dict)


def load_config(config_path: str | None = None) -> AdapterConfig:
    """Load adapter configuration from YAML file or environment variables.

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
        )

    with open(config_path) as f:
        data = yaml.safe_load(f)

    routes: dict[str, RouteOverride] = {}
    for cap_name, route_data in data.get("routes", {}).items():
        routes[cap_name] = RouteOverride(
            path=route_data["path"],
            method=route_data.get("method", "POST").upper(),
        )

    return AdapterConfig(
        anip_service_url=data.get(
            "anip_service_url", "http://localhost:8000"
        ),
        port=data.get("port", 3001),
        routes=routes,
    )
```

**Step 2: Update `adapter.example.yaml`**

```yaml
# ANIP REST Adapter Configuration
#
# Copy to adapter.yaml and adjust for your setup.

# The ANIP service to expose as REST endpoints
anip_service_url: "http://localhost:8000"

# REST server port
port: 3001

# Authentication: callers must provide credentials via HTTP headers:
#   X-ANIP-Token: <signed-anip-token>  (preferred)
#   X-ANIP-API-Key: <api-key>           (convenience)
#
# The adapter is a stateless bridge — it holds no tokens of its own.

# Route overrides (optional)
# Override default path/method for specific capabilities
# routes:
#   search_flights:
#     path: "/api/flights/search"
#     method: "GET"
#   book_flight:
#     path: "/api/flights/book"
#     method: "POST"
```

**Step 3: Update `server.py` build_app to remove delegation references**

In `build_app()`, remove the line that references `config.delegation`. The invoker constructor should just be `ANIPInvoker(service=service)` (already done in Task 1). Also remove the `DelegationConfig` import from `server.py` if present.

**Step 4: Verify**

Run: `cd adapters/rest-py && python -c "from anip_rest_adapter.config import load_config; c = load_config(); print(c)"`
Expected: Output showing `AdapterConfig(anip_service_url='http://localhost:8000', port=3001, routes={})`

**Step 5: Commit**

```bash
git add adapters/rest-py/anip_rest_adapter/config.py adapters/rest-py/adapter.example.yaml adapters/rest-py/anip_rest_adapter/server.py
git commit -m "feat(rest-py): remove delegation config, adapter holds no identity

DelegationConfig removed. Config now only has service URL, port, and
route overrides. Credentials come from caller headers."
```

---

## Task 3: Update REST-PY Tests

**Files:**
- Modify: `adapters/rest-py/test_adapter.py`

**Step 1: Update test_config_defaults**

Remove assertions about delegation fields (issuer, scope, token_ttl_minutes):

```python
def test_config_defaults() -> None:
    print("\n--- Config defaults ---")
    from anip_rest_adapter.config import AdapterConfig, load_config

    cfg = AdapterConfig()
    _assert(cfg.anip_service_url == "http://localhost:8000", "default service URL")
    _assert(cfg.port == 3001, "default port")
    _assert(cfg.routes == {}, "default routes empty")
```

**Step 2: Update test_invocation**

Change `ANIPInvoker` construction and `invoke()` calls to use API key:

```python
async def test_invocation(anip_url: str) -> None:
    print("\n--- Invocation ---")
    from anip_rest_adapter.discovery import discover_service
    from anip_rest_adapter.invocation import ANIPInvoker

    service = await discover_service(anip_url)
    invoker = ANIPInvoker(service=service)

    # Search flights (using API key)
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

    # Book flight (using API key)
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

    # --- Token path tests ---
    # First, obtain a signed token via the ANIP server directly
    import httpx as _httpx

    async with _httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            service.endpoints["tokens"],
            json={
                "subject": "test:token-path",
                "scope": ["travel.search"],
                "capability": "search_flights",
            },
            headers={"Authorization": "Bearer demo-human-key"},
        )
        token_data = token_resp.json()
        _assert(token_data.get("issued") is True, "token issued for token-path test")
        jwt_token = token_data["token"]

    # Search flights using the pre-issued token
    result = await invoker.invoke(
        "search_flights",
        {
            "origin": "SEA",
            "destination": "SFO",
            "date": "2026-03-10",
            "passengers": 1,
        },
        token=jwt_token,
    )
    _assert(isinstance(result, dict), "token-path search_flights returns dict")
    _assert(result.get("success") is True, "token-path search_flights succeeds")

    # Test missing credentials raises CredentialError
    from anip_rest_adapter.invocation import CredentialError

    try:
        await invoker.invoke("search_flights", {"origin": "SEA", "destination": "SFO", "date": "2026-03-10", "passengers": 1})
        _fail("missing credentials should raise CredentialError")
    except CredentialError:
        _ok("missing credentials raises CredentialError")
```

**Step 3: Update test_server**

Add API key header to HTTP requests through the test app:

```python
async def test_server(anip_url: str) -> None:
    print("\n--- Server (ASGI) ---")
    from anip_rest_adapter.config import AdapterConfig
    from anip_rest_adapter.server import build_app

    config = AdapterConfig(anip_service_url=anip_url)
    app = await build_app(config)

    # Pre-issue a signed token from the real ANIP server (outside ASGI transport)
    async with httpx.AsyncClient(timeout=30) as real_client:
        token_resp = await real_client.post(
            f"{anip_url}/anip/tokens",
            json={"subject": "test:token-path", "scope": ["travel.search"], "capability": "search_flights"},
            headers={"Authorization": "Bearer demo-human-key"},
        )
        _assert(token_resp.status_code == 200, "pre-issued token request succeeds")
        jwt_token = token_resp.json()["token"]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-ANIP-API-Key": "demo-human-key"}

        # OpenAPI spec endpoint (no auth needed)
        resp = await client.get("/openapi.json")
        _assert(resp.status_code == 200, "GET /openapi.json returns 200")

        # GET search_flights (with API key)
        resp = await client.get(
            "/api/search_flights",
            params={
                "origin": "SEA",
                "destination": "SFO",
                "date": "2026-03-10",
                "passengers": "1",
            },
            headers=headers,
        )
        _assert(resp.status_code == 200, "GET /api/search_flights returns 200")
        data = resp.json()
        _assert(data.get("success") is True, "search_flights response success")

        # Test X-ANIP-Token path (preferred) using pre-issued token
        resp = await client.get(
            "/api/search_flights",
            params={"origin": "SEA", "destination": "SFO", "date": "2026-03-10", "passengers": "1"},
            headers={"X-ANIP-Token": jwt_token},
        )
        _assert(resp.status_code == 200, "X-ANIP-Token path returns 200")
        data = resp.json()
        _assert(data.get("success") is True, "X-ANIP-Token path succeeds")

        # Test 401 without credentials
        resp = await client.get(
            "/api/search_flights",
            params={"origin": "SEA", "destination": "SFO", "date": "2026-03-10", "passengers": "1"},
        )
        _assert(resp.status_code == 401, "missing credentials returns 401")

        # POST book_flight
        search_resp = await client.get(
            "/api/search_flights",
            params={"origin": "SEA", "destination": "SFO", "date": "2026-03-10", "passengers": "1"},
            headers=headers,
        )
        flights = search_resp.json().get("result", {}).get("flights", [])
        flight_number = flights[0]["flight_number"] if flights else "UA100"

        resp = await client.post(
            "/api/book_flight",
            json={"flight_number": flight_number, "date": "2026-03-10", "passengers": 1},
            headers=headers,
        )
        _assert(resp.status_code == 200, "POST /api/book_flight returns 200")

        # Docs endpoint
        resp = await client.get("/docs")
        _assert(resp.status_code == 200, "GET /docs returns 200")
```

**Step 4: Commit**

```bash
git add adapters/rest-py/test_adapter.py
git commit -m "test(rest-py): update tests for v0.2 credential pass-through"
```

---

## Task 4: Rewrite REST-TS `invocation.ts` — Same Pattern as REST-PY

**Files:**
- Modify: `adapters/rest-ts/src/invocation.ts` (complete rewrite)

**Step 1: Rewrite `invocation.ts`**

```typescript
/**
 * ANIP capability invocation from REST requests.
 *
 * Passes caller-provided credentials (delegation token or API key)
 * through to the ANIP service. The adapter holds no tokens of its own.
 */

import type { ANIPService } from "./discovery.js";

export class CredentialError extends Error {
  constructor() {
    super(
      "No credentials provided. Include either " +
      "'X-ANIP-Token: <anip-token>' or " +
      "'X-ANIP-API-Key: <key>' header."
    );
    this.name = "CredentialError";
  }
}

export class IssuanceError extends Error {
  readonly error: string;
  constructor(error: string) {
    super(`Token issuance denied: ${error}`);
    this.name = "IssuanceError";
    this.error = error;
  }
}

export class ANIPInvoker {
  private service: ANIPService;

  constructor(service: ANIPService) {
    this.service = service;
  }

  async invoke(
    capabilityName: string,
    args: Record<string, unknown>,
    opts: { token?: string; apiKey?: string },
  ): Promise<Record<string, unknown>> {
    if (opts.token) {
      return this.invokeWithToken(capabilityName, args, opts.token);
    } else if (opts.apiKey) {
      return this.invokeWithApiKey(capabilityName, args, opts.apiKey);
    } else {
      throw new CredentialError();
    }
  }

  private async invokeWithToken(
    capabilityName: string,
    args: Record<string, unknown>,
    token: string,
  ): Promise<Record<string, unknown>> {
    const invokeUrl = this.service.endpoints.invoke.replace(
      "{capability}",
      capabilityName,
    );
    const resp = await fetch(invokeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, parameters: args }),
    });
    if (!resp.ok) {
      throw new Error(`Invocation failed: ${resp.status}`);
    }
    return (await resp.json()) as Record<string, unknown>;
  }

  private async invokeWithApiKey(
    capabilityName: string,
    args: Record<string, unknown>,
    apiKey: string,
  ): Promise<Record<string, unknown>> {
    // Determine narrow scope
    const capability = this.service.capabilities.get(capabilityName);
    let capScope = ["*"];
    if (capability && capability.minimumScope.length > 0) {
      capScope = capability.minimumScope;
    }

    // Step 1: Request a signed token
    const tokenResp = await fetch(this.service.endpoints.tokens, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        subject: "adapter:anip-rest-adapter-ts",
        scope: capScope,
        capability: capabilityName,
      }),
    });
    if (!tokenResp.ok) {
      throw new Error(`Token request failed: ${tokenResp.status}`);
    }
    const tokenData = (await tokenResp.json()) as Record<string, unknown>;
    if (!tokenData.issued) {
      throw new IssuanceError(
        (tokenData.error as string) ?? "unknown error",
      );
    }
    const jwt = tokenData.token as string;

    // Step 2: Invoke with the signed token
    return this.invokeWithToken(capabilityName, args, jwt);
  }
}
```

**Step 2: Verify**

Run: `cd adapters/rest-ts && npx tsc --noEmit src/invocation.ts`
Expected: No errors (or only errors from missing discovery types, which is fine)

**Step 3: Commit**

```bash
git add adapters/rest-ts/src/invocation.ts
git commit -m "feat(rest-ts): migrate invocation to v0.2 credential pass-through"
```

---

## Task 5: Update REST-TS Config and Server — Remove Delegation, Add Credential Extraction

**Files:**
- Modify: `adapters/rest-ts/src/config.ts`
- Modify: `adapters/rest-ts/src/index.ts`
- Modify: `adapters/rest-ts/adapter.example.yaml`

**Step 1: Simplify `config.ts`**

Remove `DelegationConfig` interface. Remove `delegation` from `AdapterConfig`. Remove all delegation-related loading:

```typescript
/**
 * Adapter configuration — from YAML file, environment variables, or defaults.
 */

import { readFileSync, existsSync } from "node:fs";
import { parse as parseYaml } from "yaml";

export interface RouteOverride {
  path: string;
  method: string;
}

export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  routes: Record<string, RouteOverride>;
}

export function loadConfig(configPath?: string): AdapterConfig {
  let path = configPath ?? process.env.ANIP_ADAPTER_CONFIG;
  if (path && !existsSync(path)) {
    path = undefined;
  }
  if (!path && existsSync("adapter.yaml")) {
    path = "adapter.yaml";
  }

  if (!path) {
    return {
      anipServiceUrl:
        process.env.ANIP_SERVICE_URL ?? "http://localhost:8000",
      port: Number(process.env.ANIP_ADAPTER_PORT ?? "3001"),
      routes: {},
    };
  }

  const raw = readFileSync(path, "utf-8");
  const data = parseYaml(raw) as Record<string, unknown>;

  const routes: Record<string, RouteOverride> = {};
  const routesData = (data.routes ?? {}) as Record<
    string,
    Record<string, string>
  >;
  for (const [capName, routeData] of Object.entries(routesData)) {
    routes[capName] = {
      path: routeData.path,
      method: (routeData.method ?? "POST").toUpperCase(),
    };
  }

  return {
    anipServiceUrl:
      (data.anip_service_url as string) ?? "http://localhost:8000",
    port: Number(data.port ?? 3001),
    routes,
  };
}
```

**Step 2: Update `index.ts` — credential extraction and pass-through**

In `buildApp()`, replace invoker setup (lines 138-145):

```typescript
  // Step 2: Set up the invoker (stateless — no token registration)
  const invoker = new ANIPInvoker(service);
  console.error("[anip-rest-adapter] Invoker ready (pass-through mode)");
```

Add credential extraction helper:

```typescript
function extractCredentials(c: { req: { header: (name: string) => string | undefined } }): {
  token?: string;
  apiKey?: string;
} {
  const token = c.req.header("x-anip-token") ?? undefined;
  const apiKey = c.req.header("x-anip-api-key") ?? undefined;
  return { token, apiKey };
}
```

Update `registerRoute()` to extract and pass credentials:

```typescript
function registerRoute(
  app: Hono,
  route: RESTRoute,
  invoker: ANIPInvoker
): void {
  const capName = route.capabilityName;
  const cap = route.capability;

  if (route.method === "GET") {
    app.get(route.path, async (c) => {
      const queryParams: Record<string, string> = {};
      for (const [k, v] of Object.entries(c.req.query())) {
        if (v !== undefined) queryParams[k] = v;
      }
      const args = convertParamTypes(queryParams, cap);
      const creds = extractCredentials(c);
      const { status, body } = await invokeAndRespond(
        invoker, capName, args, cap, creds,
      );
      return c.json(body, status as 200);
    });
  } else {
    app.post(route.path, async (c) => {
      const body = await c.req.json();
      const creds = extractCredentials(c);
      const { status, body: responseBody } = await invokeAndRespond(
        invoker, capName, body, cap, creds,
      );
      return c.json(responseBody, status as 200);
    });
  }
}
```

Update `invokeAndRespond()` signature and error handling:

```typescript
import { ANIPInvoker, CredentialError, IssuanceError } from "./invocation.js";

async function invokeAndRespond(
  invoker: ANIPInvoker,
  capabilityName: string,
  args: Record<string, unknown>,
  cap: ANIPCapability,
  creds: { token?: string; apiKey?: string },
): Promise<{ status: number; body: Record<string, unknown> }> {
  let result: Record<string, unknown>;
  try {
    result = await invoker.invoke(capabilityName, args, creds);
  } catch (e) {
    if (e instanceof CredentialError) {
      return {
        status: 401,
        body: {
          success: false,
          failure: { type: "missing_credentials", detail: e.message, retry: false },
        },
      };
    }
    if (e instanceof IssuanceError) {
      return {
        status: 403,
        body: {
          success: false,
          failure: { type: "token_issuance_denied", detail: e.error, retry: false },
        },
      };
    }
    return {
      status: 502,
      body: {
        success: false,
        failure: {
          type: "adapter_error",
          detail: e instanceof Error ? e.message : String(e),
          retry: true,
        },
      },
    };
  }

  // ... rest of response building stays the same (lines 89-121)
```

**Step 3: Update `adapter.example.yaml`** — same content as REST-PY example yaml (without delegation section).

**Step 4: Commit**

```bash
git add adapters/rest-ts/src/config.ts adapters/rest-ts/src/index.ts adapters/rest-ts/adapter.example.yaml
git commit -m "feat(rest-ts): remove delegation config, add credential extraction

Adapter is now a stateless bridge. Caller provides credentials
via X-ANIP-Token or X-ANIP-API-Key headers."
```

---

## Task 6: Update REST-TS Tests

**Files:**
- Modify: `adapters/rest-ts/test-adapter.ts`

**Step 1: Read current test file**

Read `adapters/rest-ts/test-adapter.ts` to understand the test structure.

**Step 2: Update tests**

Apply the same pattern as REST-PY tests (Task 3):
- Remove delegation config from invoker construction
- Add `api_key` / credentials to invoke calls
- Add 401 test for missing credentials
- Remove assertions about delegation config fields

**Step 3: Commit**

```bash
git add adapters/rest-ts/test-adapter.ts
git commit -m "test(rest-ts): update tests for v0.2 credential pass-through"
```

---

## Task 7: Rewrite GraphQL-PY `invocation.py` — Same as REST-PY Invocation

**Files:**
- Modify: `adapters/graphql-py/anip_graphql_adapter/invocation.py` (complete rewrite)

**Step 1: Rewrite `invocation.py`**

Use the exact same `ANIPInvoker`, `CredentialError`, and `IssuanceError` classes as REST-PY (Task 1), but with GraphQL-appropriate subject strings:
- `subject: "adapter:anip-graphql-adapter"` in `_invoke_with_api_key`

The file is structurally identical to REST-PY's `invocation.py` — same two credential paths, same error types. Only the subject string differs.

**Step 2: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/invocation.py
git commit -m "feat(graphql-py): migrate invocation to v0.2 credential pass-through"
```

---

## Task 8: Update GraphQL-PY Server and Config — Credential Extraction from GraphQL Context

**Files:**
- Modify: `adapters/graphql-py/anip_graphql_adapter/config.py`
- Modify: `adapters/graphql-py/anip_graphql_adapter/server.py`
- Modify: `adapters/graphql-py/adapter.example.yaml`

**Step 1: Simplify `config.py`**

Remove `DelegationConfig`. Keep `GraphQLConfig`. Update `AdapterConfig`:

```python
@dataclass
class AdapterConfig:
    """Full adapter configuration."""

    anip_service_url: str = "http://localhost:8000"
    port: int = 3002
    graphql: GraphQLConfig = field(default_factory=GraphQLConfig)
```

Remove all delegation-related loading from `load_config()`.

**Step 2: Update `server.py` — pass credentials through GraphQL context**

In `build_app()`, replace invoker setup (lines 141-149):

```python
    # Step 2: Set up the invoker (stateless — no token registration)
    invoker = ANIPInvoker(service=service)
    logger.info("Invoker ready (pass-through mode)")
```

Update `_make_resolver` to extract credentials from the GraphQL request info/context:

```python
def _make_resolver(capability_name: str, invoker: ANIPInvoker):
    """Create a resolver function for a given capability."""

    async def resolver(_obj: Any, info: Any, **kwargs: Any) -> dict[str, Any]:
        # Convert camelCase args back to snake_case for ANIP
        arguments = {_camel_to_snake(k): v for k, v in kwargs.items()}

        # Extract credentials from the HTTP request
        token, api_key = _extract_credentials_from_info(info)

        try:
            result = await invoker.invoke(
                capability_name, arguments,
                token=token, api_key=api_key,
            )
        except CredentialError as e:
            return {
                "success": False,
                "result": None,
                "costActual": None,
                "failure": {
                    "type": "missing_credentials",
                    "detail": str(e),
                    "resolution": None,
                    "retry": False,
                },
            }
        except IssuanceError as e:
            return {
                "success": False,
                "result": None,
                "costActual": None,
                "failure": {
                    "type": "token_issuance_denied",
                    "detail": e.error,
                    "resolution": None,
                    "retry": False,
                },
            }
        except Exception as e:
            logger.exception("ANIP invocation failed for %s", capability_name)
            return {
                "success": False,
                "result": None,
                "costActual": None,
                "failure": {
                    "type": "adapter_error",
                    "detail": str(e),
                    "resolution": None,
                    "retry": True,
                },
            }
        return _build_anip_response(result)

    return resolver
```

Add the Ariadne-specific credential extractor:

```python
def _extract_credentials_from_info(info: Any) -> tuple[str | None, str | None]:
    """Extract ANIP credentials from Ariadne's GraphQL info context.

    Ariadne provides the ASGI request via info.context["request"].
    """
    token: str | None = None
    api_key: str | None = None

    request = info.context.get("request")
    if request is not None:
        token = request.headers.get("x-anip-token")
        api_key = request.headers.get("x-anip-api-key")

    return token, api_key
```

Add imports at top of server.py:

```python
from .invocation import ANIPInvoker, CredentialError, IssuanceError
```

**Step 3: Update `adapter.example.yaml`**

```yaml
# ANIP GraphQL Adapter Configuration
#
# Copy to adapter.yaml and adjust for your setup.

# The ANIP service to expose as a GraphQL endpoint
anip_service_url: "http://localhost:8000"

# GraphQL server port
port: 3002

# Authentication: callers must provide credentials via HTTP headers:
#   X-ANIP-Token: <signed-anip-token>  (preferred)
#   X-ANIP-API-Key: <api-key>           (convenience)
#
# The adapter is a stateless bridge — it holds no tokens of its own.

# GraphQL configuration (optional)
# graphql:
#   path: "/graphql"
#   playground: true
#   introspection: true
```

**Step 4: Commit**

```bash
git add adapters/graphql-py/anip_graphql_adapter/config.py adapters/graphql-py/anip_graphql_adapter/server.py adapters/graphql-py/adapter.example.yaml
git commit -m "feat(graphql-py): remove delegation config, add credential extraction from GraphQL context"
```

---

## Task 9: Update GraphQL-PY Tests

**Files:**
- Modify: `adapters/graphql-py/test_adapter.py`

**Step 1: Read and update tests**

Same pattern as REST-PY tests:
- Remove delegation config references
- Add API key credentials to invocation tests
- Add test for missing-credentials error response

**Step 2: Commit**

```bash
git add adapters/graphql-py/test_adapter.py
git commit -m "test(graphql-py): update tests for v0.2 credential pass-through"
```

---

## Task 10: Rewrite GraphQL-TS `invocation.ts`

**Files:**
- Modify: `adapters/graphql-ts/src/invocation.ts` (complete rewrite)

**Step 1: Rewrite `invocation.ts`**

Same structure as REST-TS `invocation.ts` (Task 4), with GraphQL-appropriate subject string:
- `subject: "adapter:anip-graphql-adapter-ts"` in `invokeWithApiKey`

**Step 2: Commit**

```bash
git add adapters/graphql-ts/src/invocation.ts
git commit -m "feat(graphql-ts): migrate invocation to v0.2 credential pass-through"
```

---

## Task 11: Update GraphQL-TS Server and Config — Credential Extraction

**Files:**
- Modify: `adapters/graphql-ts/src/config.ts`
- Modify: `adapters/graphql-ts/src/index.ts`
- Modify: `adapters/graphql-ts/adapter.example.yaml`

**Step 1: Simplify `config.ts`**

Remove `DelegationConfig`. Keep `graphqlPath`. Update `AdapterConfig`:

```typescript
export interface AdapterConfig {
  anipServiceUrl: string;
  port: number;
  graphqlPath: string;
}
```

Remove delegation loading from `loadConfig()`.

**Step 2: Update `index.ts`**

Replace invoker setup (lines 109-116):

```typescript
  // Step 2: Set up the invoker (stateless — no token registration)
  const invoker = new ANIPInvoker(service);
  console.error("[anip-graphql-adapter] Invoker ready (pass-through mode)");
```

Update `makeResolver()` to accept credentials:

```typescript
function makeResolver(capabilityName: string, invoker: ANIPInvoker) {
  return async (
    args: Record<string, unknown>,
    creds: { token?: string; apiKey?: string },
  ) => {
    const snakeArgs: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(args)) {
      snakeArgs[toSnakeCase(k)] = v;
    }

    try {
      const result = await invoker.invoke(capabilityName, snakeArgs, creds);
      return buildAnipResponse(result);
    } catch (e) {
      if (e instanceof CredentialError) {
        return {
          success: false, result: null, costActual: null,
          failure: { type: "missing_credentials", detail: e.message, resolution: null, retry: false },
        };
      }
      if (e instanceof IssuanceError) {
        return {
          success: false, result: null, costActual: null,
          failure: { type: "token_issuance_denied", detail: e.error, resolution: null, retry: false },
        };
      }
      console.error(`ANIP invocation failed for ${capabilityName}:`, e);
      return {
        success: false, result: null, costActual: null,
        failure: {
          type: "adapter_error",
          detail: e instanceof Error ? e.message : String(e),
          resolution: null, retry: true,
        },
      };
    }
  };
}
```

Update the GraphQL POST handler to extract credentials and pass them to resolvers via rootValue wrappers:

```typescript
  // POST /graphql — execute GraphQL query/mutation
  app.post(config.graphqlPath, async (c) => {
    const body = await c.req.json() as {
      query: string;
      variables?: Record<string, unknown>;
      operationName?: string;
    };

    // Extract credentials from HTTP headers
    const token = c.req.header("x-anip-token") ?? undefined;
    const apiKey = c.req.header("x-anip-api-key") ?? undefined;
    const creds = { token, apiKey };

    // Wrap resolvers to inject credentials
    const rootValueWithCreds: Record<string, (args: Record<string, unknown>) => Promise<Record<string, unknown>>> = {};
    for (const [name, resolver] of Object.entries(rootValue)) {
      rootValueWithCreds[name] = (args: Record<string, unknown>) => resolver(args, creds);
    }

    const result = await graphql({
      schema,
      source: body.query,
      rootValue: rootValueWithCreds,
      variableValues: body.variables,
      operationName: body.operationName,
    });

    return c.json(result);
  });
```

Also update the GET handler similarly (for inline query testing).

**Step 3: Update `adapter.example.yaml`** — same as GraphQL-PY example yaml.

**Step 4: Commit**

```bash
git add adapters/graphql-ts/src/config.ts adapters/graphql-ts/src/index.ts adapters/graphql-ts/adapter.example.yaml
git commit -m "feat(graphql-ts): remove delegation config, add credential extraction"
```

---

## Task 12: Update GraphQL-TS Tests

**Files:**
- Modify: `adapters/graphql-ts/test-adapter.ts`

**Step 1: Read and update tests**

Same pattern as other adapter tests:
- Remove delegation config references
- Add API key credentials
- Add test for missing-credentials error response

**Step 2: Commit**

```bash
git add adapters/graphql-ts/test-adapter.ts
git commit -m "test(graphql-ts): update tests for v0.2 credential pass-through"
```

---

## Task 13: Integration Verification

**Step 1: Start the ANIP server**

```bash
cd examples/anip && .venv/bin/python -m anip_server.main &
```

Wait for it to be ready on port 8000.

**Step 2: Run REST-PY tests**

```bash
cd adapters/rest-py && python test_adapter.py http://localhost:8000
```

Expected: All tests pass.

**Step 3: Run GraphQL-PY tests**

```bash
cd adapters/graphql-py && python test_adapter.py http://localhost:8000
```

Expected: All tests pass.

**Step 4: Run REST-TS tests** (if executable)

```bash
cd adapters/rest-ts && npx tsx test-adapter.ts http://localhost:8000
```

**Step 5: Run GraphQL-TS tests** (if executable)

```bash
cd adapters/graphql-ts && npx tsx test-adapter.ts http://localhost:8000
```

**Step 6: Manual smoke test — 401 on missing credentials**

```bash
curl -s http://localhost:3001/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10&passengers=1 | python -m json.tool
```

Expected: 401 with `missing_credentials` failure type.

**Step 7: Manual smoke test — API key path**

```bash
curl -s -H "X-ANIP-API-Key: demo-human-key" "http://localhost:3001/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10&passengers=1" | python -m json.tool
```

Expected: 200 with flight results.

**Step 8: Manual smoke test — token path (preferred)**

```bash
# First obtain a signed token
TOKEN=$(curl -s -X POST http://localhost:8000/anip/tokens \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo-human-key" \
  -d '{"subject":"test:smoke","scope":["travel.search"],"capability":"search_flights"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Use the token via X-ANIP-Token header
curl -s -H "X-ANIP-Token: $TOKEN" "http://localhost:3001/api/search_flights?origin=SEA&destination=SFO&date=2026-03-10&passengers=1" | python -m json.tool
```

Expected: 200 with flight results (same as API key path but using pre-issued token).

**Step 9: Stop the ANIP server and commit**

```bash
git add -A
git commit -m "chore: integration verification complete for v0.2 adapter migration"
```
