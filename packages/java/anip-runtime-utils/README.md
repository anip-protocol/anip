# ANIP Runtime Utils for Java

Small deterministic helpers for agent-consumption flows.

These helpers assist consuming agents with routing, compact prompt construction, and contract-derived preflight checks. They are not the trust boundary. The authoritative policy decision remains the ANIP service invocation result.

## AgentConsumption

`dev.anip.runtimeutils.AgentConsumption` provides static helper methods that use only declared capability metadata:

- `selectConsumableCapability(conversation, selectedCapability, metadata)` picks a stronger same-effect capability when the conversation better matches its declared metadata.
- `missingRequiredInputNames(conversation, metadata)` returns required inputs not grounded by allowed values or declared input meanings.
- `requestedUnsupportedEffects(conversation, metadata)` returns declared unsupported effects requested by the conversation.
- `detectUnsupportedEffects(conversation, metadata)` is an alias for unsupported-effect detection.
- `capabilityMatchScore(conversation, capabilityId, metadata)` exposes the deterministic match score used by selection.
- `validateInvocationPlanForFallback(plan, conversation, metadata, options)` returns deterministic reasons a primary planner result should escalate to a fallback model.

The helpers do not call LLMs and do not use product-specific rules. They derive behavior from capability id, description/framing fields, `business_effects`, `input_specs`, `app_profile` boundaries, semantic types, and input descriptions.

Fallback validation is intended for mixed-model agent runtimes, for example
trying a small routing model first and escalating only when the planner result
is structurally unsafe or inconsistent with the contract. It does not replace
service-side ANIP enforcement.

## Test

From `packages/java`:

```bash
mvn -pl anip-runtime-utils test
```
