# @anip-dev/runtime-utils

Small TypeScript helpers for deterministic agent-consumption decisions from ANIP capability metadata.

The package does not call an LLM and does not encode app-specific phrases. Helpers use contract-derived fields such as capability identifiers, descriptions, framing, effects, input specs, app boundaries, semantic types, and input descriptions.

These helpers assist consuming agents with routing, compact prompt construction, and contract-derived preflight checks. They are not the trust boundary. The authoritative policy decision remains the ANIP service invocation result.

## API

- `selectConsumableCapability(conversation, selectedCapability, metadata)` chooses the strongest same-effect capability from available metadata.
- `missingRequiredInputNames(conversation, capabilityMetadata)` returns required inputs that are not grounded in the conversation.
- `requestedUnsupportedEffects(conversation, capabilityMetadata)` returns unsupported effects requested by the conversation.
- `validateInvocationPlanForFallback(plan, conversation, metadata, options)` returns deterministic reasons a primary planner result should escalate to a fallback model.

`detectUnsupportedEffects` is exported as an alias for `requestedUnsupportedEffects`.

Fallback validation is intended for mixed-model agent runtimes, for example
trying a small routing model first and escalating only when the planner result
is structurally unsafe or inconsistent with the contract. It does not replace
service-side ANIP enforcement.
