# @anip-dev/runtime-utils

Small TypeScript helpers for deterministic agent-consumption decisions from ANIP capability metadata.

The package does not call an LLM and does not encode app-specific phrases. Helpers use contract-derived fields such as capability identifiers, descriptions, framing, effects, input specs, app boundaries, semantic types, and input descriptions.

## API

- `selectConsumableCapability(conversation, selectedCapability, metadata)` chooses the strongest same-effect capability from available metadata.
- `missingRequiredInputNames(conversation, capabilityMetadata)` returns required inputs that are not grounded in the conversation.
- `requestedUnsupportedEffects(conversation, capabilityMetadata)` returns unsupported effects requested by the conversation.

`detectUnsupportedEffects` is exported as an alias for `requestedUnsupportedEffects`.
