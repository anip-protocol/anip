# Auth Error Fix + Test Coverage Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix structured auth errors across all 4 framework bindings (#39), then expand test coverage across bindings and example apps (#40).

**Architecture:** Two sequential workstreams. Workstream 1 changes the `_resolve_token`/`resolveToken` helpers in each binding to propagate `ANIPError` instead of swallowing it, distinguishes "no header" from "bad token" at the route level, and adds `_auth_failure_*`/`authFailure*` helpers for the "no header" case. Invalid/expired tokens use the existing `_error_response`/`errorResponse` path. Workstream 2 adds ~54 new tests for permissions, audit, auth errors (including invalid token), health, and failure scenarios.

**Tech Stack:** Python (FastAPI, pytest), TypeScript (Hono, Express, Fastify, vitest)

---

## Workstream 1: Structured Auth Errors (#39)

### Key Design Decision: Resolver Returns Three-State Result

The current `_resolve_token`/`resolveToken` helpers return `token | None` — they catch `ANIPError` and return `None`. This means "no header" and "invalid JWT" are indistinguishable. The fix changes the return type to a three-state union:

- `None` → no Authorization header → `authentication_required` + `obtain_delegation_token` resolution
- `ANIPError` → bad/expired JWT → structured failure with the specific error type (`invalid_token`, `token_expired`, etc.)
- `DelegationToken` → success → proceed

Each route handler then dispatches based on the type.

---

### Task 1: FastAPI — Fix resolver, add auth failure helpers, fix auth errors

**Files:**
- Modify: `packages/python/anip-fastapi/src/anip_fastapi/routes.py`
- Test: `packages/python/anip-fastapi/tests/test_routes.py`

**Step 1: Write the failing tests**

Add to `test_routes.py`:

```python
class TestAuthErrors:
    def test_token_endpoint_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/tokens", json={"scope": ["greet"]})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "provide_api_key"
        assert data["failure"]["retry"] is True

    def test_invoke_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/invoke/greet", json={"parameters": {"name": "X"}})
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "obtain_delegation_token"
        assert data["failure"]["retry"] is True

    def test_permissions_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/permissions")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "obtain_delegation_token"

    def test_audit_without_auth_returns_anip_failure(self, client):
        resp = client.post("/anip/audit")
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "authentication_required"
        assert data["failure"]["resolution"]["action"] == "obtain_delegation_token"

    def test_invoke_with_invalid_token_returns_structured_error(self, client):
        resp = client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "X"}},
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"

    def test_permissions_with_invalid_token_returns_structured_error(self, client):
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/python && pytest anip-fastapi/tests/test_routes.py::TestAuthErrors -v`
Expected: FAIL — current responses return `{"error": "Authentication required"}` without `success`/`failure` keys.

**Step 3: Implement the fix**

First, change `_resolve_token` to return `DelegationToken | ANIPError | None`:

```python
async def _resolve_token(request: Request, service: ANIPService):
    """Resolve a bearer token from the Authorization header.

    Returns:
        DelegationToken if valid, ANIPError if invalid/expired, None if no header.
    """
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    jwt_str = auth[7:].strip()
    try:
        return await service.resolve_bearer_token(jwt_str)
    except ANIPError as e:
        return e
```

Then add two "no header" helpers after the existing `_error_response` function:

```python
def _auth_failure_token_endpoint() -> JSONResponse:
    """Structured auth failure for POST /anip/tokens (API key required)."""
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": "authentication_required",
                "detail": "A valid API key is required to issue delegation tokens",
                "resolution": {
                    "action": "provide_api_key",
                    "requires": "API key in Authorization header",
                    "grantable_by": None,
                    "estimated_availability": None,
                },
                "retry": True,
            },
        },
        status_code=401,
    )


def _auth_failure_jwt_endpoint() -> JSONResponse:
    """Structured auth failure for JWT-authenticated endpoints (no header)."""
    return JSONResponse(
        {
            "success": False,
            "failure": {
                "type": "authentication_required",
                "detail": "A valid delegation token (JWT) is required in the Authorization header",
                "resolution": {
                    "action": "obtain_delegation_token",
                    "requires": "Bearer token from POST /anip/tokens",
                    "grantable_by": None,
                    "estimated_availability": None,
                },
                "retry": True,
            },
        },
        status_code=401,
    )
```

Then update all 4 JWT-authenticated route handlers. The pattern for each becomes:

