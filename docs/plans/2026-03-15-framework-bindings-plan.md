# Framework Bindings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three framework binding packages (`anip-flask`, `@anip/express`, `@anip/fastify`) that mount an ANIPService as HTTP routes, following the same pattern as `anip-fastapi` and `@anip/hono`.

**Architecture:** Each binding is a thin routing layer: a single `mount_anip`/`mountAnip` function that takes a framework app + ANIPService, mounts 9 identical routes, handles bearer extraction/error mapping/manifest signing, and returns a lifecycle handle with `stop()`. All three bindings reuse the exact same route structure, status code mapping, and error response format as the existing bindings.

**Tech Stack:** Python 3.11+, Flask 3.0+, Node 20+, Express 4.21+, Fastify 5.0+, pytest, vitest, supertest

---

### Task 1: Create `anip-flask` package

**Files:**
- Create: `packages/python/anip-flask/pyproject.toml`
- Create: `packages/python/anip-flask/src/anip_flask/__init__.py`
- Create: `packages/python/anip-flask/src/anip_flask/routes.py`
- Create: `packages/python/anip-flask/tests/__init__.py`
- Create: `packages/python/anip-flask/tests/test_routes.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "anip-flask"
version = "0.3.0"
description = "ANIP Flask bindings — mount an ANIPService as HTTP routes"
requires-python = ">=3.11"
dependencies = [
    "anip-service>=0.3.0",
    "flask>=3.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Step 2: Create `__init__.py`**

```python
"""ANIP Flask bindings — mount an ANIPService as HTTP routes."""
from .routes import mount_anip, ANIPHandle

__all__ = ["mount_anip", "ANIPHandle"]
```

**Step 3: Create `routes.py`**

```python
"""Mount ANIP routes onto a Flask application."""
from __future__ import annotations

from flask import Flask, Blueprint, Request, request, jsonify, Response

from anip_service import ANIPService, ANIPError


class ANIPHandle:
    """Lifecycle handle returned by mount_anip."""

    def __init__(self, service: ANIPService) -> None:
        self._service = service

    def stop(self) -> None:
        self._service.stop()


def mount_anip(
    app: Flask,
    service: ANIPService,
    prefix: str = "",
) -> ANIPHandle:
    """Mount all ANIP protocol routes onto a Flask app.

    Routes:
        GET  {prefix}/.well-known/anip          → discovery
        GET  {prefix}/.well-known/jwks.json     → JWKS
        GET  {prefix}/anip/manifest             → full manifest (signed)
        POST {prefix}/anip/tokens               → issue token
        POST {prefix}/anip/permissions           → discover permissions
        POST {prefix}/anip/invoke/<capability>   → invoke capability
        POST {prefix}/anip/audit                → query audit log
        GET  {prefix}/anip/checkpoints          → list checkpoints
        GET  {prefix}/anip/checkpoints/<id>     → get checkpoint
    """
    bp = Blueprint("anip", __name__)

    # --- Discovery & Identity ---

    @bp.route("/.well-known/anip")
    def discovery():
        return jsonify(service.get_discovery())

    @bp.route("/.well-known/jwks.json")
    def jwks():
        return jsonify(service.get_jwks())

    @bp.route("/anip/manifest")
    def manifest():
        body_bytes, signature = service.get_signed_manifest()
        return Response(
            body_bytes,
            content_type="application/json",
            headers={"X-ANIP-Signature": signature},
        )

    # --- Tokens ---

    @bp.route("/anip/tokens", methods=["POST"])
    def issue_token():
        principal = _extract_principal(request, service)
        if principal is None:
            return jsonify({"error": "Authentication required"}), 401

        body = request.get_json(force=True)
        try:
            result = service.issue_token(principal, body)
            return jsonify(result)
        except ANIPError as e:
            return _error_response(e)

    # --- Permissions ---

    @bp.route("/anip/permissions", methods=["POST"])
    def permissions():
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401
        return jsonify(service.discover_permissions(token))

    # --- Invoke ---

    @bp.route("/anip/invoke/<capability>", methods=["POST"])
    def invoke(capability: str):
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401

        body = request.get_json(force=True)
        params = body.get("parameters", body)
        result = service.invoke(capability, token, params)

        if not result.get("success"):
            status = _failure_status(result.get("failure", {}).get("type"))
            return jsonify(result), status

        return jsonify(result)

    # --- Audit ---

    @bp.route("/anip/audit", methods=["POST"])
    def audit():
        token = _resolve_token(request, service)
        if token is None:
            return jsonify({"error": "Authentication required"}), 401

        filters = {
            "capability": request.args.get("capability"),
            "since": request.args.get("since"),
            "limit": int(request.args.get("limit", "50")),
        }
        return jsonify(service.query_audit(token, filters))

    # --- Checkpoints ---

    @bp.route("/anip/checkpoints")
    def list_checkpoints():
        limit = int(request.args.get("limit", "10"))
        return jsonify(service.get_checkpoints(limit))

    @bp.route("/anip/checkpoints/<checkpoint_id>")
    def get_checkpoint(checkpoint_id: str):
        options = {
            "include_proof": request.args.get("include_proof") == "true",
            "leaf_index": request.args.get("leaf_index"),
            "consistency_from": request.args.get("consistency_from"),
        }
        result = service.get_checkpoint(checkpoint_id, options)
        if result is None:
            return jsonify({"error": "Checkpoint not found"}), 404
        return jsonify(result)

    app.register_blueprint(bp, url_prefix=prefix or None)
    service.start()
    return ANIPHandle(service)


