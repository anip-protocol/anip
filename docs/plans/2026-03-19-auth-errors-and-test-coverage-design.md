# Auth Error Fix + Test Coverage Expansion — Design

## Goal

Two sequential workstreams:
1. **Fix #39** — Replace generic `{"error": "..."}` auth responses with structured `ANIPFailure` across all 4 framework bindings (16 call sites)
2. **Fix #40** — Fill test coverage gaps: permissions endpoint, audit endpoint, health endpoint, auth error scenarios, failure scenarios in example apps

## Workstream 1: Structured Auth Errors (#39)

### Problem

All framework bindings return `{"error": "Authentication required"}` (a plain string) when auth fails. This violates ANIP's core design principle: every error gives the agent a structured recovery path.

### Fix

Replace all 16 `{"error": "..."}` responses with proper `ANIPFailure` envelopes. Two distinct cases:

**Case A — No bearer token on JWT-authenticated endpoints** (permissions, invoke, audit):
```json
{
  "success": false,
  "failure": {
    "type": "authentication_required",
    "detail": "A valid delegation token (JWT) is required in the Authorization header",
    "resolution": {
      "action": "obtain_delegation_token",
      "requires": "Bearer token from POST /anip/tokens",
      "grantable_by": null,
      "estimated_availability": null
    },
    "retry": true
  }
}
```

**Case B — No API key on token issuance endpoint** (`POST /anip/tokens`):
```json
{
  "success": false,
  "failure": {
    "type": "authentication_required",
    "detail": "A valid API key is required to issue delegation tokens",
    "resolution": {
      "action": "provide_api_key",
      "requires": "API key in Authorization header",
      "grantable_by": null,
      "estimated_availability": null
    },
    "retry": true
  }
}
```

### Scope

| Binding | File | Call sites |
|---------|------|-----------|
| FastAPI | `packages/python/anip-fastapi/src/anip_fastapi/routes.py` | 4 |
| Hono | `packages/typescript/hono/src/routes.ts` | 4 |
| Express | `packages/typescript/express/src/routes.ts` | 4 |
| Fastify | `packages/typescript/fastify/src/routes.ts` | 4 |

Each binding also gets a `_auth_failure()` / `authFailure()` helper to avoid duplicating the response construction.

### Also fix

`{"error": "Checkpoint not found"}` on `GET /anip/checkpoints/:id` — same pattern, should be `ANIPFailure` with `type: "not_found"`.

## Workstream 2: Test Coverage (#40)

### P0 — Zero coverage (must fix)

1. **`POST /anip/permissions`** — Add to all 4 framework binding test suites + both example apps. Test: valid token returns available/restricted/denied buckets.

2. **`POST /anip/audit`** — Add to all 4 framework binding test suites + both example apps. Test: returns entries filtered by root_principal, query with `?capability=X`, `?limit=N`.

3. **Auth error response format** — After workstream 1 fix, add tests validating the `ANIPFailure` structure on 401 responses across all bindings.

### P1 — Thin coverage (should fix)

4. **`GET /-/health`** — Add to Hono, Express, Fastify binding tests + both example apps. Test: disabled by default (404), enabled returns HealthReport, status field present.

5. **Failure scenarios in example apps** — Add to both Python and TS examples:
   - Budget exceeded (book flight over $500 limit)
   - Scope mismatch (search token used for booking)
   - Purpose binding violation (book token used for search)
   - Unknown capability

6. **Hook isolation integration test** — In service layer tests: register a hook that throws, invoke a capability, verify invocation succeeds and returns correct result.

### P2 — Edge cases (nice to have)

7. **Audit query filters** — Test `?capability=`, `?since=`, `?limit=` at HTTP level
8. **Checkpoint detail** — Positive test for `GET /anip/checkpoints/:id` with valid ID
9. **Invalid request bodies** — Missing required fields, malformed JSON

### Estimated new test count

| Area | New tests |
|------|-----------|
| Framework bindings (permissions) | ~8 (2 per binding) |
| Framework bindings (audit) | ~8 (2 per binding) |
| Framework bindings (auth errors) | ~12 (3 per binding) |
| Framework bindings (health) | ~6 (2 per binding, 3 bindings) |
| Example apps (permissions + audit) | ~8 (4 per example) |
| Example apps (failure scenarios) | ~8 (4 per example) |
| Hook isolation integration | ~4 (2 per runtime) |
| **Total** | **~54 new tests** |

## Execution Order

1. Fix auth errors (#39) — must land first since test coverage (#40) depends on the correct error format
2. Add test coverage (#40) — P0 items first, then P1, then P2

## What This Does Not Do

- Add performance/stress tests
- Add concurrent request handling tests
- Add cross-runtime parity assertion tests (structurally enforced by having equivalent test suites)
- Change any protocol semantics
