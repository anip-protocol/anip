# GTM Showcase

This folder is the canonical documentation root for the GTM ANIP showcase.

It is intentionally separate from earlier demo/example material.

This showcase is being treated as:

- a new flagship implementation
- a real multi-service system
- a proof of the full ANIP lifecycle:
  - design
  - implement
  - validate
  - execute

This is not a repackaged toy example.

## Showcase Objectives

This showcase has to prove the full ANIP lifecycle in a way that a serious GTM
team can inspect and trust.

The required proof chain is:

1. a clear PM-readable business spec that states what the agent should be able
   to do
2. a translated behavior specification in Studio design
3. a completed developer design in Studio
4. generated code that is actually used for the running showcase services
5. Studio validation that checks the running services against the intended
   specification and observed ANIP metadata
6. execution through real agent runtimes and a simple user-facing UI

If the showcase does not prove that chain, it is not strong enough.

It is intended to show that GTM agents can be built:

- safer
- more governably
- more easily validated
- reproducibly locally

than the default `agent + prompts + raw tool access` pattern.

Claims about being faster or cheaper should be demonstrated by the running
stack, not assumed up front.

## Documents

- [gtm-revenue-operations-business-spec.md](./gtm-revenue-operations-business-spec.md)
- [business-spec.md](./business-spec.md)
- [enrichment-business-spec.md](./enrichment-business-spec.md)
- [prioritization-business-spec.md](./prioritization-business-spec.md)
- [outreach-business-spec.md](./outreach-business-spec.md)
- [pipeline-forecast-business-spec.md](./pipeline-forecast-business-spec.md)
- [stage-bottleneck-business-spec.md](./stage-bottleneck-business-spec.md)
- [sales-team-performance-business-spec.md](./sales-team-performance-business-spec.md)
- [product-pipeline-business-spec.md](./product-pipeline-business-spec.md)
- [prepare-reassignment-business-spec.md](./prepare-reassignment-business-spec.md)
- [anip-capability-runtime-governance.csv](./anip-capability-runtime-governance.csv)
- [anip-capability-input-contracts.csv](./anip-capability-input-contracts.csv)
- [story.md](./story.md)
- [architecture.md](./architecture.md)
- [implementation-plan.md](./implementation-plan.md)
- [phase3-live-proof.md](./phase3-live-proof.md)
- [phase4-live-proof.md](./phase4-live-proof.md)
- [phase5-live-proof.md](./phase5-live-proof.md)
- [phase6-live-proof.md](./phase6-live-proof.md)
- [phase7-live-proof.md](./phase7-live-proof.md)
- [phase8-scale-and-packaging-plan.md](./phase8-scale-and-packaging-plan.md)
- [phase8-bi-verification.md](./phase8-bi-verification.md)
- [question-banks/README.md](./question-banks/README.md)
- [question-bank-runs/README.md](./question-bank-runs/README.md)
- [model-tier-comparison.md](./model-tier-comparison.md)

## Developer Runtime Evidence

Studio Autopilot should use the two strict CSV files as developer-owned runtime
evidence. The Markdown documents explain intent; the CSV files provide the
parseable contract facts that must not be inferred from prose.

- `anip-capability-runtime-governance.csv` defines service ownership,
  operation type, side-effect level, grant policy, canonical business effects,
  minimum scope, backend operation, and output shape for each capability.
- `anip-capability-input-contracts.csv` defines every runtime input: name, type,
  required flag, semantic type, entity-reference posture, resolution behavior,
  defaults, allowed values, catalog/resolver refs, and clarification hints.

Business effects must use the canonical ANIP effect IDs only. Values such as
`content.rationale`, `external_send`, or `raw_conversation_export` are invalid;
use `content.recommendation`, `external_dispatch`, and `raw_data_export`
respectively.

## Current Proof State

The showcase currently has live proof for:

- Phase 1 bounded GTM pipeline behavior
- Phase 2 multi-service `pipeline -> enrichment` behavior
- Phase 3 actor-aware visibility, approval posture, and auditability
- Phase 4 REST-backed prioritization through ANIP
- Phase 5 MCP-backed outreach through ANIP
- Phase 6 bounded forecast, bottleneck, team-performance, and product-pipeline
  reads over the Maven CRM layer
  plus one approval-gated reassignment preview
- Phase 7 governed scenario composition across multiple services from one
  compound user question
- broad question-bank execution across Phases 1 through 7
  - `350 / 350` passed

## Next Expansion

The next planned work is split cleanly:

- Phase 6: deepen the Maven CRM state layer with bounded forecast, bottleneck,
  team-performance, product-pipeline, and reassignment-preview capabilities
- Phase 7: prove governed scenario composition across services
- Phase 8: package the showcase as a clean shareable flagship stack

That sequencing is intentional:

- complete the four-service architecture first
- then deepen the CRM-state layer with additional bounded capabilities
- keep Phase 6 focused on bounded semantic CRM reads and preview-safe
  operational work
- prove compound governed execution before packaging
- package only after the proof surface is complete
