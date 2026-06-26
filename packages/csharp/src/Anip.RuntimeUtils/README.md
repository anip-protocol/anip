# ANIP Runtime Utils for C#

Small deterministic helpers for consuming agents that need to route requests and run contract-derived preflight checks before invoking an ANIP service.

These helpers assist consuming agents with routing, compact prompt construction, and contract-derived preflight checks. They are not the trust boundary. The authoritative policy decision remains the ANIP service invocation result.

## Agent Consumption Helpers

- `AgentConsumption.SelectConsumableCapability(conversation, selectedCapability, metadata)` chooses the strongest same-effect capability from available metadata.
- `AgentConsumption.MissingRequiredInputNames(conversation, capabilityMetadata)` returns required inputs that are not grounded in the conversation.
- `AgentConsumption.RequestedUnsupportedEffects(conversation, capabilityMetadata)` returns unsupported effects requested by the conversation.
- `AgentConsumption.DetectUnsupportedEffects(conversation, capabilityMetadata)` is an alias for unsupported-effect detection.
- `AgentConsumption.CapabilityMatchScore(conversation, capabilityId, capabilityMetadata)` scores a capability against the conversation using declared metadata.

The helpers use only contract metadata such as capability descriptions, business effects, input specs, app profile framing, app boundaries, semantic types, and input descriptions. They do not perform model calls.
