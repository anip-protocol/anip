# ANIP Runtime Utils for Java

Small deterministic helpers for agent-consumption flows.

## AgentConsumption

`dev.anip.runtimeutils.AgentConsumption` provides static helper methods that use only declared capability metadata:

- `selectConsumableCapability(conversation, selectedCapability, metadata)` picks a stronger same-effect capability when the conversation better matches its declared metadata.
- `missingRequiredInputNames(conversation, metadata)` returns required inputs not grounded by allowed values or declared input meanings.
- `requestedUnsupportedEffects(conversation, metadata)` returns declared unsupported effects requested by the conversation.
- `detectUnsupportedEffects(conversation, metadata)` is an alias for unsupported-effect detection.
- `capabilityMatchScore(conversation, capabilityId, metadata)` exposes the deterministic match score used by selection.

The helpers do not call LLMs and do not use product-specific rules. They derive behavior from capability id, description/framing fields, `business_effects`, `input_specs`, `app_profile` boundaries, semantic types, and input descriptions.

## Test

From `packages/java`:

```bash
mvn -pl anip-runtime-utils test
```