```python
# permissions, invoke, audit routes:
result = await _resolve_token(request, service)
if result is None:
    return _auth_failure_jwt_endpoint()
if isinstance(result, ANIPError):
    return _error_response(result)
token = result
```

For the tokens endpoint (line 66), keep using `_extract_principal` but replace:
```python
return JSONResponse({"error": "Authentication required"}, status_code=401)
```
with:
```python
return _auth_failure_token_endpoint()
```

Also fix checkpoint not found (line 233):
```python
return JSONResponse(
    {
        "success": False,
        "failure": {
            "type": "not_found",
            "detail": f"Checkpoint {checkpoint_id} not found",
            "resolution": {
                "action": "list_checkpoints",
                "requires": "GET /anip/checkpoints to find valid checkpoint IDs",
                "grantable_by": None,
                "estimated_availability": None,
            },
            "retry": False,
        },
    },
    status_code=404,
)
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/python && pytest anip-fastapi/tests/test_routes.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/python/anip-fastapi/src/anip_fastapi/routes.py packages/python/anip-fastapi/tests/test_routes.py
git commit -m "fix(fastapi): return structured ANIPFailure for auth errors (#39)

Changes _resolve_token to propagate ANIPError instead of swallowing it,
so invalid/expired JWTs get their specific error type rather than a
generic authentication_required."
```

---

### Task 2: Hono — Fix resolver, add auth failure helpers, fix auth errors

**Files:**
- Modify: `packages/typescript/hono/src/routes.ts`
- Test: `packages/typescript/hono/tests/routes.test.ts`

**Step 1: Write the failing tests**

Add to `routes.test.ts`:

```typescript
describe("Auth error responses", () => {
  it("POST /anip/tokens without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: ["greet"] }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("provide_api_key");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/invoke without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters: { name: "X" } }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    expect(data.failure.retry).toBe(true);
  });

  it("POST /anip/permissions without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/audit without auth returns ANIPFailure", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/audit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer not-a-valid-jwt",
      },
      body: JSON.stringify({ parameters: { name: "X" } }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app } = await makeApp();
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer not-a-valid-jwt",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/hono`
Expected: FAIL — 6 new tests fail

**Step 3: Implement the fix**

First, change `resolveToken` to return the three-state union:

```typescript
async function resolveToken(c: any, service: ANIPService): Promise<any> {
  const auth = c.req.header("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch (e) {
    if (e instanceof ANIPError) return e;
    throw e;  // rethrow unexpected errors — don't mask as auth failure
  }
}
```

Then add two "no header" helpers:

```typescript
function authFailureTokenEndpoint(c: any) {
  return c.json({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid API key is required to issue delegation tokens",
      resolution: {
        action: "provide_api_key",
        requires: "API key in Authorization header",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  }, 401);
}

function authFailureJwtEndpoint(c: any) {
  return c.json({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid delegation token (JWT) is required in the Authorization header",
      resolution: {
        action: "obtain_delegation_token",
        requires: "Bearer token from POST /anip/tokens",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  }, 401);
}
```

Then update all JWT-authenticated route handlers (permissions, invoke, audit). The new pattern:

```typescript
const result = await resolveToken(c, service);
if (result === null) return authFailureJwtEndpoint(c);
if (result instanceof ANIPError) return errorResponse(c, result);
const token = result;
```

For the tokens endpoint: replace `c.json({ error: "Authentication required" }, 401)` with `authFailureTokenEndpoint(c)`.

Also fix checkpoint not found (line 176):
```typescript
return c.json({
  success: false,
  failure: {
    type: "not_found",
    detail: `Checkpoint ${id} not found`,
    resolution: {
      action: "list_checkpoints",
      requires: "GET /anip/checkpoints to find valid checkpoint IDs",
      grantable_by: null,
      estimated_availability: null,
    },
    retry: false,
  },
}, 404);
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/hono`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/typescript/hono/src/routes.ts packages/typescript/hono/tests/routes.test.ts
git commit -m "fix(hono): return structured ANIPFailure for auth errors (#39)

