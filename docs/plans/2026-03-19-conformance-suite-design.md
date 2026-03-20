# ANIP Language-Agnostic Conformance Suite Design

**Goal:** A standalone, HTTP-based pytest suite that validates ANIP protocol compliance against any service by URL.

**Architecture:** Flat Python test suite under `conformance/` at the project root. Uses httpx for HTTP, pytest for test execution. No SDK imports, no runtime internals — pure wire-level protocol validation. Shared helpers are thin and protocol-oriented (token issuance, discovery fetch), not a thick client layer.

**Tech Stack:** Python, pytest, httpx, PyJWT + cryptography (for JWT verification against JWKS)

---

## Structure

```
conformance/
├── pyproject.toml              # httpx, pytest, pyjwt, cryptography
├── conftest.py                 # --base-url fixture, thin helpers
├── test_discovery.py           # Discovery + manifest + JWKS
├── test_tokens.py              # Token issuance + delegation
├── test_invoke.py              # Invocation success + failure shapes
├── test_permissions.py         # Scope enforcement + permission queries
├── test_audit.py               # Audit log queries + filtering
├── test_checkpoints.py         # Checkpoint listing + proof behavior
```

## Running

```bash
cd conformance
pip install -e ".[dev]"
pytest --base-url=http://localhost:8090 -v   # Python service
pytest --base-url=http://localhost:4100 -v   # TypeScript service
```

## conftest.py

Provides:

- `--base-url` CLI option (required)
- `base_url` fixture (session-scoped)
- `client` fixture (httpx.AsyncClient, session-scoped)
- `discovery` fixture — fetches `/.well-known/anip` once per session, used by all tests
- `api_token(scope, capability)` — thin helper that POST to `/anip/tokens` with a demo API key, returns the JWT string. Not an abstraction — just avoids repeating the same 5 lines in every test file.

Helpers stay minimal. Tests should visibly construct HTTP requests so the protocol contract is clear in the test code itself.

## Test Coverage

### test_discovery.py (Spec §6.1, Conformance Category 1)

- Discovery document has required fields: `protocol`, `compliance`, `base_url`, `profile`, `auth`, `capabilities`, `endpoints`, `trust_level`
- Declared endpoint URLs are internally consistent with `base_url`
- `compliance` is either `anip-compliant` or `anip-complete`
- Manifest endpoint returns capability declarations
- Manifest includes `X-ANIP-Signature` header (detached JWS)
- JWKS endpoint returns valid key set with ES256 keys
- Endpoint map contains required keys: `manifest`, `invoke`, `tokens`, `permissions`

### test_tokens.py (Spec §4.3, Conformance Category 4)

- Issue token with valid API key returns `issued: true`, `token`, `token_id`, `expires`
- Issued JWT is valid ES256, verifiable against service's JWKS
- Token `expires` is in the future
- Token scoped to specific capability
- Token request without auth returns 401 with structured failure
- Denied token issuance returns structured failure with `type`, `detail`, `resolution`, `retry`

### test_invoke.py (Spec §4.1–4.5, Conformance Categories 3, 5)

- Successful invocation returns `success: true`, `invocation_id` (format `inv-{hex12}`), `result`
- `client_reference_id` echoed back when provided in request
- Unknown capability returns 404 with failure object
- Invocation without auth returns 401 — distinguished from invalid token (also 401 but different `failure.type`)
- Invocation with invalid/malformed token returns 401
- Failure response includes all required fields: `failure.type`, `failure.detail`, `failure.resolution`, `failure.retry`
- `cost_actual` present when capability declares financial cost
- Failure `retry` field is boolean and present

### test_permissions.py (Spec §4.4, Conformance Category 4)

- Query with full-scope token returns capabilities in `available`
- Query with narrow scope moves some capabilities to `restricted`
- Response contains `available`, `restricted`, `denied` arrays
- Each entry has required fields (capability name, reason/scope info)
- Unauthenticated request returns 401 with structured failure

### test_audit.py (Spec §5.4, Conformance Category 6)

- Audit query returns `count` and `entries`
- Filter by `capability` narrows results
- Each entry has `invocation_id`, `capability`, `timestamp`, `success`
- Unauthenticated access returns 401
- Combined filter (e.g., `capability` + `since`) works correctly

### test_checkpoints.py (Spec §6.5)

- List checkpoints returns array with `checkpoint_id`, `merkle_root`, `timestamp`
- Pagination via `next_cursor`
- Not-found checkpoint returns 404
- Proof request behavior: if `include_proof=true` supported, response includes `inclusion_proof` or `proof_unavailable`

## What This Does NOT Test

- Language-specific SDK behavior
- Runtime internals or in-process method calls
- Streaming (SSE) — deferred to a later version
- Behavioral contracts (side-effect accuracy, cost accuracy) — requires sandbox
- Performance or latency

## CI Integration

Add a `conformance` job to CI that:
1. Starts the Python example app
2. Runs `pytest --base-url=http://localhost:8090`
3. Starts the TypeScript example app
4. Runs `pytest --base-url=http://localhost:4100`

Both must pass. This ensures both reference implementations stay conformant.

## Assumptions

- A demo API key (`demo-human-key`) is available on the target service for token issuance
- The target service has at least one read capability and one irreversible/financial capability
- The target service runs the observability and trust profiles (for audit and checkpoint tests)
