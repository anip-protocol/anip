# runtimeutils

Small Go helpers for deterministic agent-consumption decisions from ANIP capability metadata.

The package does not call an LLM and does not encode app-specific phrases. Helpers use contract-derived fields such as capability identifiers, descriptions, framing, effects, input specs, app boundaries, semantic types, and input descriptions.

These helpers assist consuming agents with routing, compact prompt construction, and contract-derived preflight checks. They are not the trust boundary. The authoritative policy decision remains the ANIP service invocation result.

## API

- `SelectConsumableCapability(conversation, selectedCapability, metadata)` chooses the strongest same-effect capability from available metadata.
- `MissingRequiredInputNames(conversation, capabilityMetadata)` returns required inputs that are not grounded in the conversation.
- `RequestedUnsupportedEffects(conversation, capabilityMetadata)` returns unsupported effects requested by the conversation.
- `DetectUnsupportedEffects(conversation, capabilityMetadata)` is an alias for `RequestedUnsupportedEffects`.