Changes resolveToken to propagate ANIPError instead of swallowing it,
so invalid/expired JWTs get their specific error type."
```

---

### Task 3: Express — Fix resolver, add auth failure helpers, fix auth errors

**Files:**
- Modify: `packages/typescript/express/src/routes.ts`
- Test: `packages/typescript/express/tests/routes.test.ts`

**Step 1: Write the failing tests**

Add to `routes.test.ts` (use the existing test patterns — `supertest`):

```typescript
describe("Auth error responses", () => {
  it("POST /anip/tokens without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app).post("/anip/tokens").send({ scope: ["greet"] });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("provide_api_key");
    expect(res.body.failure.retry).toBe(true);
    stop();
  });

  it("POST /anip/invoke without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app)
      .post("/anip/invoke/greet")
      .send({ parameters: { name: "X" } });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
    expect(res.body.failure.retry).toBe(true);
    stop();
  });

  it("POST /anip/permissions without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app).post("/anip/permissions").send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
    stop();
  });

  it("POST /anip/audit without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app).post("/anip/audit").send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("authentication_required");
    expect(res.body.failure.resolution.action).toBe("obtain_delegation_token");
    stop();
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", "Bearer not-a-valid-jwt")
      .send({ parameters: { name: "X" } });
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("invalid_token");
    stop();
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", "Bearer not-a-valid-jwt")
      .send({});
    expect(res.status).toBe(401);
    expect(res.body.success).toBe(false);
    expect(res.body.failure.type).toBe("invalid_token");
    stop();
  });
});
```

**Note:** Check the Express test file's existing `makeApp` and cleanup patterns. Adapt if it uses `beforeAll`/`afterAll` instead of inline `stop()`.

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/express`
Expected: FAIL — 6 new tests fail

**Step 3: Implement the fix**

Same three-part change as Hono:

1. Change `resolveToken` to propagate `ANIPError`:

```typescript
async function resolveToken(req: Request, service: ANIPService) {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch (e) {
    if (e instanceof ANIPError) return e;
    throw e;  // rethrow unexpected errors — don't mask as auth failure
  }
}
```

2. Add two helpers (Express pattern — mutates `res`):

```typescript
function authFailureTokenEndpoint(res: Response) {
  res.status(401).json({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid API key is required to issue delegation tokens",
      resolution: {
        action: "provide_api_key",
        requires: "API key in Authorization header",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}

function authFailureJwtEndpoint(res: Response) {
  res.status(401).json({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid delegation token (JWT) is required in the Authorization header",
      resolution: {
        action: "obtain_delegation_token",
        requires: "Bearer token from POST /anip/tokens",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}
```

3. Update route handlers:

```typescript
// permissions, invoke, audit:
const result = await resolveToken(req, service);
if (result === null) { authFailureJwtEndpoint(res); return; }
if (result instanceof ANIPError) { errorResponse(res, result); return; }
const token = result;
```

For tokens endpoint: replace `res.status(401).json({ error: "Authentication required" })` with `authFailureTokenEndpoint(res)`.

