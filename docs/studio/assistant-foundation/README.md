# Studio Assistant Foundation

Date: 2026-04-19

## Purpose

This folder defines the next implementation slice for AI-assisted Studio authoring.

The target is:

- `Studio` remains fully usable without AI
- the core product flow remains deterministic
- one shared optional assistant helps on both PM and Developer surfaces
- the generator still consumes the same canonical JSON model regardless of whether the user worked manually or with assistance

This folder is intentionally narrower than the older broad assistant notes. It is meant to drive implementation decisions.

## Documents

1. [Architecture](./2026-04-19-studio-assistant-architecture.md)
   - product boundary
   - deterministic core ownership
   - assistant boundary
   - why there should be one shared assistant system with PM and Dev modes

2. [Capability Surface And Proposal Contract](./2026-04-19-studio-assistant-capability-surface.md)
   - bounded ANIP capabilities
   - request and response shape
   - proposal/patch model
   - explicit rules for what the assistant may and may not do

3. [Implementation Plan](./2026-04-19-studio-assistant-implementation-plan.md)
   - staged rollout
   - how to use the current Studio assistant capability path as the starting point
   - where backend, schema, and UI changes should land first

4. [User Flow](./2026-04-20-studio-assistant-user-flow.md)
   - dedicated project assistant page
   - PM and Developer lane flows
   - clarification answer and section regeneration loop
   - read-only mode behavior

## Core Rule

AI helps users operate Studio.

AI does not become the Studio engine.

That means:

- the assistant may interpret, draft, explain, and ask for clarification
- the deterministic backend remains responsible for:
  - state transitions
  - schema validation
  - locking
  - revision integrity
  - canonical artifact persistence
  - generation and verification orchestration

## Success Condition

This work is successful when:

1. a PM can upload or paste business specs and get a high-quality first draft without hand-authoring every field
2. a developer can refine the same project with contract-grade assistance instead of filling every field from scratch
3. Studio still works end to end without the assistant
4. the final saved artifacts are the same deterministic contract types already used by generation and verification
