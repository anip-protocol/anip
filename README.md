# ANIP — Agent-Native Interface Protocol

> A protocol for software interfaces designed from the ground up for AI agents, not humans.

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
- [MCP bridge — Python](bridges/mcp/) — use ANIP with your existing MCP tooling today
- [MCP bridge — TypeScript](bridges/mcp-ts/) — same bridge, TypeScript/Node implementation
- [Agent skills](skills/) — machine-optimized guides for consuming and building ANIP services
- [Open questions](SPEC.md#open-questions) — where we need input

**Agent skills** are themselves an example of ANIP's philosophy applied to documentation. Instead of prose docs written for humans that agents have to interpret, ANIP ships structured skill files that agents can consume directly. The protocol eats its own cooking. These skill files were generated by an agent working directly from the spec, demonstrating the principle that ANIP documentation should be agent-consumable from day one.

**What's next:**
- Capability declaration format design
- Delegation chain token format

If this resonates, star the repo, open an issue, or [contribute](CONTRIBUTING.md). If you think we're wrong, tell us why — that's equally valuable.

## How This Was Built

ANIP was designed through parallel sessions with Claude Sonnet and Claude Code as co-authors. The commit history reflects that — every commit is co-authored, and we kept it that way deliberately. A protocol for agent-native interfaces, co-created with agents.

## License

Specification documents (SPEC.md, MANIFESTO.md, GUIDE.md, skills/, docs/): [CC-BY 4.0](LICENSE-SPEC)
Reference implementations and tooling (examples/, bridges/, schema/): [Apache 2.0](LICENSE-CODE)

## Attribution

When implementing or referencing ANIP, please cite:
"Agent-Native Interface Protocol (ANIP) — [anip-protocol/anip](https://github.com/anip-protocol/anip)"