Also fix checkpoint not found (line 159):
```typescript
res.status(404).json({
  success: false,
  failure: {
    type: "not_found",
    detail: `Checkpoint ${req.params.id} not found`,
    resolution: {
      action: "list_checkpoints",
      requires: "GET /anip/checkpoints to find valid checkpoint IDs",
      grantable_by: null,
      estimated_availability: null,
    },
    retry: false,
  },
});
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/express`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/typescript/express/src/routes.ts packages/typescript/express/tests/routes.test.ts
git commit -m "fix(express): return structured ANIPFailure for auth errors (#39)"
```

---

### Task 4: Fastify — Fix resolver, add auth failure helpers, fix auth errors

**Files:**
- Modify: `packages/typescript/fastify/src/routes.ts`
- Test: `packages/typescript/fastify/tests/routes.test.ts`

**Step 1: Write the failing tests**

Add to `routes.test.ts` (Fastify uses `app.inject()` and `JSON.parse(res.payload)`):

```typescript
describe("Auth error responses", () => {
  it("POST /anip/tokens without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      payload: { scope: ["greet"] },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("provide_api_key");
    expect(data.failure.retry).toBe(true);
    stop();
  });

  it("POST /anip/invoke without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      payload: { parameters: { name: "X" } },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    expect(data.failure.retry).toBe(true);
    stop();
  });

  it("POST /anip/permissions without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    stop();
  });

  it("POST /anip/audit without auth returns ANIPFailure", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/audit",
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("authentication_required");
    expect(data.failure.resolution.action).toBe("obtain_delegation_token");
    stop();
  });

  it("POST /anip/invoke with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { Authorization: "Bearer not-a-valid-jwt" },
      payload: { parameters: { name: "X" } },
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
    stop();
  });

  it("POST /anip/permissions with invalid JWT returns structured invalid_token", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { Authorization: "Bearer not-a-valid-jwt" },
      payload: {},
    });
    expect(res.statusCode).toBe(401);
    const data = JSON.parse(res.payload);
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
    stop();
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/fastify`
Expected: FAIL — 6 new tests fail

**Step 3: Implement the fix**

Same three-part change:

1. Change `resolveToken`:

```typescript
async function resolveToken(req: FastifyRequest, service: ANIPService) {
  const auth = req.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) return null;
  try {
    return await service.resolveBearerToken(auth.slice(7).trim());
  } catch (e) {
    if (e instanceof ANIPError) return e;
    throw e;  // rethrow unexpected errors — don't mask as auth failure
  }
}
```

2. Add two helpers (Fastify pattern — uses `reply`):

```typescript
function authFailureTokenEndpoint(reply: FastifyReply) {
  return reply.status(401).send({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid API key is required to issue delegation tokens",
      resolution: {
        action: "provide_api_key",
        requires: "API key in Authorization header",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}

function authFailureJwtEndpoint(reply: FastifyReply) {
  return reply.status(401).send({
    success: false,
    failure: {
      type: "authentication_required",
      detail: "A valid delegation token (JWT) is required in the Authorization header",
      resolution: {
        action: "obtain_delegation_token",
        requires: "Bearer token from POST /anip/tokens",
        grantable_by: null,
        estimated_availability: null,
      },
      retry: true,
    },
  });
}
```

3. Update route handlers:

```typescript
// permissions, invoke, audit:
const result = await resolveToken(req, service);
if (result === null) return authFailureJwtEndpoint(reply);
if (result instanceof ANIPError) return errorResponse(reply, result);
const token = result;
```

For tokens: replace `reply.status(401).send({ error: "Authentication required" })` with `authFailureTokenEndpoint(reply)`.

Also fix checkpoint not found (line 149):
```typescript
return reply.status(404).send({
  success: false,
  failure: {
    type: "not_found",
    detail: `Checkpoint ${req.params.id} not found`,
    resolution: {
      action: "list_checkpoints",
      requires: "GET /anip/checkpoints to find valid checkpoint IDs",
      grantable_by: null,
      estimated_availability: null,
    },
    retry: false,
  },
});
```

**Step 4: Run tests to verify they pass**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/fastify`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add packages/typescript/fastify/src/routes.ts packages/typescript/fastify/tests/routes.test.ts
git commit -m "fix(fastify): return structured ANIPFailure for auth errors (#39)"
```

---

### Task 5: Update existing tests that assert on old error format

**Files:**
- Modify: `packages/python/anip-fastapi/tests/test_routes.py` (`test_checkpoint_not_found`)
- Modify: `packages/typescript/hono/tests/routes.test.ts` (checkpoint 404)
- Modify: `packages/typescript/express/tests/routes.test.ts` (checkpoint 404)
- Modify: `packages/typescript/fastify/tests/routes.test.ts` (checkpoint 404)

**Step 1: Update checkpoint-not-found tests**

FastAPI:
```python
def test_checkpoint_not_found(self, client):
    resp = client.get("/anip/checkpoints/ckpt-nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["success"] is False
    assert data["failure"]["type"] == "not_found"
```

Hono:
```typescript
it("GET /anip/checkpoints/:id returns 404 for unknown", async () => {
  const { app } = await makeApp();
  const res = await app.request("/anip/checkpoints/ckpt-nonexistent");
  expect(res.status).toBe(404);
  const data = await res.json();
  expect(data.success).toBe(false);
  expect(data.failure.type).toBe("not_found");
});
```

Same pattern for Express and Fastify checkpoint 404 tests.

**Step 2: Run all binding tests**

Run:
```bash
cd packages/python && pytest anip-fastapi/tests/test_routes.py -v
cd packages/typescript && npm test --workspace=@anip-dev/hono && npm test --workspace=@anip-dev/express && npm test --workspace=@anip-dev/fastify
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/python/anip-fastapi/tests/test_routes.py packages/typescript/hono/tests/routes.test.ts packages/typescript/express/tests/routes.test.ts packages/typescript/fastify/tests/routes.test.ts
git commit -m "test: update checkpoint-not-found assertions to match ANIPFailure format (#39)"
```

---

### Task 6: Update example app tests for new auth error format

**Files:**
- Modify: `examples/anip/tests/test_flight_service.py`
- Modify: `examples/anip-ts/tests/flight-service.test.ts`

**Step 1: Update auth error assertions**

In `test_flight_service.py`, update `test_unauthenticated_rejected` and `test_invoke_without_auth`:

```python
def test_unauthenticated_rejected(self, client):
    resp = client.post("/anip/tokens", json={"scope": ["travel.search"]})
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["failure"]["type"] == "authentication_required"
    assert data["failure"]["resolution"]["action"] == "provide_api_key"

def test_invoke_without_auth(self, client):
    resp = client.post(
        "/anip/invoke/search_flights",
        json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["success"] is False
    assert data["failure"]["type"] == "authentication_required"
    assert data["failure"]["resolution"]["action"] == "obtain_delegation_token"
```

In `flight-service.test.ts`, update the two equivalent tests:

```typescript
it("rejects unauthenticated request", async () => {
  const res = await app.request("/anip/tokens", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope: ["travel.search"] }),
  });
  expect(res.status).toBe(401);
  const data = await res.json();
  expect(data.success).toBe(false);
  expect(data.failure.type).toBe("authentication_required");
  expect(data.failure.resolution.action).toBe("provide_api_key");
});

it("rejects unauthenticated invoke", async () => {
  const res = await app.request("/anip/invoke/search_flights", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" } }),
  });
  expect(res.status).toBe(401);
  const data = await res.json();
  expect(data.success).toBe(false);
  expect(data.failure.type).toBe("authentication_required");
  expect(data.failure.resolution.action).toBe("obtain_delegation_token");
});
```

**Step 2: Run example app tests**

Run:
```bash
cd examples/anip && pip install -e ".[dev]" && pytest tests/ -v
cd examples/anip-ts && npm test
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add examples/anip/tests/test_flight_service.py examples/anip-ts/tests/flight-service.test.ts
git commit -m "test: update example app auth assertions for ANIPFailure format (#39)"
```

---

## Workstream 2: Test Coverage Expansion (#40)

### Task 7: FastAPI — Add permissions and audit endpoint tests

**Files:**
- Modify: `packages/python/anip-fastapi/tests/test_routes.py`

**Step 1: Write the tests**

```python
class TestPermissionsRoute:
    def _get_token(self, client, scope=None):
        resp = client.post(
            "/anip/tokens",
            json={"scope": scope or ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        return resp.json()["token"]

    def test_permissions_returns_available(self, client):
        token = self._get_token(client)
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "restricted" in data
        assert "denied" in data
        cap_names = [c["capability"] for c in data["available"]]
        assert "greet" in cap_names

    def test_permissions_shows_restricted_for_missing_scope(self, client):
        """A token with no matching scope should show capabilities as restricted."""
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["unrelated"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        assert "greet" in restricted_names


class TestAuditRoute:
    def test_audit_returns_entries(self, client):
        # First invoke to create an audit entry
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        token = resp.json()["token"]

        client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Query audit
        resp = client.post(
            "/anip/audit",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "count" in data
        assert data["count"] >= 1

    def test_audit_with_capability_filter(self, client):
        resp = client.post(
            "/anip/tokens",
            json={"scope": ["greet"], "capability": "greet"},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        token = resp.json()["token"]

        client.post(
            "/anip/invoke/greet",
            json={"parameters": {"name": "World"}},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = client.post(
            "/anip/audit?capability=greet",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["capability_filter"] == "greet"
```

**Step 2: Run tests**

Run: `cd packages/python && pytest anip-fastapi/tests/test_routes.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/python/anip-fastapi/tests/test_routes.py
git commit -m "test(fastapi): add permissions and audit endpoint tests (#40)"
```

---

### Task 8: Hono — Add permissions and audit endpoint tests

**Files:**
- Modify: `packages/typescript/hono/tests/routes.test.ts`

**Step 1: Write the tests**

```typescript
describe("Permissions endpoint", () => {
  it("returns available/restricted/denied buckets", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.available).toBeDefined();
    expect(data.restricted).toBeDefined();
    expect(data.denied).toBeDefined();
    expect(data.available.some((c: any) => c.capability === "greet")).toBe(true);
  });

  it("shows restricted for missing scope", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["unrelated"], "greet");
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.restricted.some((c: any) => c.capability === "greet")).toBe(true);
  });
});

describe("Audit endpoint", () => {
  it("returns entries after invocation", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");

    // Invoke to create audit entry
    await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ parameters: { name: "World" } }),
    });

    // Query audit
    const res = await app.request("/anip/audit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.entries).toBeDefined();
    expect(data.count).toBeGreaterThanOrEqual(1);
  });

  it("filters by capability", async () => {
    const { app } = await makeApp();
    const token = await issueToken(app, ["greet"], "greet");

    await app.request("/anip/invoke/greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ parameters: { name: "World" } }),
    });

    const res = await app.request("/anip/audit?capability=greet", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.capability_filter).toBe("greet");
  });
});
```

**Note:** Reuse the existing `issueToken` helper already defined in the streaming tests section.

**Step 2: Run tests**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/hono`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/typescript/hono/tests/routes.test.ts
git commit -m "test(hono): add permissions and audit endpoint tests (#40)"
```

---

### Task 9: Express — Add permissions and audit endpoint tests

**Files:**
- Modify: `packages/typescript/express/tests/routes.test.ts`

**Step 1: Write the tests**

Follow Express test patterns (`supertest` + `request(app)`):

```typescript
describe("Permissions endpoint", () => {
  it("returns available/restricted/denied buckets", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    const token = tokenRes.body.token;

    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.available).toBeDefined();
    expect(res.body.restricted).toBeDefined();
    expect(res.body.denied).toBeDefined();
    stop();
  });

  it("shows restricted for missing scope", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["unrelated"], capability: "greet" });
    const token = tokenRes.body.token;

    const res = await request(app)
      .post("/anip/permissions")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.restricted.some((c: any) => c.capability === "greet")).toBe(true);
    stop();
  });
});

