# Generator Conformance Suite

## Problem

GTM question-bank runs are useful end-to-end tests, but they are the wrong first gate for language parity. They mix:

- ANIP generator behavior
- target runtime library behavior
- GTM custom bundle behavior
- GTM app glue
- LLM planning behavior
- downstream service behavior

That makes failures expensive to diagnose and lets untested ANIP contract surfaces slip through if GTM does not exercise them.

## Decision

Add an ANIP generator conformance suite that runs before app-specific banks.

The generator suite must verify that the same service definition produces equivalent generated behavior across all supported targets:

- Python
- TypeScript
- Go
- Java
- C#

This suite is deterministic and does not call an LLM.

## Scope

The first suite checks generated artifact semantics, not full live service execution. It covers the surfaces that recently caused parity drift:

- v0.24 input-resolution metadata is preserved into runtime target metadata and generated capability declarations.
- Sparse runtime policy bindings are treated as overrides, not an exhaustive allowlist.
- Read-like capabilities prefer allow/allow-with-limits over unrelated deny bindings.
- Governed-stop capabilities prefer deny, approval, then clarification before allow.
- Approval-required generated hosts produce a preview path before stopping.
- Backend adapter input is filtered through the declared backend input contract.
- Composed capabilities preserve child approval/denial/clarification propagation metadata.
- Integration-fronting bindings and backend template material are emitted for every target.

## Non-Goals

- Do not encode GTM business language into generator conformance.
- Do not use the GTM 350/490 question banks as generator parity proof.
- Do not call model providers.
- Do not require all target toolchains to run in the first static artifact gate.

## Follow-Up

After this static gate is stable, add an executable generated-service conformance runner:

1. Generate the same fixture for each target into a temp directory.
2. Compile/start each generated service with default backend adapters.
3. Invoke the same request matrix against each target.
4. Compare normalized ANIP outcomes and audit/approval shapes.
5. Only then run GTM app-level question banks.

