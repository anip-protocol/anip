# ANIP — Agent-Native Interface Protocol

> REST APIs are simple. ANIP gives agents confidence.

Read the [Manifesto](MANIFESTO.md) | Read the [Spec](SPEC.md) | Read the [Guide](GUIDE.md) | [Contribute](CONTRIBUTING.md)

---

## Why "ANIP"?

**Agent-Native Interface Protocol.** Two words do different work:

- **Interface** — the surface agents interact with. What capabilities exist, what they cost, what authority they require, what they do. ANIP defines the shape of that surface.
- **Protocol** — the rules both parties agree to follow. How discovery works, how delegation chains are validated, how failures are structured. ANIP standardizes those rules.

This follows a well-established naming pattern in networked systems: **HTTP** (HyperText Transfer *Protocol*), **SMTP** (Simple Mail Transfer *Protocol*), **IP** (*Internet Protocol*). In each case, "protocol" describes the standardized rules, while the preceding words describe what flows through them. ANIP is no different — it's the protocol for agent-native interfaces.

## The Shift

Every major interface paradigm emerged when the dominant consumer changed:

| Interface | Consumer | Era |
|-----------|----------|-----|
| CLI | Humans at terminals | 1970s–80s |
| GUI | Humans with screens and mice | 1980s–2000s |
| API | Programs written by humans | 2000s–2020s |
| **ANIP** | **AI agents** | **Now** |

Each shift wasn't a new format — it was a new set of assumptions about who is on the other end. That shift is happening again. The primary consumer of digital services is becoming an AI agent.

## The Problem

Today's interfaces were designed for humans. When agents interact with them, they do it in one of two ways — both wrong:

**Computer-use agents** (OpenClaw, Anthropic Computer Use, Operator) teach AI to operate a mouse and keyboard against GUIs built for human eyes. Brilliant engineering. Fundamentally a workaround.

**REST APIs** assume a human developer reads docs, writes deterministic code, and ships a program. When an agent uses an API directly, it discovers auth requirements by getting a 401, learns permissions by getting a 403, finds out costs after being charged, and can't undo what it doesn't know is irreversible.

**MCP** (Model Context Protocol) adds a discovery layer but is still REST with a wrapper. The agent still guesses, still fails forward, still treats errors as learning opportunities rather than having the information upfront.

## What It Looks Like

**Without ANIP — what agents deal with today:**

```
Agent wants to book a flight
→ Reads OpenAPI spec (designed for human developers)
→ Guesses that POST /bookings is the right endpoint
→ Discovers auth requirements by getting a 401
→ Discovers insufficient permissions by getting a 403
→ Books the flight
→ Discovers the charge was $800 not $420 (undeclared currency conversion)
→ Cannot undo (no rollback information was available)
→ Audit log exists but agent didn't know to check it
```

**With ANIP:**

```
Agent queries manifest → profile handshake
→ Sees book_flight: irreversible, financial, cost: ~$420±10%
→ Checks delegation chain has travel.book scope + $500 budget authority
→ Confirms rollback_window: none (knows upfront it's permanent)
→ Confirms observability: logged, 90-day retention
→ Decides to proceed, executes with full context
```

Every assumption that was implicit becomes explicit, typed, and queryable.

**Five things an agent doesn't know with REST but does with ANIP:**

1. **This action is irreversible** — `side_effect: irreversible`, `rollback_window: none`
2. **This costs $280–500** — `cost.financial: { range_min: 280, range_max: 500 }`
3. **Search before booking** — `requires: [{ capability: "search_flights" }]`
4. **Budget will be enforced** — `scope: ["travel.book:max_$500"]` in the delegation chain
5. **Who can fix a permission problem** — `resolution: { grantable_by: "human:samir@anip.dev" }`

That last one is the killer feature. When a budget-exceeded failure comes back, it doesn't just say "denied" — it tells the agent exactly who can increase the budget. The agent can autonomously escalate to the right person. That's a capability that doesn't exist in REST, MCP, or OpenAPI.

## When to Use ANIP

ANIP is the right interface when the consumer is an AI agent. The distinction isn't complexity — it's consumer.

- **Consumer is a human developer** writing deterministic code → REST/API is correct
- **Consumer is an AI agent** reasoning and acting autonomously → ANIP is correct

A simple read-only `get_weather` capability still benefits from ANIP when an agent consumes it: the agent knows it's safe to call repeatedly (`side_effect: read`), can discover it without reading docs, can verify its delegation scope before calling, and gets structured failures instead of HTTP codes.

