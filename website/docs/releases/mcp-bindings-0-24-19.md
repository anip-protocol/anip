---
title: "0.24.19: MCP Bindings"
description: Security release for the C# MCP binding. The Python and C# MCP bindings move to the 2.x MCP SDKs.
---

# 0.24.19: MCP Bindings

This release changes the MCP bindings of two runtimes. The protocol version stays `anip/0.24`.

- **C#: a security fix.** `Anip.Mcp.AspNetCore` no longer serves the legacy SSE endpoints, where a tool call could run with another caller's credentials.
- **Python and C#: new MCP SDK major versions.** `anip-mcp` moves to `mcp` 2.x and `Anip.Mcp.AspNetCore` to `ModelContextProtocol.AspNetCore` 2.4.0.

Upgrade if you mount the C# MCP binding. TypeScript, Go and Java are unchanged in this release.

## The C# security fix

**Affected:** `Anip.Mcp.AspNetCore` 0.11.1 through 0.24.18, which is every earlier version.

`MapAnipMcp` mounted two endpoints besides the documented one: `/mcp/sse` and `/mcp/message`, the legacy SSE transport that the MCP SDK mapped by default. A tool call sent over them ran with the `Authorization` header of the request that opened the stream, not of the request that carried the call.

- A caller who knew the session ID of a stream opened with valid credentials could invoke tools as the caller who opened it, with no key, a wrong key, or their own key. The call was recorded in the audit log under the opener's identity.
- The session ID is random and is not a credential, but it travels in the URL of every `/mcp/message` request, so it can appear in access logs and proxy logs.
- A stream opened without credentials gave no authority, and the documented Streamable HTTP endpoint (`/mcp`) checked credentials on every request and was not affected.

The binding no longer maps the legacy endpoints; both paths now answer 404.

**If you cannot upgrade yet:** block `/mcp/sse` and `/mcp/message` (under your mount path) in your reverse proxy or with ASP.NET Core middleware.

**The other runtimes** were checked for the same fault. Python, TypeScript and Go mount only a stateless Streamable HTTP endpoint and read the credential from each request. Java keeps a session, and was probed: a call inside a session with no key or a wrong key is refused, and the legacy paths answer 404.

## What changes for you: C#

`Anip.Mcp.AspNetCore` now builds on `ModelContextProtocol.AspNetCore` 2.4.0. Authentication, authorization and refusal texts are unchanged. The transport behaves differently in these ways:

| | 0.24.18 and earlier | 0.24.19 |
|---|---|---|
| Legacy SSE (`/mcp/sse`, `/mcp/message`) | served | 404. Clients that only speak SSE must move to Streamable HTTP |
| Sessions | `initialize` returned an `Mcp-Session-Id`, and later requests had to carry it | no session ID is issued |
| `tools/call` with no `initialize` before it | 400 | served, and authenticated like any other call |
| A client still holding a session ID from before the upgrade | n/a | 400 on a handshake-era request. Re-initialize |
| MCP protocol revision 2026-07-28 | 400, unsupported | served |
| `GET /mcp`, `DELETE /mcp` | 400 / 200 | 405 |
| `tools/call` with a `task` member | refused | `task` is ignored and the call runs normally |
| Invalid JSON or an empty body | 500 | 400 with a JSON-RPC error |

A request that was refused for missing or invalid credentials before is still refused.

Known limit: the SDK answers some malformed 2026-07-28 requests with a 500, for example a `tools/call` whose `name` is not a string. No tool runs and the server keeps serving.

## What changes for you: Python

`anip-mcp` now requires `mcp>=2.0.0,<3`. It was capped below 2 since 0.24.15. If your own code imports `mcp`, it must work with 2.x; the SDK's [migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/v2.3.0/docs/migration.md) lists what changed.

Authentication, authorization and refusal texts are unchanged. Tool arguments are still validated against the tool's input schema before the capability runs; the 2.x SDK no longer does this, so the binding does it itself and `jsonschema` is now a direct dependency.

| | 0.24.18 and earlier | 0.24.19 |
|---|---|---|
| `Accept: */*` | 406 | accepted. An incompatible `Accept` is still 406 |
| Request body over 4 MiB | accepted | 413 (SDK default) |
| An unexpected exception inside a capability handler | tool result with `isError` | JSON-RPC error |
| OpenTelemetry | not installed | `opentelemetry-api` is installed by the SDK. Spans are no-ops unless you configure an exporter |

Clients built on the 1.x and on the 2.x MCP SDK both work against the upgraded server.

## Not in this release

- The Go and Java MCP bindings still build on earlier major versions of their MCP libraries.
- The C# MCP binding does not validate tool arguments against the input schema, on either SDK version. Capability handlers validate their own parameters.
