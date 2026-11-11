# Porting a binding to a new major SDK version

Findings from porting the Python `anip-mcp` package from the 1.x to the 2.x
MCP SDK ([#318](https://github.com/anip-protocol/anip/pull/318)). The first
version of that port passed its tests and CI and still lost a behaviour; an
independent review caught it.

## General

### 1. Read the migration guide in full before reading the new API

- **Claim:** Read the SDK's migration guide end to end first. Search it for
  "removed", "no longer", "validation" and "default".
- **Applies to:** any SDK port.
- **Source:** #318. The author read the new SDK's source and not its guide. The
  guide states the lost behaviour in one sentence
  ([MCP Python SDK migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/migration.md#lowlevel-server-decorator-based-handlers-replaced-with-constructor-on_-params)).
- **Status:** verified.

### 2. List what the old SDK did for you automatically

- **Claim:** Before changing code, write down everything the old SDK did around
  your handlers without being asked: validating arguments, turning exceptions
  into error results, wrapping return values, checking headers, limiting
  request size. For each item decide: the new SDK still does it, we now do it
  ourselves, or it changes on purpose. State the last group in the pull request.
- **Applies to:** any SDK port.
- **Source:** #318. Argument validation was automatic in 1.x and absent in 2.x.
- **Status:** verified.

### 3. Pin refusal behaviour with tests before the port

- **Claim:** Add tests for what must be *refused*, on the old SDK, before
  porting. They must pass on the old version and keep passing after. Each test
  asserts the refusal reaches the caller **and that the capability handler did
  not run**.
- **Applies to:** any binding that sits in front of capabilities.
- **Cases worth covering:** a token issued for another capability; a token with
  insufficient scope; no credentials; invalid credentials; unknown tool;
  arguments that break the declared schema (missing required, wrong type, null,
  a boolean or a fraction where an integer is required).
- **Source:** #318, `tests/test_http_token_auth.py` and
  `tests/test_input_validation.py`.
- **Status:** verified. The token tests held through the port. The argument
  tests were only written after review found the gap.

### 4. Test through the real request path

- **Claim:** Send the request the way a client would (a real HTTP request, or a
  real client session against the mounted server). Tests that call an internal
  helper do not see what the SDK does or stopped doing around it.
- **Applies to:** any binding.
- **Source:** #318. The regression was invisible to helper-level tests.
- **Status:** verified.

### 5. Make sure a new test can fail

- **Claim:** When a new test passes the first time, break the code on purpose
  and confirm the test notices, then restore it.
- **Applies to:** everything.
- **Source:** #318. The token tests passed immediately; a deliberate break
  confirmed two of the three fail when the check is bypassed.
- **Status:** verified.

### 6. Tests that inspect SDK internals will break, and were weak anyway

- **Claim:** Replace assertions on the SDK's internal tables with behaviour
  tests. Be suspicious of assertions joined by `or`: one of them can hide a
  regression.
- **Applies to:** any SDK port.
- **Source:** #318. Two tests read `server.request_handlers`, which 2.x removed.
- **Status:** verified.

### 7. Check both old and new clients against the new server

- **Claim:** After the port, connect a client built on the old SDK and one built
  on the new SDK. Callers in the wild will be on the old one for a long time.
- **Applies to:** any protocol binding.
- **Source:** #318. MCP clients 1.30.0 and 2.3.0 were both run against the
  ported server.
- **Status:** verified.

### 8. Ask for an independent review that compares behaviour before and after

- **Claim:** Have someone other than the author run the same malformed and
  unauthorized requests against the code before and after the port and compare.
- **Applies to:** any port.
- **Source:** #318. This is what found the lost validation.
- **Status:** observed once.

### 9. Look for other users of the package in the repository

- **Claim:** Search for imports of the package outside it, and run what you find.
- **Applies to:** everything.
- **Source:** #318. The travel, finance and devops showcases mount the Python
  MCP binding; their contract tests were run against the port.
- **Status:** verified.

## Python and the MCP SDK 2.x only

- **Handlers** are passed to `Server(on_list_tools=..., on_call_tool=...)` or
  registered with `server.add_request_handler(method, ParamsType, handler)`.
  They take `(ctx, params)` and return result objects. **Status:** verified.
- **No argument validation.** The binding validates against the tool's input
  schema itself, with `jsonschema`. **Status:** verified.
- **Raised exceptions** no longer become tool errors. Return
  `CallToolResult(..., is_error=True)` for expected refusals. **Status:** verified.
- **The HTTP request** is on `ctx.request`. **Status:** verified.
- **Field names** are snake_case (`input_schema`, `is_error`); the camelCase
  names still work as constructor arguments. **Status:** verified.
- **`mcp.Client(server)`** connects to a server in-process and is the simplest
  way to test a mounted server end to end. **Status:** verified.
- **A wildcard `Accept` header** is now accepted; 1.x answered 406.
  **Status:** verified.
- **Request bodies over 4 MiB** are refused with 413 by default.
  **Status:** unverified (from the guide; not exercised).
- **Not yet fixed:** the GTM showcase's Python code imports
  `streamablehttp_client`, which 2.x no longer exports, and does not limit the
  SDK version. **Status:** verified that the name is gone; the showcase was not run.

## Remaining ports

Measured on 2026-11-11. Sizes are the non-test code that uses the library.

| Runtime | Library | Pinned | Latest stable | Size |
|---|---|---|---|---|
| C# | `ModelContextProtocol.AspNetCore` | 1.1.0 | 2.4.0 | 1 file, about 240 lines |
| Go | `github.com/mark3labs/mcp-go` | 0.45.0 | 1.5.0 | 2 files, about 760 lines in `mcpapi` |
| Java | `io.modelcontextprotocol.sdk:mcp-core` | 1.1.0 | 2.1.0 | 12 files, about 1,070 lines, three modules |

Whether these libraries dropped behaviour in the same way as the Python SDK is
**unverified**. Finding 2 applies to each.
