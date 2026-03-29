# ANIP Stdio Transport Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the native ANIP-over-stdio transport binding in Python — a JSON-RPC 2.0 server that reads from stdin, writes to stdout, and exposes all 9 ANIP protocol operations. Plus a client library for agents to consume ANIP services as subprocesses.

**Architecture:** New Python package `anip-stdio` at `packages/python/anip-stdio/`. The server wraps `ANIPService` and dispatches JSON-RPC methods to the corresponding service calls. The client spawns a subprocess and provides an async API matching the JSON-RPC methods. Both use `asyncio` for I/O.

**Tech Stack:** Python 3.11+, `asyncio`, `ANIPService` from `anip-service`. No external dependencies beyond the ANIP packages.

**Spec:** `docs/specs/2026-03-22-anip-stdio-transport-design.md`

---

## File Structure

```
packages/python/anip-stdio/
├── pyproject.toml
├── src/anip_stdio/
│   ├── __init__.py          # exports serve_stdio, AnipStdioClient
│   ├── server.py            # JSON-RPC server reading stdin, dispatching to ANIPService
│   ├── client.py            # Subprocess client for agents
│   ├── protocol.py          # JSON-RPC message types, error codes, method dispatch table
│   └── framing.py           # Newline-delimited JSON read/write helpers
└── tests/
    ├── test_protocol.py     # Unit tests for message parsing, error mapping
    ├── test_server.py       # Integration tests: dispatch JSON-RPC through server
    ├── test_client.py       # Client spawns server subprocess, runs operations
    └── serve_test.py        # Minimal stdio server for client tests
```

---

## Task 1: Package Scaffold + Framing + Protocol

Create the package, JSON framing helpers, and protocol types with unit tests.

**Files:**
- Create: `packages/python/anip-stdio/pyproject.toml`
- Create: `packages/python/anip-stdio/src/anip_stdio/__init__.py`
- Create: `packages/python/anip-stdio/src/anip_stdio/framing.py`
- Create: `packages/python/anip-stdio/src/anip_stdio/protocol.py`
- Create: `packages/python/anip-stdio/tests/test_protocol.py`

Protocol module defines: 9 valid ANIP method names, JSON-RPC error codes mapped to ANIP failure types, message constructors (make_response, make_error, make_notification), request validation, auth extraction from params.auth.bearer.

Framing module: async read_message (readline + json.loads) and write_message (json.dumps + newline + drain).

Tests: validate all protocol helpers, error codes, method set, auth extraction.

- [ ] Create all files, run tests, commit

---

## Task 2: JSON-RPC Server

The server reads JSON-RPC requests, dispatches to ANIPService methods, returns responses.

**Files:**
- Create: `packages/python/anip-stdio/src/anip_stdio/server.py`
- Create: `packages/python/anip-stdio/tests/test_server.py`

Server class `AnipStdioServer` with method handlers for all 9 operations:
- `anip.discovery` → `service.get_discovery()`
- `anip.manifest` → `service.get_signed_manifest()` → `{manifest, signature}`
- `anip.jwks` → `service.get_jwks()`
- `anip.tokens.issue` → bootstrap-then-JWT auth, `service.issue_token()`
- `anip.permissions` → JWT auth, `service.discover_permissions()`
- `anip.invoke` → JWT auth, `service.invoke()` with optional streaming (progress notifications + final response)
- `anip.audit.query` → JWT auth, `service.query_audit()` with full filter surface (capability, since, invocation_id, client_reference_id, event_class, limit)
- `anip.checkpoints.list` → `service.get_checkpoints(limit)`
- `anip.checkpoints.get` → `service.get_checkpoint(id, options)` with include_proof, leaf_index, consistency_from

`serve_stdio(service)` function: connects stdin/stdout as asyncio streams, loops reading messages, dispatching, and writing responses until EOF. Calls service.start() on entry, service.shutdown()+stop() on exit.

Auth: `anip.tokens.issue` tries `authenticate_bearer()` first (API key), then `resolve_bearer_token()` (JWT sub-delegation). All other protected methods use `resolve_bearer_token()` only.

Streaming: when `anip.invoke` has `stream: true`, progress notifications are sent before the final JSON-RPC response. The response is the single source of truth for the terminal result.

Tests: create an ANIPService with one "echo" capability, test all 9 methods through handle_request(), test auth errors, test unknown methods.

- [ ] Create all files, run tests, commit

---

## Task 3: Stdio Client

An async client that spawns an ANIP service as a subprocess.

**Files:**
- Create: `packages/python/anip-stdio/src/anip_stdio/client.py`
- Create: `packages/python/anip-stdio/tests/test_client.py`
- Create: `packages/python/anip-stdio/tests/serve_test.py`
- Update: `packages/python/anip-stdio/src/anip_stdio/__init__.py`

`AnipStdioClient(*cmd)` — async context manager. Spawns subprocess, connects stdin/stdout. Provides typed methods: discovery(), manifest(), jwks(), issue_token(), permissions(), invoke(), audit_query(), checkpoints_list(), checkpoints_get().

Uses asyncio.create_subprocess_exec (not shell) to spawn the server process.

**Streaming client API:** `invoke()` with `stream=True` returns an `InvokeStream` object (async iterator + result). The caller iterates progress notifications, then accesses the terminal result:

```python
stream = await client.invoke(bearer, "search", params, stream=True)
async for progress in stream:
    print(progress["payload"])  # each progress notification
result = stream.result  # the terminal JSON-RPC response (set after iteration completes)
```

`InvokeStream` reads from the subprocess stdout, yields `anip.invoke.progress` notifications as they arrive, and captures the final JSON-RPC response (matched by `id`) when it appears. This preserves the streaming capability at the client boundary.

`serve_test.py` — minimal ANIP service in stdio mode for client integration tests.

Tests: spawn the test server, run a full flow (discovery → issue_token → invoke → audit_query), verify round-trip correctness.

- [ ] Create all files, run tests, commit

---

## Task 4: Showcase Integration + Release + PR

**Files:**
- Create: `examples/showcase/travel/stdio_server.py`
- Modify: `examples/showcase/travel/requirements.txt`
- Modify: `.github/workflows/release.yml`
- Modify: `.github/workflows/ci-python.yml`

Create a stdio entry point for the travel showcase that agents can spawn as a subprocess. Add anip-stdio to:
- Release workflow validation/publish loops (`.github/workflows/release.yml`)
- Python CI workflow package install/test list (`.github/workflows/ci-python.yml`) — the CI explicitly installs and tests each Python package; anip-stdio must be added alongside the existing packages

Verify with: `echo '{"jsonrpc":"2.0","id":1,"method":"anip.discovery","params":{}}' | python3 examples/showcase/travel/stdio_server.py`

- [ ] Create files, test, update release + CI workflows, commit, push, create PR
