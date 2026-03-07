# Contributing to ANIP

ANIP is an early-stage protocol specification. We're looking for people who think deeply about interfaces, agent architectures, and protocol design.

## How to Contribute

**Discussion** — Open an issue to discuss ideas, challenge assumptions, or propose changes. The best contributions right now are ones that stress-test the spec.

**Spec changes** — Submit a PR against `SPEC.md`. Explain what you're changing and why. Changes to core primitives require more justification than changes to contextual primitives — that's by design.

**Examples** — The `examples/` directory contains reference implementations. We welcome implementations in any language that demonstrate ANIP concepts.

## Where to Start

The spec has [open questions](SPEC.md#11-open-questions) that need community input. These are genuine design decisions, not rhetorical questions:

1. Capability declaration format (JSON Schema baseline — what extensions does it need?)
2. Relationship to existing standards (OpenAPI, JSON-LD, AsyncAPI)
3. Registry model for ANIP services
4. Side-effect type completeness
5. Delegation chain auth format
6. Service advertisement mechanism

Pick one that interests you and open an issue.

## Guidelines

- Be constructive and specific. "This is wrong" is less useful than "this breaks when X happens."
- Show your reasoning. Protocol design is full of tradeoffs — help us see the ones we've missed.
- Small, focused PRs over large sweeping changes.

## Code of Conduct

Be respectful, be specific, be constructive. We're building something new and that means being wrong sometimes. That's fine — surface it, fix it, move on.