describe("Audit endpoint", () => {
  it("returns entries after invocation", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await request(app)
      .post("/anip/tokens")
      .set("Authorization", `Bearer ${API_KEY}`)
      .send({ scope: ["greet"], capability: "greet" });
    const token = tokenRes.body.token;

    await request(app)
      .post("/anip/invoke/greet")
      .set("Authorization", `Bearer ${token}`)
      .send({ parameters: { name: "World" } });

    const res = await request(app)
      .post("/anip/audit")
      .set("Authorization", `Bearer ${token}`)
      .send({});
    expect(res.status).toBe(200);
    expect(res.body.entries).toBeDefined();
    expect(res.body.count).toBeGreaterThanOrEqual(1);
    stop();
  });
});
```

**Step 2: Run tests**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/express`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/typescript/express/tests/routes.test.ts
git commit -m "test(express): add permissions and audit endpoint tests (#40)"
```

---

### Task 10: Fastify — Add permissions and audit endpoint tests

**Files:**
- Modify: `packages/typescript/fastify/tests/routes.test.ts`

**Step 1: Write the tests**

Use Fastify's `app.inject()` pattern:

```typescript
describe("Permissions endpoint", () => {
  it("returns available/restricted/denied buckets", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { Authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;

    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { Authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.available).toBeDefined();
    expect(data.restricted).toBeDefined();
    expect(data.denied).toBeDefined();
    stop();
  });

  it("shows restricted for missing scope", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { Authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["unrelated"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;

    const res = await app.inject({
      method: "POST",
      url: "/anip/permissions",
      headers: { Authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.restricted.some((c: any) => c.capability === "greet")).toBe(true);
    stop();
  });
});

describe("Audit endpoint", () => {
  it("returns entries after invocation", async () => {
    const { app, stop } = await makeApp();
    const tokenRes = await app.inject({
      method: "POST",
      url: "/anip/tokens",
      headers: { Authorization: `Bearer ${API_KEY}` },
      payload: { scope: ["greet"], capability: "greet" },
    });
    const token = JSON.parse(tokenRes.payload).token;

    await app.inject({
      method: "POST",
      url: "/anip/invoke/greet",
      headers: { Authorization: `Bearer ${token}` },
      payload: { parameters: { name: "World" } },
    });

    const res = await app.inject({
      method: "POST",
      url: "/anip/audit",
      headers: { Authorization: `Bearer ${token}` },
      payload: {},
    });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.entries).toBeDefined();
    expect(data.count).toBeGreaterThanOrEqual(1);
    stop();
  });
});
```

**Step 2: Run tests**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/fastify`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add packages/typescript/fastify/tests/routes.test.ts
git commit -m "test(fastify): add permissions and audit endpoint tests (#40)"
```

---

### Task 11: Example apps — Add permissions, audit, and failure scenario tests

**Files:**
- Modify: `examples/anip/tests/test_flight_service.py`
- Modify: `examples/anip-ts/tests/flight-service.test.ts`

**Step 1: Write Python example tests**

Add to `test_flight_service.py`:

```python
class TestPermissions:
    def test_permissions_show_search_and_book(self, client, auth_headers):
        resp = client.post("/anip/permissions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        cap_names = [c["capability"] for c in data["available"]]
        assert "search_flights" in cap_names
        assert "book_flight" in cap_names

    def test_permissions_restricted_without_book_scope(self, client):
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "scope": ["travel.search"],
                "capability": "search_flights",
                "purpose_parameters": {"task_id": "test"},
            },
        )
        token = resp.json()["token"]
        resp = client.post(
            "/anip/permissions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        restricted_names = [c["capability"] for c in data["restricted"]]
        assert "book_flight" in restricted_names


class TestAudit:
    def test_audit_returns_entries(self, client, auth_headers):
        client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )

        resp = client.post("/anip/audit", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert "entries" in data

    def test_audit_filter_by_capability(self, client, auth_headers):
        client.post(
            "/anip/invoke/search_flights",
            headers=auth_headers,
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )

        resp = client.post(
            "/anip/audit?capability=search_flights",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["capability_filter"] == "search_flights"


class TestFailureScenarios:
    def test_scope_mismatch(self, client):
        """Use a search-only token to try booking."""
        resp = client.post(
            "/anip/tokens",
            headers={"Authorization": "Bearer demo-human-key"},
            json={
                "subject": "human:samir@example.com",
                "scope": ["travel.search"],
                "capability": "search_flights",
                "purpose_parameters": {"task_id": "test-scope"},
            },
        )
        token = resp.json()["token"]

        resp = client.post(
            "/anip/invoke/book_flight",
            headers={"Authorization": f"Bearer {token}"},
            json={"parameters": {"flight_number": "AA100", "date": "2026-03-10", "passengers": 1}},
        )
        data = resp.json()
        assert data["success"] is False

    def test_unknown_capability(self, client, auth_headers):
        resp = client.post(
            "/anip/invoke/cancel_flight",
            headers=auth_headers,
            json={"parameters": {}},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "unknown_capability"

    def test_invoke_with_invalid_token(self, client):
        """Invalid JWT should return structured invalid_token error."""
        resp = client.post(
            "/anip/invoke/search_flights",
            headers={"Authorization": "Bearer garbage-jwt-string"},
            json={"parameters": {"origin": "SEA", "destination": "SFO", "date": "2026-03-10"}},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert data["success"] is False
        assert data["failure"]["type"] == "invalid_token"
```

**Step 2: Write TypeScript example tests**

Add to `flight-service.test.ts`:

```typescript
describe("Permissions", () => {
  it("shows search and book as available", async () => {
    const token = await getToken("search_flights");
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    const names = data.available.map((c: any) => c.capability);
    expect(names).toContain("search_flights");
    expect(names).toContain("book_flight");
  });

  it("shows book_flight as restricted without book scope", async () => {
    const token = await getToken("search_flights", ["travel.search"]);
    const res = await app.request("/anip/permissions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    const restricted = data.restricted.map((c: any) => c.capability);
    expect(restricted).toContain("book_flight");
  });
});

describe("Audit", () => {
  it("returns entries after invocation", async () => {
    const token = await getToken("search_flights");
    await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" },
      }),
    });

    const res = await app.request("/anip/audit", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.count).toBeGreaterThanOrEqual(1);
    expect(data.entries).toBeDefined();
  });

  it("filters by capability", async () => {
    const token = await getToken("search_flights");
    await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" },
      }),
    });

    const res = await app.request("/anip/audit?capability=search_flights", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.capability_filter).toBe("search_flights");
  });
});

