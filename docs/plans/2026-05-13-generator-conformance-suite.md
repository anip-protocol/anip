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
- Generated policy fails closed, the same way in every target:
  1. A matching `deny` binding refuses (`denied`), whatever the capability posture. A binding whose decision the host does not recognise refuses too.
  2. When a capability has bindings and none matches the actor, the request is refused (`denied`). A principal without actor claims matches none.
  3. A capability without bindings is allowed. Bindings stay sparse overrides at the capability level: once a capability has any, they are its allowlist.
  4. An approval-gated capability (`side_effect_level` or `execution_posture` `approval_required`, `execution_posture` or `operation_type` `approval_gated`) stops before the backend adapter runs, unless the runtime validated an approval grant for this invocation.
- Among matching bindings, `deny` wins over `approval_required`, which wins over `clarify`, which wins over `allow` and `allow_with_limits`, for every capability.
- An `approval_required` stop is an ANIP failure that carries an approval request; its preview is the governed request (semantic input and backend input contract), not backend output. A validated grant for the same capability, parameters and principal lets the continuation reach the adapter.
- A composed capability is executed by the runtime, not by generated code, so generated policy never evaluates the parent. Each child step goes through the full invoke pipeline with a token delegated from the caller's, carrying the same root principal and only its mapped inputs, so every child applies these rules itself. A composition cannot reach anything its caller could not reach by invoking the children directly.
- Because the parent is never evaluated, definition validation refuses a runtime policy binding or permission intent that names a composed capability (a permission intent targeting a whole service is accepted), and generation refuses such a definition. The rule belongs on the child capabilities; the executable suite checks that a child's deny applies when the child runs as a composition step.
- A policy refusal carries the same failure type, detail and resolution on HTTP and on stdio.
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