ANIP scales down gracefully. A read-only service with no auth needs only the 5 core primitives and the ceremony is minimal. The value is in the consistency: agents that speak ANIP can interact with any ANIP service without reading documentation, regardless of complexity.

HTTP isn't overkill for serving a single static HTML file. The protocol is the same — GET, 200, content. The simplicity of the content doesn't make the protocol unnecessary. What makes HTTP unnecessary is when you're not on the web at all. Same with ANIP — what makes it unnecessary is when there's no agent in the picture.

## Core Principles

ANIP defines 9 primitives in two tiers:

**Core (ANIP-compliant) — every implementation MUST support:**

1. **Capability Declaration** — intent-based ("I can book flights"), not endpoint-based (`POST /bookings`)
2. **Side-effect Typing** — read, write, irreversible, transactional — with rollback windows
3. **Delegation Chain** — structured identity as a DAG: who's asking, on whose behalf, with what scoped authority
4. **Permission Discovery** — query what you're allowed to do *before* attempting it
5. **Failure Semantics** — errors that reference the delegation chain, budget, and scope — not HTTP status codes

**Contextual (ANIP-complete) — standardized shape, SHOULD support:**

6. **Cost & Resource Signaling** — bidirectional: service declares cost, agent declares budget, service offers alternatives
7. **Capability Graph** — capabilities know their prerequisites and what they compose with, so agents can navigate without reading docs
8. **State & Session Semantics** — stateless vs. continuation vs. multi-step workflow, explicitly declared
9. **Observability Contract** — what's logged, how long it's retained, who can audit it

## Status

ANIP is early-stage. The spec is a v0.1 draft. The core ideas have been validated through independent design review but the hard problems — trust verification, capability declaration format, multi-agent coordination — are open.

This is a community effort. We'd rather define this standard thoughtfully and in the open than let it emerge ad-hoc.

**What exists today:**
- [Manifesto](MANIFESTO.md) — why this moment matters
- [Spec](SPEC.md) — the technical design (v0.1)
- [Guide](GUIDE.md) — walkthrough of the reference implementation with design rationale
- [Reference implementation — Python](examples/anip/) — FastAPI + SQLite, full demo with audit logging
- [Reference implementation — TypeScript](examples/anip-ts/) — Hono + Zod, same capabilities and endpoints
- [JSON Schema](schema/) — validate any ANIP implementation against the spec
- [MCP adapter — Python](adapters/mcp-py/) — use ANIP with your existing MCP tooling today
- [MCP adapter — TypeScript](adapters/mcp-ts/) — same adapter, TypeScript/Node implementation
- [REST/OpenAPI adapter — Python](adapters/rest-py/) — expose ANIP as REST with auto-generated OpenAPI spec
- [REST/OpenAPI adapter — TypeScript](adapters/rest-ts/) — same adapter, TypeScript/Hono implementation
- [GraphQL adapter — Python](adapters/graphql-py/) — expose ANIP as GraphQL with custom @anip* directives
- [GraphQL adapter — TypeScript](adapters/graphql-ts/) — same adapter, TypeScript/Hono implementation
- [Agent skills](skills/) — machine-optimized guides for consuming and building ANIP services
- [Open questions](SPEC.md#open-questions) — where we need input

**Agent skills** are themselves an example of ANIP's philosophy applied to documentation. Instead of prose docs written for humans that agents have to interpret, ANIP ships structured skill files that agents can consume directly. The protocol eats its own cooking. These skill files were generated by an agent working directly from the spec, demonstrating the principle that ANIP documentation should be agent-consumable from day one.

**What's next:**
- Capability declaration format design
- Delegation chain token format

If this resonates, star the repo, open an issue, or [contribute](CONTRIBUTING.md). If you think we're wrong, tell us why — that's equally valuable.

## How This Was Built

ANIP was designed through parallel sessions with Claude Opus and Claude Code as co-authors. The commit history reflects that — every commit is co-authored, and we kept it that way deliberately. A protocol for agent-native interfaces, co-created with agents.

## License

Specification documents (SPEC.md, MANIFESTO.md, GUIDE.md, skills/, docs/): [CC-BY 4.0](LICENSE-SPEC)
Reference implementations and tooling (examples/, adapters/, schema/): [Apache 2.0](LICENSE-CODE)

## Attribution

When implementing or referencing ANIP, please cite:
"Agent-Native Interface Protocol (ANIP) — [anip-protocol/anip](https://github.com/anip-protocol/anip)"
