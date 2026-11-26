# ANIP as an MCP extension: concept mapping

Nov 26, 2026 · @Samir

## Summary

ANIP's service-owned capability contract can move into MCP in three pieces: additions to an experimental draft MCP already has, and two small new extensions for structured refusals and approval grants. That would replace maintaining ANIP as a separate wire protocol. It is a working paper for two readers: MCP maintainers and server authors who can say whether the idea is wanted, and the ANIP author deciding how much is worth porting.

It asks three questions:

- Do MCP's experimental tool-annotation drafts want ANIP's reversibility window and review reasons?
- Are structured refusals and approval by a third party wanted as extensions, and which group would own them?
- Is the scenario-based conformance method useful to MCP server authors even without the extension?

Since the first draft, the conformance part has been built as a standalone harness and run against GitHub's MCP server, with two findings. The extensions themselves are not implemented yet. The mapping is from a reading of both specifications, listed under Sources. The harness results, and ANIP's prior art on undo and cost, have been posted to MCP's Tool Annotations Interest Group, which runs the experimental repository where the closest draft lives.

## Evidence so far

A harness built on ANIP's contract-testing method found two wrong annotations in GitHub's MCP server v2.3.0, and no counterexample among 25 read-only claims.

[`mcp-annotation-check`](https://github.com/anip-protocol/mcp-annotation-check) calls a server's tools against known fixtures and reads state before and after through GitHub's REST API, a different channel from the server under test. It tests only explicit claims, quotes the schema's definition of the hint in every result, and treats a pass as "no counterexample on these fixtures". It is Apache-2.0, built on the official MCP Python SDK, and carries no ANIP branding.

The run used the image `ghcr.io/github/github-mcp-server:v2.3.0` locally over stdio, with default toolsets and the `issues_granular` flag. The server listed 62 tools.

| Claim | Tools claiming it | Tested | Result |
| --- | --- | --- | --- |
| `readOnlyHint: true` | 27 | 25 | 25 pass |
| `destructiveHint: false` | 15 | 6 | 2 findings, 3 observations, 1 pass |
| `idempotentHint: true` | 1 | 0 | Skipped, because the tool starts Copilot work |

The two findings:

- **`update_issue_labels`** claims to be non-destructive. Labels `c` and `d` were replaced by `a`. Its own description says it replaces the current labels.
- **`update_issue_assignees`** makes the same claim. An empty list removed the existing assignee.

Both wrong annotations sit on tools whose descriptions say "replaces", so the description was right and the annotation was not. That suggests a cheap static check: compare annotations with descriptions.

Three more tools (`update_issue_title`, `update_issue_body`, `update_issue_state`) overwrite a single value with exactly what the caller supplied. They are recorded as observations. The question put to the group is whether that counts as "only additive updates".

The results were posted on [github-mcp-server#3760](https://github.com/github/github-mcp-server/issues/3760#issuecomment-7184390137) and on the Interest Group's audit thread, as [method and first results](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/issues/10#issuecomment-7184047670) and [sweep results](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/issues/10#issuecomment-7186607131). The author reports no response as of 26 November 2026.

Three limits apply. The results cover one server, one release and one configuration. Nine `destructiveHint: false` tools and two team tools are untested. The read-only comparison covers labels, refs, issues and the main fields of one fixed issue and one fixed pull request, and does not cover releases, milestones or collaborators. Full numbers are in the [round 1 report](https://github.com/anip-protocol/mcp-annotation-check/blob/main/results/2026-11-26-github-mcp-server-v2.3.0-round-1.md).

## What ANIP adds

ANIP's distinct idea is that the server states, in structured and checkable form, what a call will do, who may make it and how to recover when it is refused. MCP carries most of that as free text today.

ANIP's own MCP adapter shows the gap. [`anip-mcp`](https://github.com/anip-protocol/anip/tree/main/packages/python/anip-mcp) writes side effects, cost and scope into the tool description as prose ("WARNING: IRREVERSIBLE action") and returns a refusal as text lines with `isError: true`. An MCP client can show that text to a model but cannot act on it mechanically.

Five ideas from the [ANIP specification](https://github.com/anip-protocol/anip/blob/main/SPEC.md) are worth carrying over:

1. **Graded side effects with a rollback window.** Every capability declares `read`, `write`, `irreversible` or `transactional`, plus how long the action can be undone (section 4.2).
2. **Permission discovery before the call.** The server sorts capabilities into available, restricted and denied for the caller, with a reason type and who can grant what is missing (section 4.4).
3. **Refusals that say how to recover.** A failure carries a type, one of 18 canonical resolution actions, a coarse recovery class and the grantor (section 4.5).
4. **Approval as a bound object.** An approval request stores digests of the parameters and the preview. The grant is signed, one-time or session-bound, and consumed atomically before side effects run (sections 4.7 to 4.9).
5. **Input resolution.** Each input can declare how its value is produced and what happens when it is missing, ambiguous or unresolved (section 4.10).

## Mapping

Most of ANIP's contract has a home in work MCP already has under way; two pieces need a new extension. "MCP today" covers the 2026-07-28 specification and the experimental drafts named.

| ANIP concept | MCP today | Proposed home | Verdict |
| --- | --- | --- | --- |
| Side-effect type (4.2) | Core hints `readOnlyHint`, `destructiveHint`, `idempotentHint`. The experimental [`action-metadata`](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/blob/main/specification/draft/action-metadata.mdx) draft adds `outcome`: benign, consequential or irreversible | Contribute to `action-metadata`: map ANIP's four types onto `outcome` | Contribute |
| Rollback window (4.2) | Nothing released. PR #11 on the experimental repository proposes undo and cost fields | A reversibility duration beside `outcome` | Posted as prior art on PR #11 |
| Approval needed, static (4.7) | `requiresReview` boolean in `action-metadata`; the draft asks whether it needs a machine-readable reason | Offer a reason field and ANIP's vocabulary | Propose upstream |
| Approval request and grant (4.7 to 4.9) | Elicitation covers confirmation by the calling user. Tasks can pause at `input_required`. Nothing binds a third party's approval to exact parameters | New extension: approval grants | New |
| Structured refusal and recovery (4.5) | `isError: true` with free text, JSON-RPC errors, and a 403 `insufficient_scope` challenge that lists required scopes | New extension: a refusal object on error results | New |
| Permission discovery (4.4) | `tools/list` may vary by the caller's authorization. [SEP-1862](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/1862) proposes `tools/resolve` for argument-specific metadata before a call | Bring "restricted, and who can grant it" to SEP-1862 as a use case | Contribute |
| Delegation tokens (4.3) | OAuth 2.1 with protected resource metadata, plus stable authorization extensions | Use MCP authorization. Raise purpose binding and budget limits as questions | Drop the format |
| Input resolution (4.10) | JSON Schema `enum` and `default` in `inputSchema`; elicitation for missing input | Schema annotation keys, following the `x-mcp-header` precedent | Later |
| Cost and budget (5.1) | Nothing released. PR #11 on the experimental repository proposes undo and cost fields | ANIP's cost-certainty levels, offered on PR #11 | Posted as prior art on PR #11 |
| Binding requirements (4.1) | Non-normative guidance to pass state handles as arguments | Vendor annotation | Later |
| Signed manifest, trust levels (7.1) | Annotations are untrusted unless the server is trusted. The [`trust-annotations`](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations/blob/main/specification/draft/trust-annotations.mdx) draft has an `evidenceRef` pointer for out-of-band proof | Offer the signed manifest as an `evidenceRef` scheme | Adapt |
| Audit log and Merkle checkpoints (6.5, 7.3) | Nothing in core. Audit records are listed as a candidate `evidenceRef` scheme | Offer checkpoint proofs as a scheme | Later |
| Composition and cross-service contracts (4.1, 4.6) | Nothing equivalent | Not in a first cut | Drop for now |
| Discovery document and manifest endpoint (6.1) | `server/discover`, and Server Cards in beta | Use MCP's | Drop |
| Transports and streaming (6.6, 11) | Streamable HTTP, stdio, progress and Tasks | Use MCP's | Drop |

## Already covered by MCP

Six ANIP features should defer to what MCP has, because re-proposing them would read as a rival protocol.

- **Authentication and scopes.** MCP uses OAuth 2.1. A server answers a call that lacks scope with 403 and a `WWW-Authenticate` challenge naming the scopes needed, and the client steps up. ANIP's `insufficient_scope` and `request_broader_scope` should ride on that challenge.
- **Filtering tools by caller.** The specification lets `tools/list` return only the tools the caller's granted scopes permit. That is ANIP's "available" list.
- **Clarifying missing input.** A server can answer `tools/call` with an input-required result and an elicitation request, and the client retries with the answers. That covers ANIP's `clarify` behaviour.
- **Long waits.** The Tasks extension, in beta and headed for core, has `working` and `input_required` states and durable handles. An approval that takes hours fits there.
- **Discovery and caching.** `server/discover` advertises capabilities and extensions with a time-to-live, and Server Cards cover discovery before connecting.
- **Human confirmation.** The specification already says a human should be able to deny a tool call, and `requiresReview` in the experimental draft lets a tool author ask for it.

## What to drop

None of the following should be carried into the extension work. Each is either MCP's job already or internal to an implementation.

- **Service-issued delegation tokens.** The `/anip/tokens` endpoint, the JWT format and the delegation graph compete with MCP authorization. Keep the ideas of purpose binding and budget limits as questions for the authorization discussion.
- **The wire protocol.** `/.well-known/anip`, the manifest and invoke endpoints, the unimplemented handshake, and the HTTP, stdio and gRPC bindings.
- **Generated REST and GraphQL surfaces.** They are outside MCP's scope.
- **Compliance levels.** "ANIP-compliant" and "ANIP-complete" have no meaning inside MCP; extension negotiation replaces them.
- **Capability composition and cross-service contracts.** They are recent additions (v0.21 and v0.23) and would widen the proposal past what a first review can absorb.
- **Runtime internals.** Observability hooks, horizontal scaling, storage redaction and audit aggregation are implementation choices.
- **Four of the five runtimes, for this work.** MCP asks for a reference implementation in an official SDK before an extension proposal is reviewed. One language is enough to start.

## Status of ANIP

ANIP is frozen to security fixes as of November 2026, and its ideas continue as MCP extensions and tooling.

- The hosted Studio, Registry and Playground were shut down on 26 November 2026.
- The repository, the documentation at anip.dev, the specification and the published packages remain as a reference.
- The harness described under Evidence so far is the first piece delivered. Planned next are `dev.anip/refusal`, then `dev.anip/approval-grants`.

## Extension sketch

The work splits into three pieces, ordered by how little each asks of anyone else. All field names below are proposals, and the examples omit the `_meta` fields MCP requires on every request.

### 1. Additions to action metadata

This piece needs no new extension. Prototype the fields under a vendor key, then propose them to the Tool Annotations group for the `action-metadata` draft.

```json
{
  "name": "transfer_funds",
  "annotations": {
    "io.modelcontextprotocol/action-metadata": {
      "outcome": "irreversible",
      "requiresReview": true
    },
    "dev.anip/action": {
      "reversibleFor": null,
      "reviewReason": "amount_over_threshold",
      "minimumScope": ["payments.transfer"]
    }
  }
}
```

ANIP's `write` with a rollback window becomes `outcome: consequential` with `reversibleFor` set to an ISO 8601 duration. `transactional` has no counterpart in the draft and is a question to raise.

### 2. Structured refusals: `dev.anip/refusal`

A server that refuses a call returns a normal tool error and adds a refusal object in the result's `_meta`. Clients that do not know the extension still get the text.

```json
{
  "isError": true,
  "content": [
    { "type": "text", "text": "Refused: transfers over $10,000 need approval." }
  ],
  "_meta": {
    "dev.anip/refusal": {
      "type": "approval_required",
      "action": "request_approval",
      "recoveryClass": "wait_then_retry",
      "retry": false,
      "grantableBy": "role:treasury-approver"
    }
  }
}
```

`type`, `action` and `recoveryClass` reuse ANIP's vocabularies from section 4.5, cut down to the values that still make sense once delegation tokens are gone.

### 3. Approval grants: `dev.anip/approval-grants`

This piece depends on the refusal object. The flow has four steps:

1. The client calls the tool. The server stores an approval request and refuses, with the request ID, a digest of the parameters, a digest of the preview and an expiry inside the refusal object.
2. An approver reviews the preview outside the MCP session and issues a grant. How the approver is reached is the server's business.
3. The client retries the same call with the grant ID in the request's `_meta`.
4. The server checks the grant against the capability, the caller and the parameter digest, reserves it atomically, then runs the tool.

```json
{
  "method": "tools/call",
  "params": {
    "name": "transfer_funds",
    "arguments": { "from": "acct-1", "to": "acct-2", "amount": 50000 },
    "_meta": { "dev.anip/approval-grant": "grant_8a7c" }
  }
}
```

A retry with changed arguments, a spent one-time grant or an expired grant is refused before any side effect. Those rules come from ANIP section 4.8 unchanged.

### Negotiation and fallback

Both new extensions follow MCP's extension rules. The identifier uses a reversed domain you own, so `anip.dev` gives the prefix `dev.anip`. The server lists the extensions under `capabilities.extensions` in its `server/discover` response, and the client lists them in the client capabilities it sends with each request. Extensions are off by default. A third-party extension under your own prefix needs no approval from MCP maintainers. After a breaking change, an experimental extension should carry a `revision` string in its settings so peers can detect a mismatch.

## Conformance

ANIP's scenario method ports directly: each declared behaviour gets a scenario that a harness runs against any MCP server. This is the part most useful on its own, because it can test the hints MCP servers already publish. That part now exists as the mcp-annotation-check harness, which covers the first row below and also checks the destructive and idempotent hints.

ANIP has two suites today. [`conformance/`](https://github.com/anip-protocol/anip/tree/main/conformance) checks protocol behaviour against a running service: discovery, tokens and delegation, permissions, invocation, failures, audit, checkpoints, budgets and bindings. It does not yet cover approvals. [`contract-tests/`](https://github.com/anip-protocol/anip/tree/main/contract-tests) checks that a service does what it declares, using per-domain test packs.

| Scenario | What the harness checks on an MCP server | Needs the extension |
| --- | --- | --- |
| Read purity | A tool marked `readOnlyHint` or `outcome: benign` leaves state unchanged | No |
| Reversal works | A tool that declares a reversal window has a working undo path, driven by a test pack | Piece 1 |
| Refusal shape | A denied call returns a refusal object with a valid type, action and recovery class | Piece 2 |
| Scope agreement | The scope named in a refusal matches the scope in the 403 challenge | Piece 2 |
| Approval is stored | An approval refusal always points to a retrievable approval request | Piece 3 |
| Parameter drift | A grant used with changed arguments is rejected | Piece 3 |
| Grant reuse and expiry | A spent one-time grant and an expired grant are both rejected before side effects | Piece 3 |
| Concurrent use | Two simultaneous calls with one grant do not both succeed | Piece 3 |

Two limits apply. Read purity cannot be fully verified from outside a server, which ANIP's own specification says of its equivalent check. And MCP requires a conformance scenario plus two independent, interoperating implementations before an extension can become stable, so this suite is also the route to that stage.

## Open questions

For the [Tool Annotations Interest Group](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/community/interest-groups/tool-annotations.mdx):

- Does `action-metadata` want a reversibility window, or is the three-value `outcome` enough?
- Is there a place for `transactional`, meaning the action fully succeeds or fully rolls back?
- The draft asks whether `requiresReview` needs a machine-readable reason. Would a short closed vocabulary help, and who should own it?
- Should a structured refusal live in a result's `_meta`, in `structuredContent`, or in a core error shape? Is anyone already proposing one?
- Does SEP-1862 intend `tools/resolve` to answer "you cannot call this, and here is who can grant it"?

For MCP maintainers more broadly:

- Is approval by someone other than the calling user wanted as an extension, or is it left to gateways and the interceptor work in [SEP-2624](https://github.com/modelcontextprotocol/experimental-ext-interceptors)?
- An official extension needs a Working Group or Interest Group behind it and a named Extension Maintainer. Which group would be the home for refusals and approval grants?

For the ANIP author:

- Which official SDK carries the reference implementation, Python or TypeScript? The existing `anip-mcp` adapter exists in both.
- Settled on 26 November 2026: ANIP is frozen to security fixes, and the harness and the extensions carry the work forward.

## Sources

Everything above comes from reading four public repositories as cloned on 25 November 2026.

| Repository | Commit | What was read |
| --- | --- | --- |
| [anip-protocol/anip](https://github.com/anip-protocol/anip) | `a27e6f4`, 13 Nov 2026 | `SPEC.md` v0.24 sections 1 to 4.5, 4.7 to 4.10, 5.1, 5.4, 6.1, 6.2, 7.1, 7.2 and 8 to 14; the Python `anip-mcp` translation and invocation modules; `docs/adapters/parity.md`; the contract-testing design note |
| [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) | `2bbace5`, 24 Nov 2026 | Extensions overview; the 2026-07-28 Tools page; the scope-challenge part of Authorization; the start of Multi Round-Trip Requests; `ToolAnnotations` in the schema; the Tool Annotations charter; the abstracts of SEP-2127 and SEP-2484; the status list in the Tasks overview |
| [experimental-ext-tool-annotations](https://github.com/modelcontextprotocol/experimental-ext-tool-annotations) | `fecace7`, 12 Aug 2026 | README; the `action-metadata` draft; the trust model, open questions, SEP disposition and priorities notes; the `evidenceRef` part of the `trust-annotations` draft |
| [experimental-ext-interceptors](https://github.com/modelcontextprotocol/experimental-ext-interceptors) | `b488d14`, 24 Nov 2026 | README and the abstract of the SEP text |

Added 26 November 2026: the harness results, the posting locations and the ANIP status come from the author's notes of that date. The [round 1 report](https://github.com/anip-protocol/mcp-annotation-check/blob/main/results/2026-11-26-github-mcp-server-v2.3.0-round-1.md) was fetched and its image, tool counts and outcomes match those notes. The pages for issue #10 and github-mcp-server#3760 were fetched too, but the comments did not render for a signed-out reader, so the posted comments and the lack of replies are as the author reports. PR #11 was not read.

Not read or not verified:

- SEP-1862 beyond its one-line summary, and SEP-2787, SEP-1984 and SEP-2624 in full. Their descriptions here come from the documents above, plus one web search result for SEP-1862's summary line.
- The Enterprise-Managed Authorization extension and the full Elicitation page.
- ANIP sections 4.6, 5.2, 5.3, 6.3 to 6.12 and 7.3 to 7.7.
- Whether the Tool Annotations group will respond. Its experimental repository's latest commit was 12 August 2026 when read, and the author reports no reply to the posts of 25 and 26 November.
- No code was run. The example payloads are illustrations and have not been validated against an MCP SDK.
