# Porting a binding to a new major SDK version

Findings from porting the Python `anip-mcp` package from the 1.x to the 2.x
MCP SDK ([#318](https://github.com/anip-protocol/anip/pull/318)). The first
version of that port passed its tests and CI and still lost a behaviour; an
independent review caught it.

## General

In each finding below, only the **Observed** part carries a status. The
**Recommendation** is advice drawn from one port; whether it pays off on other
ports is not yet known.

### 1. The migration guide named the behaviour we lost

- **Observed:** The 2.x migration guide states in one sentence that automatic
  argument validation was removed with no replacement
  ([guide](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/migration.md#lowlevel-server-decorator-based-handlers-replaced-with-constructor-on_-params)).
  The author of #318 read the new SDK's source, not the guide, and missed it.
- **Source:** #318. **Status:** verified.
- **Recommendation:** Read the migration guide in full before reading the new
  API. Search it for "removed", "no longer", "validation" and "default".
- **Applies to:** any SDK port.

### 2. The old SDK did work for us that nobody had written down

- **Observed:** In 1.x the SDK validated tool arguments against the declared
  schema and turned raised exceptions into tool errors. Neither was visible in
  our own code. 2.x does neither.
- **Source:** #318. **Status:** verified.
- **Recommendation:** Before changing code, list what the old SDK does around
  your handlers without being asked (validating arguments, converting
  exceptions, wrapping return values, checking headers, limiting request size).
  For each, decide: the new SDK still does it, we now do it ourselves, or it
  changes on purpose. State the last group in the pull request.
- **Applies to:** any SDK port.

### 3. Refusal tests written before the port held; the missing ones were the gap

- **Observed:** Three tests for token refusals were added before the port,
  passed on 1.x and kept passing on 2.x. No test covered invalid arguments, and
  that is where the regression was. Twelve such tests were added after review.
- **Source:** #318, `tests/test_http_token_auth.py` and
  `tests/test_input_validation.py`. **Status:** verified.
- **Recommendation:** Before porting, add tests on the old version for
  everything that must be refused. Each asserts that the refusal reaches the
  caller and that the capability handler did not run. Cases to consider: a token
  issued for another capability; insufficient scope; no credentials; invalid
  credentials; unknown tool; arguments that break the declared schema (missing
  required, wrong type, null, a boolean or a fraction where an integer is
  required).
- **Applies to:** any binding that sits in front of capabilities.

### 4. The regression could only be seen through the real request path

- **Observed:** Argument validation happened inside the SDK, between the
  request and our handler. Tests that called our helper functions directly
  could not see it disappear.
- **Source:** #318. **Status:** verified.
- **Recommendation:** Test the way a client calls: a real HTTP request, or a
  real client session against the mounted server.
- **Applies to:** any binding.

### 5. A test that passed first time was shown able to fail

- **Observed:** The three token tests passed as soon as they were written. With
  the token check deliberately bypassed, two of them failed; the code was then
  restored.
- **Source:** #318. **Status:** verified.
- **Recommendation:** When a new test passes immediately, break the code on
  purpose to confirm the test notices.
- **Applies to:** everything.

### 6. Tests that read SDK internals broke

- **Observed:** Two tests asserted on `server.request_handlers`, an internal
  table that 2.x removed. One older test joined its assertions with `or`, so it
  could pass without the refusal it was meant to check.
- **Source:** #318. **Status:** verified.
- **Recommendation:** Replace assertions on SDK internals with behaviour tests,
  and be suspicious of assertions joined by `or`.
- **Applies to:** any SDK port.

### 7. Old and new clients both worked against the ported server

- **Observed:** MCP clients 1.30.0 and 2.3.0 each completed a handshake, listed
  tools, called one, and received a tool error for a wrong key against the
  ported server.
- **Source:** #318. **Status:** verified.
- **Recommendation:** After a port, connect a client built on the old SDK as
  well as one built on the new SDK. Existing callers stay on the old one.
- **Applies to:** any protocol binding.

### 8. An independent review found what the author's tests and CI did not

- **Observed:** A reviewer who had not written the port sent the same malformed
  requests to the code before and after it and compared the results. That is
  how the lost validation was found. The author's tests and CI were green.
- **Source:** #318. **Status:** observed once.
- **Recommendation:** Ask for a review that compares behaviour before and after
  for malformed and unauthorized requests.
- **Applies to:** any port.

### 9. Other parts of the repository used the package

- **Observed:** The travel, finance and devops showcases mount the Python MCP
  binding. Their contract tests passed against the port.
- **Source:** #318. **Status:** verified.
- **Recommendation:** Search for imports of the package outside it and run what
  you find.
- **Applies to:** everything.

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
