# Studio Agent Consumption Simulator Plan

Date: 2026-04-28

## Purpose

Studio needs an early simulation loop for agent consumption. The goal is to catch likely package-consumption failures before Registry publication, code generation, deployment, and paid benchmark runs.

This is a simulation, not proof of runtime correctness. It predicts how an ANIP-aware agent is likely to consume a locked contract/package from metadata alone.

## Problem

The GTM benchmark showed a costly feedback loop:

1. Generate package.
2. Publish to Registry.
3. Generate code.
4. Deploy services.
5. Run agent tests.
6. Discover that the agent misunderstood intent, missing context, unsupported effects, or app glue.

Many of those failures are visible earlier from the Developer Definition, readiness findings, reviewed consumability metadata, and deterministic probes.

## Model Roles

Studio must separate model configuration by role.

- `Studio Assistant`: high-quality design-time drafting, explanation, and proposal generation. This can use advanced models and heavier reasoning.
- `Simulator Baseline`: the model expected to represent a realistic consuming agent. Default target is `gpt-5.4-mini` or compatible.
- `Simulator Adversarial` (later): stronger model used to generate paraphrases and edge cases. It is a test designer, not the baseline consuming agent.
- `Runtime Agent`: the deployed/demo agent model, expected to stay at the low-cost baseline when possible.

The simulator must not silently reuse assistant settings. It has separate provider/model/base URL/key/temperature/timeout configuration.

## Simulator Inputs

The simulator should consume:

- Developer Definition capability formalizations.
- Agent Consumption Readiness report.
- Reviewed `agent_consumability` metadata.
- Required app glue records.
- Deterministic simulator probes.
- Optional reviewed/adversarial paraphrase probes.

## Simulation Flow

1. Build an agent-consumption brief from the same metadata the generated kit will receive.
2. For each probe, ask the baseline simulator model to produce a single planning result:
   - selected capability
   - parameters
   - unsupported flag
   - expected user-facing outcome
   - rationale
3. Score the result deterministically against the expected probe outcome:
   - selected capability matches expected target when present
   - unsupported is set for unsupported-effect probes
   - missing context is omitted rather than guessed
   - undeclared parameters are not invented
   - approval/clarification expectations are respected
   - selected capability owns the declared business effect
4. Store a simulator report as a Studio artifact.
5. Surface failures in Developer Coverage before publication.

## Non-Goals

- Do not invoke generated services.
- Do not call Registry.
- Do not prove business implementation correctness.
- Do not let AI verdicts become authority without deterministic scoring.
- Do not create giant phrase alias lists.

## Phase 1

- Add separate simulator model settings.
- Expose simulator configuration in Studio Settings.
- Add backend persistence with environment overrides.
- Document model-role separation.

Status: implemented.

## Phase 2

- Add a simulator runner API for deterministic readiness probes.
- Store simulator reports as artifacts.
- Show pass/fail results in Developer Coverage.

Status: initial implementation complete. The backend exposes `POST /api/agent-consumption-simulator/run`; Developer Coverage can run the configured baseline simulator and scores the returned plan deterministically. The report is saved as an `agent_consumption_simulation_report` artifact and is also included in the readiness handoff artifact.

Assistant feedback loop: implemented. Studio Assistant exposes `analyze_agent_consumption_simulation`, reads the latest saved simulator report as evidence, and proposes reviewable fixes. Developer Coverage also has an “Ask Assistant for Fix Plan” action. This does not couple assistant and simulator runtime configs; it only shares persisted artifacts.

## Phase 3

- Add optional adversarial paraphrase generation.
- Require PM/dev review before probes become publication gates.
- Export simulator reports with packages.

## Gate Rule

The simulator can be AI-powered, but the gate must be deterministic. The simulator model proposes a plan; Studio scores that plan against reviewed expected outcomes.

Current scoring compares expected outcome and, for successful probes, expected capability. Stronger deterministic checks should be added next for undeclared parameters, business-effect ownership, approval posture, and required-context handling.
