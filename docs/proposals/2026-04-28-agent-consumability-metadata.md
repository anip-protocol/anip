# ANIP Agent Consumability Metadata

Date: 2026-04-28

Status: Proposal

## Problem

ANIP already gives agents a strong contract surface: discoverable capabilities, declared inputs and outputs, scopes, delegation, approval grants, descriptive failures, package lineage, and registry-backed verification.

The remaining gap is narrower than "agent prompts" or "workflow design":

> How can an ANIP-aware agent safely choose and invoke a capability from natural user language without embedding domain-specific glue in the agent runtime?

The answer should not be giant prompt files, benchmark-specific phrase lists, or service-specific routing code in a generic agent. Contract metadata should describe durable service semantics, not every possible way a user might phrase a request.

## Design Principle

ANIP metadata should stay structured, controlled, and service-owned.

Allowed:

- Metadata that helps an agent safely select, authorize, invoke, clarify, deny, approve, or render a capability.
- Controlled taxonomies for effects and intent categories.
- Short semantic descriptions for enum values and references.
- A small number of canonical examples.

Not allowed:

- Generic runtimes containing domain-specific logic such as `if "competitor objection" then ...`.
- Open-ended phrase lists attempting to enumerate every user wording.
- Generator, verifier, or registry code containing GTM-specific behavior.
- Contract metadata turning into a replacement skill file or workflow prompt.

## 1. Capability Intent

Each capability should expose a compact intent block that explains the business purpose in a stable way.

Example:

```json
{
  "intent": {
    "category": "outreach.draft",
    "summary": "Draft bounded outreach content for a selected target."
  }
}
```

Purpose:

- Helps agents choose between similar capabilities.
- Reduces over-reliance on capability names.
- Keeps intent separate from long natural-language descriptions.

Open question:

- Whether `category` should be fully controlled by ANIP, package-local, or hybrid.

## 2. Business Effects

Capabilities should expose what they produce or affect using a small controlled taxonomy, not arbitrary strings or phrase aliases.

Example:

```json
{
  "business_effects": {
    "produces": ["content.draft"],
    "does_not_produce": ["external_dispatch", "system.mutation", "raw_data_export"]
  }
}
```

Possible initial taxonomy:

- `content.draft`
- `content.summary`
- `content.recommendation`
- `data.read`
- `data.aggregate`
- `data.export`
- `raw_data_export`
- `system.preview_mutation`
- `system.mutation`
- `external_dispatch`
- `approval.request`
- `approval.execute`

Purpose:

- Handles distinctions like draft vs send, summary vs raw export, preview vs mutation.
- Lets a generic ANIP-aware agent classify the requested effect against capability boundaries.
- Avoids brittle phrase lists like "send it now", "ship it", "fire it off".

## 3. Input Semantics

Inputs should expose semantic meaning, especially for enum values and entity references.

Example:

```json
{
  "input_name": "objection_theme",
  "semantic_type": "business_category",
  "allowed_values": [
    {
      "value": "competitor",
      "meaning": "Competitive vendor, alternative solution, or incumbent displacement concern."
    },
    {
      "value": "pricing",
      "meaning": "Price, budget, affordability, or cost concern."
    }
  ]
}
```

Entity reference example:

```json
{
  "input_name": "target_ref",
  "semantic_type": "account_or_lead_reference",
  "required": true
}
```

Purpose:

- Lets an agent map natural language to declared values by meaning.
- Keeps domain knowledge in the contract instead of the runtime.
- Avoids enumerating every possible alias.

## 4. Required Context

Capabilities should expose which inputs are materially required for safe invocation and what should happen when they are missing.

Example:

```json
{
  "required_context": [
    {
      "input": "quarter",
      "missing_behavior": "clarify"
    },
    {
      "input": "target_ref",
      "missing_behavior": "clarify"
    }
  ]
}
```

Purpose:

- Prevents agents from guessing business-critical scope.
- Makes clarification behavior discoverable.
- Lets services remain authoritative if the agent still invokes with missing context.

## 5. Invocation Examples

Capabilities may include a small number of canonical invocation examples.

Example:

```json
{
  "examples": [
    {
      "user_request": "Draft a first-touch message for Acme.",
      "capability": "gtm.draft_outreach_message",
      "parameters": {
        "target_ref": "Acme",
        "objective": "first_touch"
      }
    }
  ]
}
```

Purpose:

- Helps agents understand shape and parameter binding.
- Improves reliability without building workflow-specific prompts.

Constraint:

- Examples should be sparse. A good default is 0-3 examples per capability.
- Examples should not become the primary way to define semantics.

## 6. Result Semantics

Capabilities should expose enough output semantics for generic rendering.

Example:

```json
{
  "output_semantics": {
    "primary_field": "result",
    "result_type": "draft_content",
    "display_fields": ["subject", "body", "rationale"]
  }
}
```

Purpose:

- Lets a generic agent present useful responses without service-specific renderers.
- Makes important result fields discoverable.
- Reduces custom UI/runtime formatting logic.

## 7. Approval And Grant Semantics

ANIP v0.23 already defines approval grants. Discovery should expose the practical semantics clearly enough for agents.

Example:

```json
{
  "approval": {
    "required": true,
    "grant_types": ["one_time", "session_bound"],
    "approval_effect": "system.mutation"
  }
}
```

Purpose:

- Lets agents explain approval requirements before or after invocation.
- Makes one-time vs session-bound grants discoverable.
- Connects approvals to business effects.

## 8. Composition Semantics

Contract-level composition should be exposed as business capability metadata, not as workflow instructions for the agent to execute.

Example:

```json
{
  "composition": {
    "kind": "same_service",
    "business_capability": true,
    "steps_visible_to_agent": false
  }
}
```

Purpose:

- Tells the agent that one declared capability represents a composed business operation.
- Prevents agents from rebuilding service workflows client-side.
- Keeps orchestration inside the service contract and implementation.

## Studio Responsibilities

Studio should not ask PMs or developers to manually author a large semantic metadata file.

Studio should:

- Infer initial metadata from product docs, developer design, capability descriptions, side effects, inputs, outputs, and approval rules.
- Present controlled choices where possible, especially for business effects.
- Let PM/dev reviewers correct or approve metadata before publication.
- Version metadata with the contract.
- Publish metadata into the signed package and registry record.

## Generic Agent Responsibilities

A generic ANIP-aware agent should:

- Discover services and capabilities.
- Read intent, effects, input semantics, required context, approval, composition, and output semantics.
- Select one declared capability.
- Bind only declared inputs.
- Request tokens using declared scopes.
- Invoke the capability.
- Handle standard ANIP outcomes.
- Render using output semantics.

It should not:

- Contain GTM-specific code.
- Contain benchmark-specific deny lists.
- Chain capabilities unless a declared composition/business capability supports the behavior.
- Override service authority.

## Next Implementation Direction

1. Remove domain-specific phrase lists from the generic runtime.
2. Add a minimal metadata model for intent, business effects, input semantics, required context, and output semantics.
3. Expose approval grant and contract-level composition semantics consistently in discovery and registry packages.
4. Update Studio to infer and review these fields.
5. Update the generator so service declarations and manifests preserve these fields.
6. Update the generic runtime to consume these fields generically.
7. Add tests that reject domain-specific logic in generic runtime, generator, verifier, and registry.
8. Regenerate the GTM package from contract metadata and rerun the benchmark.
