# Contributing to ANIP

ANIP is an early-stage protocol specification. We're looking for people who think deeply about interfaces, agent architectures, and protocol design.

## How to Contribute

**Discussion** — Open an issue to discuss ideas, challenge assumptions, or propose changes. The best contributions right now are ones that stress-test the spec.

**Spec changes** — Submit a PR against `SPEC.md`. Explain what you're changing and why. Changes to core primitives require more justification than changes to contextual primitives — that's by design.

**Examples** — The `examples/` directory contains reference implementations (Python and TypeScript), and `packages/go/examples/` contains the Go reference implementation. We welcome implementations in any language that demonstrate ANIP concepts.

## Where to Start

The spec has [open questions](SPEC.md#14-open-questions) that need community input. These are genuine design decisions, not rhetorical questions:

1. Relationship to existing standards (OpenAPI, JSON-LD, AsyncAPI)
2. Registry model for ANIP services
3. Side-effect type completeness
4. Global service registry
5. Wildcard scope matching

Some earlier open questions have been resolved: capability declaration format (JSON Schema, resolved in v0.1), delegation chain auth format (JWT/ES256, resolved in v0.2), audit log verifiability (Merkle checkpoints, resolved in v0.3), discovery governance visibility (posture declaration, resolved in v0.7), security hardening with event classification and retention policies (resolved in v0.8).

Pick one that interests you and open an issue.

## Guidelines

- Be constructive and specific. "This is wrong" is less useful than "this breaks when X happens."
- Show your reasoning. Protocol design is full of tradeoffs — help us see the ones we've missed.
- Small, focused PRs over large sweeping changes.

## Code of Conduct

Be respectful, be specific, be constructive. We're building something new and that means being wrong sometimes. That's fine — surface it, fix it, move on.