def _extract_principal(req: Request, service: ANIPService) -> str | None:
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer_value = auth[7:].strip()
    return service.authenticate_bearer(bearer_value)


def _resolve_token(req: Request, service: ANIPService):
    auth = req.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return service.resolve_bearer_token(jwt_str)
    except ANIPError:
        return None


def _failure_status(failure_type: str | None) -> int:
    mapping = {
        "invalid_token": 401,
        "token_expired": 401,
        "scope_insufficient": 403,
        "insufficient_authority": 403,
        "purpose_mismatch": 403,
        "unknown_capability": 404,
        "not_found": 404,
        "unavailable": 409,
        "concurrent_lock": 409,
        "internal_error": 500,
    }
    return mapping.get(failure_type or "", 400)


def _error_response(error: ANIPError):
    status = _failure_status(error.error_type)
    return jsonify(
        {"success": False, "failure": {"type": error.error_type, "detail": error.detail}}
    ), status
```

**Step 4: Create `tests/__init__.py`**

Empty file.

**Step 5: Create `tests/test_routes.py`**

```python
import pytest
from flask import Flask
from anip_service import ANIPService, Capability
from anip_flask import mount_anip
from anip_core import CapabilityDeclaration, CapabilityInput, CapabilityOutput, SideEffect, SideEffectType