describe("Failure scenarios", () => {
  it("scope mismatch — search token for booking", async () => {
    const token = await getToken("search_flights", ["travel.search"]);
    const res = await app.request("/anip/invoke/book_flight", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { flight_number: "AA100", date: "2026-03-10", passengers: 1 },
      }),
    });
    const data = await res.json();
    expect(data.success).toBe(false);
  });

  it("unknown capability returns 404", async () => {
    const token = await getToken("search_flights");
    const res = await app.request("/anip/invoke/cancel_flight", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ parameters: {} }),
    });
    expect(res.status).toBe(404);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("unknown_capability");
  });

  it("invalid JWT returns structured invalid_token error", async () => {
    const res = await app.request("/anip/invoke/search_flights", {
      method: "POST",
      headers: {
        "Authorization": "Bearer garbage-jwt-string",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        parameters: { origin: "SEA", destination: "SFO", date: "2026-03-10" },
      }),
    });
    expect(res.status).toBe(401);
    const data = await res.json();
    expect(data.success).toBe(false);
    expect(data.failure.type).toBe("invalid_token");
  });
});
```

**Step 2: Run tests**

Run:
```bash
cd examples/anip && pip install -e ".[dev]" && pytest tests/ -v
cd examples/anip-ts && npm test
```
Expected: ALL PASS

**Step 3: Commit**

```bash
git add examples/anip/tests/test_flight_service.py examples/anip-ts/tests/flight-service.test.ts
git commit -m "test: add permissions, audit, and failure scenario tests to example apps (#40)"
```

---

### Task 12: Binding tests — Add health endpoint tests for Express and Fastify

**Files:**
- Modify: `packages/typescript/express/tests/routes.test.ts`
- Modify: `packages/typescript/fastify/tests/routes.test.ts`

**Context:** FastAPI and Hono already have health endpoint tests. Express and Fastify don't.

**Step 1: Write Express health tests**

```typescript
describe("Health endpoint", () => {
  it("is not registered by default", async () => {
    const { app, stop } = await makeApp();
    const res = await request(app).get("/-/health");
    expect(res.status).toBe(404);
    stop();
  });

  it("returns health report when enabled", async () => {
    const { app, stop } = await makeApp({ healthEndpoint: true });
    const res = await request(app).get("/-/health");
    expect(res.status).toBe(200);
    expect(res.body.status).toBeDefined();
    expect(res.body.storage).toBeDefined();
    expect(res.body.retention).toBeDefined();
    stop();
  });
});
```

**Note:** Check if Express `makeApp` accepts options for `mountAnip`. If it doesn't, update `makeApp` to pass through `{ healthEndpoint }`.

**Step 2: Write Fastify health tests**

```typescript
describe("Health endpoint", () => {
  it("is not registered by default", async () => {
    const { app, stop } = await makeApp();
    const res = await app.inject({ method: "GET", url: "/-/health" });
    expect(res.statusCode).toBe(404);
    stop();
  });

  it("returns health report when enabled", async () => {
    const { app, stop } = await makeApp({ healthEndpoint: true });
    const res = await app.inject({ method: "GET", url: "/-/health" });
    expect(res.statusCode).toBe(200);
    const data = JSON.parse(res.payload);
    expect(data.status).toBeDefined();
    expect(data.storage).toBeDefined();
    expect(data.retention).toBeDefined();
    stop();
  });
});
```

**Step 3: Run tests**

Run: `cd packages/typescript && npm test --workspace=@anip-dev/express && npm test --workspace=@anip-dev/fastify`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add packages/typescript/express/tests/routes.test.ts packages/typescript/fastify/tests/routes.test.ts
git commit -m "test(express,fastify): add health endpoint tests (#40)"
```

