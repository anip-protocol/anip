# anip-runtime-utils

Small shared runtime helpers for agent-side deterministic normalization and
preflight handling.

These helpers assist consuming agents with routing, compact prompt construction,
and contract-derived preflight checks. They are not the trust boundary. The
authoritative policy decision remains the ANIP service invocation result.

Current scope:

- metadata-driven enum/default normalization
- compact agent capability catalog construction from discovery + manifest payloads
- generic phrase matching
- generic denied-preflight payload construction
- planner fallback validation for mixed-model agent runtimes

Non-goals:

- domain vocabulary parsing
- service-local aliases
- business-policy decisions that belong in ANIP services

This package is intentionally small. It exists to promote clearly reusable
runtime patterns without pulling GTM-specific logic into a shared layer.

`build_agent_capability_catalog(...)` keeps rich ANIP manifests available to the
runtime while producing a compact routing brief for model prompts. Agent
runtimes should not blindly send full manifests or package metadata to the LLM
on every turn; they should send a purpose-built brief and keep the full metadata
for deterministic normalization, token issuance, invocation, and audit.

`validate_invocation_plan_for_fallback(...)` lets an agent runtime decide
whether a primary model result should escalate to a stronger model before
invocation. It only uses contract-derived metadata and checks planner shape,
capability discovery, compact-candidate membership, concrete-but-unbound inputs,
requested unsupported effects, and requested content-effect mismatches. Declared
unsupported-effect requests are valid governed denials, not fallback triggers.