def _greet_cap():
    return Capability(
        declaration=CapabilityDeclaration(
            name="greet",
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


API_KEY = "test-key-123"


@pytest.fixture
def client():
    app = Flask(__name__)
    service = ANIPService(
        service_id="test-service",
        capabilities=[_greet_cap()],
        storage=":memory:",
        authenticate=lambda bearer: "test-agent" if bearer == API_KEY else None,
    )
    handle = mount_anip(app, service)
    yield app.test_client()
    handle.stop()


class TestDiscoveryRoutes:
    def test_well_known_anip(self, client):
        resp = client.get("/.well-known/anip")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "anip_discovery" in data
        assert "greet" in data["anip_discovery"]["capabilities"]

    def test_jwks(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "keys" in data

    def test_manifest(self, client):
        resp = client.get("/anip/manifest")
        assert resp.status_code == 200
        assert "X-ANIP-Signature" in resp.headers


class TestCheckpointRoutes:
    def test_checkpoints_list(self, client):
        resp = client.get("/anip/checkpoints")
        assert resp.status_code == 200
        assert "checkpoints" in resp.get_json()

    def test_checkpoint_not_found(self, client):
        resp = client.get("/anip/checkpoints/ckpt-nonexistent")
        assert resp.status_code == 404


class TestTokenRoutes:
    def test_token_without_auth(self, client):
        resp = client.post("/anip/tokens", json={"scope": ["greet"]})
        assert resp.status_code == 401


class TestInvokeRoutes:
    def test_invoke_success(self, client):
        # First get a token
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"]},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        token = resp.get_json()["token"]

        # Then invoke
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["result"]["message"] == "Hello, World!"


class TestLifecycle:
    def test_stop(self):
        app = Flask(__name__)
        service = ANIPService(
            service_id="test-service",
            capabilities=[_greet_cap()],
            storage=":memory:",
        )
        handle = mount_anip(app, service)
        handle.stop()  # Should not raise
```

**Step 6: Install and run tests**

```bash
pip install -e "./packages/python/anip-flask[dev]"
pytest packages/python/anip-flask/tests/ -v
```

Expected: 8 tests pass.

**Step 7: Commit**

```bash
git add packages/python/anip-flask/
git commit -m "feat: add anip-flask binding package"
```

---

### Task 2: Create `@anip/express` package

**Files:**
- Create: `packages/typescript/express/package.json`
- Create: `packages/typescript/express/tsconfig.json`
- Create: `packages/typescript/express/src/index.ts`
- Create: `packages/typescript/express/src/routes.ts`
- Create: `packages/typescript/express/tests/routes.test.ts`
- Modify: `packages/typescript/package.json` (add workspace)

**Step 1: Add workspace to root `package.json`**

In `packages/typescript/package.json`, change:
```json
"workspaces": ["core", "crypto", "server", "service", "hono"]
```
to:
```json
"workspaces": ["core", "crypto", "server", "service", "hono", "express", "fastify"]
```

**Step 2: Create `package.json`**

```json
{
  "name": "@anip/express",
  "version": "0.3.0",
  "description": "ANIP Express bindings — mount an ANIPService as HTTP routes",
  "type": "module",
  "engines": {
    "node": ">=20"
  },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/service": "0.3.0",
    "express": "^4.21.0"
  },
  "devDependencies": {
    "@types/express": "^5.0.0",
    "@types/supertest": "^6.0.0",
    "supertest": "^7.1.0",
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 3: Create `tsconfig.json`**

```json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

**Step 4: Create `src/index.ts`**

```typescript
export { mountAnip } from "./routes.js";
```

**Step 5: Create `src/routes.ts`**

```typescript
import { Router } from "express";
import type { Express, Request, Response } from "express";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

export function mountAnip(
  app: Express,
  service: ANIPService,
  opts?: { prefix?: string },
): { stop: () => void } {
  const router = Router();

  // --- Discovery & Identity ---
  router.get("/.well-known/anip", (_req, res) => {
    res.json(service.getDiscovery());
  });

  router.get("/.well-known/jwks.json", async (_req, res, next) => {
    try {
      const jwks = await service.getJwks();
      res.json(jwks);
    } catch (e) { next(e); }
  });

  router.get("/anip/manifest", async (_req, res, next) => {
    try {
      const [bodyBytes, signature] = await service.getSignedManifest();
      res.set("Content-Type", "application/json");
      res.set("X-ANIP-Signature", signature);
      res.send(Buffer.from(bodyBytes));
    } catch (e) { next(e); }
  });

  // --- Tokens ---
  router.post("/anip/tokens", async (req, res, next) => {
    try {
      const principal = await extractPrincipal(req, service);
      if (!principal) { res.status(401).json({ error: "Authentication required" }); return; }
      const result = await service.issueToken(principal, req.body);
      res.json(result);
    } catch (e) {
      if (e instanceof ANIPError) { errorResponse(res, e); return; }
      next(e);
    }
  });

  // --- Permissions ---
  router.post("/anip/permissions", async (req, res, next) => {
    try {
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      res.json(service.discoverPermissions(token));
    } catch (e) { next(e); }
  });

  // --- Invoke ---
  router.post("/anip/invoke/:capability", async (req, res, next) => {
    try {
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      const body = req.body;
      const params = body.parameters ?? body;
      const result = await service.invoke(req.params.capability, token, params);
      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        res.status(failureStatus(failure?.type as string)).json(result);
        return;
      }
      res.json(result);
    } catch (e) { next(e); }
  });

  // --- Audit ---
  router.post("/anip/audit", async (req, res, next) => {
    try {
      const token = await resolveToken(req, service);
      if (!token) { res.status(401).json({ error: "Authentication required" }); return; }
      const filters = {
        capability: (req.query.capability as string) ?? undefined,
        since: (req.query.since as string) ?? undefined,
        limit: parseInt((req.query.limit as string) ?? "50", 10),
      };
      res.json(service.queryAudit(token, filters));
    } catch (e) { next(e); }
  });

  // --- Checkpoints ---
  router.get("/anip/checkpoints", (req, res) => {
    const limit = parseInt((req.query.limit as string) ?? "10", 10);
    res.json(service.getCheckpoints(limit));
  });

  router.get("/anip/checkpoints/:id", (req, res) => {
    const options = {
      include_proof: req.query.include_proof === "true",
      leaf_index: (req.query.leaf_index as string) ?? undefined,
      consistency_from: (req.query.consistency_from as string) ?? undefined,
    };
    const result = service.getCheckpoint(req.params.id, options);
    if (!result) { res.status(404).json({ error: "Checkpoint not found" }); return; }
    res.json(result);
  });

  const prefix = opts?.prefix ?? "";
  if (prefix) {
    app.use(prefix, router);
  } else {
    app.use(router);
  }

  service.start();
  return { stop: () => service.stop() };
}

// --- Helpers ---

async function extractPrincipal(req: Request, service: ANIPService): Promise<string | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateBearer(auth.slice(7).trim());
}

async function resolveToken(req: Request, service: ANIPService) {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch {
    return null;
  }
}

function failureStatus(type?: string): number {
  const mapping: Record<string, number> = {
    invalid_token: 401,
    token_expired: 401,
    scope_insufficient: 403,
    insufficient_authority: 403,
    purpose_mismatch: 403,
    unknown_capability: 404,
    not_found: 404,
    unavailable: 409,
    concurrent_lock: 409,
    internal_error: 500,
  };
  return mapping[type ?? ""] ?? 400;
}

function errorResponse(res: Response, error: ANIPError) {
  const status = failureStatus(error.errorType);
  res.status(status).json({
    success: false,
    failure: { type: error.errorType, detail: error.detail },
  });
}
```

**Step 6: Create `tests/routes.test.ts`**

```typescript
import { describe, it, expect, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { createANIPService, defineCapability } from "@anip/service";
import { mountAnip } from "../src/routes.js";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";

function greetCap() {
  return defineCapability({
    declaration: {
      name: "greet",
      description: "Say hello",
      contract_version: "1.0",
      inputs: [{ name: "name", type: "string", required: true, description: "Who" }],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["greet"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ message: `Hello, ${params.name}!` }),
  });
}

const API_KEY = "test-key-123";

function makeApp() {
  const app = express();
  app.use(express.json());
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = mountAnip(app, service);
  return { app, stop };
}

describe("Express routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("GET /.well-known/anip returns discovery", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/anip");
    expect(res.status).toBe(200);
    expect(res.body.anip_discovery).toBeDefined();
    expect(res.body.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/.well-known/jwks.json");
    expect(res.status).toBe(200);
    expect(res.body.keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/manifest");
    expect(res.status).toBe(200);
    expect(res.headers["x-anip-signature"]).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints");
    expect(res.status).toBe(200);
    expect(res.body.checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app).get("/anip/checkpoints/ckpt-nonexistent");
    expect(res.status).toBe(404);
  });

  it("POST /anip/tokens without auth returns 401", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await request(app)
      .post("/anip/tokens")
      .send({ scope: ["greet"] });
    expect(res.status).toBe(401);
  });

  it("POST /anip/invoke/:capability with valid token succeeds", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"] });
    expect(tokenRes.status).toBe(200);
    const token = tokenRes.body.token;

    // Invoke
    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${token}`)
      .send({ parameters: { name: "World" } });
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.result.message).toBe("Hello, World!");
  });

  it("stop() can be called without error", () => {
    const { stop } = makeApp();
    stop(); // Should not throw
  });
});
```

**Step 7: Install dependencies and run tests**

```bash
cd packages/typescript && npm install
npx tsc -p core/tsconfig.json
npx tsc -p crypto/tsconfig.json
npx tsc -p server/tsconfig.json
npx tsc -p service/tsconfig.json
npx tsc -p express/tsconfig.json
npm test --workspace=@anip/express
```

Expected: 8 tests pass.

**Step 8: Commit**

```bash
git add packages/typescript/express/ packages/typescript/package.json
git commit -m "feat: add @anip/express binding package"
```

---

### Task 3: Create `@anip/fastify` package

**Files:**
- Create: `packages/typescript/fastify/package.json`
- Create: `packages/typescript/fastify/tsconfig.json`
- Create: `packages/typescript/fastify/src/index.ts`
- Create: `packages/typescript/fastify/src/routes.ts`
- Create: `packages/typescript/fastify/tests/routes.test.ts`

**Step 1: Create `package.json`**

```json
{
  "name": "@anip/fastify",
  "version": "0.3.0",
  "description": "ANIP Fastify bindings — mount an ANIPService as HTTP routes",
  "type": "module",
  "engines": {
    "node": ">=20"
  },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "test": "vitest run"
  },
  "dependencies": {
    "@anip/service": "0.3.0",
    "fastify": "^5.0.0"
  },
  "devDependencies": {
    "typescript": "^5.5.0",
    "vitest": "^4.1.0"
  }
}
```

**Step 2: Create `tsconfig.json`**

```json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src"]
}
```

**Step 3: Create `src/index.ts`**

```typescript
export { mountAnip } from "./routes.js";
```

**Step 4: Create `src/routes.ts`**

```typescript
import Fastify from "fastify";
import type { FastifyInstance, FastifyRequest, FastifyReply } from "fastify";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

export function mountAnip(
  app: FastifyInstance,
  service: ANIPService,
  opts?: { prefix?: string },
): { stop: () => void } {
  const p = opts?.prefix ?? "";

  // --- Discovery & Identity ---
  app.get(`${p}/.well-known/anip`, async () => {
    return service.getDiscovery();
  });

  app.get(`${p}/.well-known/jwks.json`, async () => {
    return service.getJwks();
  });

  app.get(`${p}/anip/manifest`, async (_req, reply) => {
    const [bodyBytes, signature] = await service.getSignedManifest();
    reply
      .header("Content-Type", "application/json")
      .header("X-ANIP-Signature", signature)
      .send(Buffer.from(bodyBytes));
  });

  // --- Tokens ---
  app.post(`${p}/anip/tokens`, async (req, reply) => {
    const principal = await extractPrincipal(req, service);
    if (!principal) return reply.status(401).send({ error: "Authentication required" });
    try {
      const result = await service.issueToken(principal, req.body as Record<string, unknown>);
      return result;
    } catch (e) {
      if (e instanceof ANIPError) return errorResponse(reply, e);
      throw e;
    }
  });

  // --- Permissions ---
  app.post(`${p}/anip/permissions`, async (req, reply) => {
    const token = await resolveToken(req, service);
    if (!token) return reply.status(401).send({ error: "Authentication required" });
    return service.discoverPermissions(token);
  });

  // --- Invoke ---
  app.post<{ Params: { capability: string } }>(
    `${p}/anip/invoke/:capability`,
    async (req, reply) => {
      const token = await resolveToken(req, service);
      if (!token) return reply.status(401).send({ error: "Authentication required" });
      const body = req.body as Record<string, unknown>;
      const params = (body.parameters as Record<string, unknown>) ?? body;
      const result = await service.invoke(req.params.capability, token, params);
      if (!result.success) {
        const failure = result.failure as Record<string, unknown>;
        return reply.status(failureStatus(failure?.type as string)).send(result);
      }
      return result;
    },
  );

  // --- Audit ---
  app.post(`${p}/anip/audit`, async (req, reply) => {
    const token = await resolveToken(req, service);
    if (!token) return reply.status(401).send({ error: "Authentication required" });
    const query = req.query as Record<string, string>;
    const filters = {
      capability: query.capability ?? undefined,
      since: query.since ?? undefined,
      limit: parseInt(query.limit ?? "50", 10),
    };
    return service.queryAudit(token, filters);
  });

  // --- Checkpoints ---
  app.get(`${p}/anip/checkpoints`, async (req) => {
    const query = req.query as Record<string, string>;
    const limit = parseInt(query.limit ?? "10", 10);
    return service.getCheckpoints(limit);
  });

  app.get<{ Params: { id: string } }>(`${p}/anip/checkpoints/:id`, async (req, reply) => {
    const query = req.query as Record<string, string>;
    const options = {
      include_proof: query.include_proof === "true",
      leaf_index: query.leaf_index ?? undefined,
      consistency_from: query.consistency_from ?? undefined,
    };
    const result = service.getCheckpoint(req.params.id, options);
    if (!result) return reply.status(404).send({ error: "Checkpoint not found" });
    return result;
  });

  service.start();
  return { stop: () => service.stop() };
}

// --- Helpers ---

async function extractPrincipal(req: FastifyRequest, service: ANIPService): Promise<string | null> {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  return service.authenticateBearer(auth.slice(7).trim());
}

async function resolveToken(req: FastifyRequest, service: ANIPService) {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch {
    return null;
  }
}

function failureStatus(type?: string): number {
  const mapping: Record<string, number> = {
    invalid_token: 401,
    token_expired: 401,
    scope_insufficient: 403,
    insufficient_authority: 403,
    purpose_mismatch: 403,
    unknown_capability: 404,
    not_found: 404,
    unavailable: 409,
    concurrent_lock: 409,
    internal_error: 500,
  };
  return mapping[type ?? ""] ?? 400;
}

function errorResponse(reply: FastifyReply, error: ANIPError) {
  const status = failureStatus(error.errorType);
  return reply.status(status).send({
    success: false,
    failure: { type: error.errorType, detail: error.detail },
  });
}
```

**Step 5: Create `tests/routes.test.ts`**

```typescript
import { describe, it, expect, afterEach } from "vitest";
import Fastify from "fastify";
import { createANIPService, defineCapability } from "@anip/service";
import { mountAnip } from "../src/routes.js";
import { InMemoryStorage } from "@anip/server";
import type { CapabilityDeclaration } from "@anip/core";

function greetCap() {
  return defineCapability({
    declaration: {
      name: "greet",
      description: "Say hello",
      contract_version: "1.0",
      inputs: [{ name: "name", type: "string", required: true, description: "Who" }],
      output: { type: "object", fields: ["message"] },
      side_effect: { type: "read", rollback_window: "not_applicable" },
      minimum_scope: ["greet"],
    } as CapabilityDeclaration,
    handler: (_ctx, params) => ({ message: `Hello, ${params.name}!` }),
  });
}

const API_KEY = "test-key-123";

function makeApp() {
  const app = Fastify();
  const service = createANIPService({
    serviceId: "test-service",
    capabilities: [greetCap()],
    storage: new InMemoryStorage(),
    authenticate: (bearer) => (bearer === API_KEY ? "test-agent" : null),
  });
  const { stop } = mountAnip(app, service);
  return { app, stop };
}

describe("Fastify routes", () => {
  let stopFn: (() => void) | undefined;

  afterEach(() => {
    stopFn?.();
    stopFn = undefined;
  });

  it("GET /.well-known/anip returns discovery", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/.well-known/anip" });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.anip_discovery).toBeDefined();
    expect(data.anip_discovery.capabilities.greet).toBeDefined();
  });

  it("GET /.well-known/jwks.json returns keys", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/.well-known/jwks.json" });
    expect(res.statusCode).toBe(200);
    expect(res.json().keys).toBeDefined();
  });

  it("GET /anip/manifest returns signed manifest", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/manifest" });
    expect(res.statusCode).toBe(200);
    expect(res.headers["x-anip-signature"]).toBeTruthy();
  });

  it("GET /anip/checkpoints returns list", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/checkpoints" });
    expect(res.statusCode).toBe(200);
    expect(res.json().checkpoints).toBeDefined();
  });

  it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({ method: "GET", url: "/anip/checkpoints/ckpt-nonexistent" });
    expect(res.statusCode).toBe(404);
  });

  it("POST /anip/tokens without auth returns 401", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;
    const res = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      payload: { scope: ["greet"] },
    });
    expect(res.statusCode).toBe(401);
  });

  it("POST /anip/invoke/:capability with valid token succeeds", async () => {
    const { app, stop } = makeApp();
    stopFn = stop;

    // Get a token first
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"] },
    });
    expect(tokenRes.statusCode).toBe(200);
    const token = tokenRes.json().token;

    // Invoke
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { authorization: `Bearer ${token}` },
      payload: { parameters: { name: "World" } },
    });
    expect(res.statusCode).toBe(200);
    const data = res.json();
    expect(data.success).toBe(true);
    expect(data.result.message).toBe("Hello, World!");
  });

  it("stop() can be called without error", () => {
    const { stop } = makeApp();
    stop(); // Should not throw
  });
});
```

**Step 6: Install dependencies, build, and run tests**

```bash
cd packages/typescript && npm install
npx tsc -p fastify/tsconfig.json
npm test --workspace=@anip/fastify
```

Expected: 8 tests pass.

**Step 7: Commit**

```bash
git add packages/typescript/fastify/
git commit -m "feat: add @anip/fastify binding package"
```

---

### Task 4: Update CI workflows and release validation

**Files:**
- Modify: `.github/workflows/ci-python.yml`
- Modify: `.github/workflows/ci-typescript.yml`
- Modify: `.github/workflows/release.yml`

**Step 1: Update Python CI workflow**

Add anip-flask to the install step in `.github/workflows/ci-python.yml`. After the `anip-fastapi` install line, add:

```yaml
          pip install -e "./packages/python/anip-flask[dev]"
```

Add a test step after "Test anip-fastapi":

```yaml
      - name: Test anip-flask
        run: pytest packages/python/anip-flask/tests/ -v
```

**Step 2: Update TypeScript CI workflow**

Add express and fastify to the build step in `.github/workflows/ci-typescript.yml`. After the hono build line, add:

```yaml
          npx tsc -p express/tsconfig.json
          npx tsc -p fastify/tsconfig.json
```

Add test steps after "Test @anip/hono":

```yaml
      - name: Test @anip/express
        working-directory: packages/typescript
        run: npm test --workspace=@anip/express

      - name: Test @anip/fastify
        working-directory: packages/typescript
        run: npm test --workspace=@anip/fastify
```

**Step 3: Update release workflow**

In `.github/workflows/release.yml`, update the version validation step:

Change the step name from:
```yaml
      - name: Validate version against all 10 packages
```
to:
```yaml
      - name: Validate version against all 13 packages
```

Add `anip-flask` to the Python package loop:
```yaml
          for pkg in anip-core anip-crypto anip-server anip-service anip-fastapi anip-flask; do
```

Add `express` and `fastify` to the TypeScript package loop:
```yaml
          for pkg in core crypto server service hono express fastify; do
```

Change the success message from:
```yaml
          echo "All 10 packages at version $EXPECTED"
```
to:
```yaml
          echo "All 13 packages at version $EXPECTED"
```

Add the two new CI checks to the required checks array:
```yaml
          REQUIRED_CHECKS=("test (3.11)" "test (3.12)" "test (20)" "test (22)")
```

Note: The check names stay the same (`test (3.11)`, etc.) since the new packages run within the same CI jobs. No change needed here.

**Step 4: Commit**

```bash
git add .github/workflows/ci-python.yml .github/workflows/ci-typescript.yml .github/workflows/release.yml
git commit -m "ci: add Flask, Express, Fastify bindings to CI and release validation"
```

---

### Task 5: Update versioning documentation

**Files:**
- Modify: `docs/plans/2026-03-15-ci-versioning-design.md`

**Step 1: Update "10 packages" references**

In `docs/plans/2026-03-15-ci-versioning-design.md`, update the two references:

Change:
```
- **Lockstep versioning** at `0.3.x` across all 10 core packages
```
to:
```
- **Lockstep versioning** at `0.3.x` across all 13 core packages
```

Change:
```
- **Lockstep versioning**: all 10 core packages (5 Python + 5 TypeScript) share the same version
```
to:
```
- **Lockstep versioning**: all 13 core packages (6 Python + 7 TypeScript) share the same version
```

**Step 2: Commit**

```bash
git add docs/plans/2026-03-15-ci-versioning-design.md
git commit -m "docs: update package count from 10 to 13"
```
