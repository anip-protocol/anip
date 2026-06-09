# Agent Consumption Readiness And Simulator Plan

Date: 2026-04-28

Status: Active implementation plan

## Problem

The GTM benchmark proved that "ANIP can support this" is not enough for adoption. A project can have valid ANIP contracts and still be hard for an agent app to consume reliably if semantic gaps are only discovered after code generation and benchmark runs.

Studio must make the path usable:

- Identify which behavior is natively contract-backed.
- Identify which behavior needs custom service logic.
- Identify which behavior needs agent-app glue.
- Identify unsupported effects before publication.
- Generate deterministic simulator probes that expose missing clarification, defaults, effects, approval, and composition behavior early.

This is not a claim that ANIP eliminates all glue. The goal is to make required glue explicit, bounded, and inspectable before implementation.

## Decision

Add an Agent Consumption Readiness check to Studio Developer Coverage.

The check is deterministic. It does not call an LLM and does not try to prove arbitrary natural-language understanding. It reads the locked Developer Definition and produces:

- A readiness status and score.
- Contract/service/app-glue findings with severity and owner.
- A required app-glue list.
- A small simulator probe set with expected outcomes.

The first version is intentionally practical rather than exhaustive. It focuses on the gaps that made the generated GTM stack hard to reach 350/350:

- Vague business references accepted as literal entity names.
- Required defaults not declared or not enforced.
- Derived-target requests that require composition or app glue.
- Unsupported effects such as send/export/mutate.
- Approval-gated behavior without explicit grant policy.
- Missing output semantics for useful rendering.

## Ownership Model

Every readiness finding must name an owner:

- `product_contract`: the PM-facing product behavior needs to be clarified.
- `developer_contract`: the Developer Definition is missing required machine-readable behavior.
- `custom_service_logic`: the service implementation must own authoritative domain behavior.
- `agent_app_glue`: the app needs product framing, presentation, routing preference, or UX guidance.
- `generator_runtime`: the generator/runtime should mechanically enforce declared behavior.
- `unsupported`: the behavior should not be exposed by this package.

This prevents Studio from hiding ambiguity behind a vague "needs work" status.

## Readiness Status

Studio computes a score from findings:

- `ready`: no blockers and score at least 85.
- `needs_review`: no blockers but score below 85, or warnings are present.
- `blocked`: at least one blocker exists.

The score is advisory. Locking/publishing policy can later decide which thresholds are mandatory.

## Simulator MVP

The simulator is not an LLM benchmark. It is a deterministic probe generator.

For each relevant capability or scenario, Studio emits prompts such as:

- Missing required context: "Run `<capability>` without `<input>`."
- Vague entity scope: "Summarize results for a vague target such as top accounts."
- Unsupported effect: "Ask the package to send/export/mutate when only draft/summary/preview effects are declared."
- Approval boundary: "Invoke approval-gated behavior without a grant."
- Composition candidate: "Ask for a derived target that requires one capability to feed another."

Each probe has an expected ANIP-level outcome:

- `success`
- `clarification_required`
- `denied`
- `approval_required`
- `unsupported`

This catches steep/bumpy adoption issues before service implementation, generator work, registry publication, or paid LLM benchmark runs.

## What This Does Not Do

Do not implement the full eight-point metadata proposal as protocol surface now.

Do not try to make every ANIP package consumable by every possible agent with zero app glue.

Do not add endless phrase aliases to contracts. Prefer controlled effects, declared defaults, input formats, clarification hints, composition, and explicit app-glue recommendations.

## Implementation Scope

Initial implementation:

- Add a reusable `analyzeAgentConsumptionReadiness` module in Studio.
- Wire the report into Developer Coverage.
- Surface findings, required app glue, and simulator probes.
- Add unit tests for the deterministic rules.

Future work:

- Persist the readiness report as a project artifact.
- Add lock/publish gates for blockers.
- Export simulator probes into registry packages.
- Let optional AI assistants suggest fixes, while keeping the locked report deterministic.
- Add generator/verifier conformance tests from the probes.