---

### Task 13: Final cross-binding test run

**Step 1: Run all Python tests**

Run: `cd packages/python && pytest anip-fastapi/tests/ -v`
Expected: ALL PASS

**Step 2: Run all TypeScript binding tests**

Run:
```bash
cd packages/typescript
npm test --workspace=@anip-dev/hono
npm test --workspace=@anip-dev/express
npm test --workspace=@anip-dev/fastify
```
Expected: ALL PASS

**Step 3: Run both example app tests**

Run:
```bash
cd examples/anip && pytest tests/ -v
cd examples/anip-ts && npm test
```
Expected: ALL PASS

**Step 4: Commit (if any fixups needed)**

Only if test failures required changes.

---

## Summary

| Task | Workstream | What |
|------|-----------|------|
| 1 | #39 | FastAPI: fix resolver + auth errors + invalid token tests |
| 2 | #39 | Hono: fix resolver + auth errors + invalid token tests |
| 3 | #39 | Express: fix resolver + auth errors + invalid token tests |
| 4 | #39 | Fastify: fix resolver + auth errors + invalid token tests |
| 5 | #39 | Update checkpoint-not-found test assertions |
| 6 | #39 | Update example app auth assertions |
| 7 | #40 | FastAPI permissions + audit tests |
| 8 | #40 | Hono permissions + audit tests |
| 9 | #40 | Express permissions + audit tests |
| 10 | #40 | Fastify permissions + audit tests |
| 11 | #40 | Example app permissions + audit + failure + invalid token tests |
| 12 | #40 | Express + Fastify health tests |
| 13 | #40 | Final cross-binding test run |
