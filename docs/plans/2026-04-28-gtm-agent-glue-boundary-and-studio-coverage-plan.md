# GTM Agent Glue Boundary And Studio Coverage Plan

Date: 2026-04-28

Status: Active plan

## Decision

ANIP should not claim to eliminate all agent/application glue.

The stronger and more defensible claim is:

> ANIP reduces service-integration glue, standardizes the remaining contract-backed behavior, and makes unavoidable product/application glue explicit.

The GTM showcase is complex enough that a zero-glue generic agent is not the right target. The correct target is a clean separation between:

- A reusable ANIP substrate.
- Contract-backed GTM services and package metadata.
- A GTM agent application layer for product-specific experience.
- Studio coverage analysis that identifies what is native, custom, glue, external, or unsupported.

## Architecture Boundary

### 1. Generic ANIP Substrate

The generic runtime may handle:

- Registry/package loading.
- Service discovery and capability catalog loading.
- Token issuance from declared scopes.
- Capability invocation.
- Standard ANIP failures.
- Approval grant flow.
- Lineage, signatures, verification, and receipts.
- Basic generic result rendering.

The generic runtime must not contain:

- GTM-specific prompts.
- GTM-specific capability IDs.
- Benchmark-specific phrase lists.
- Business-domain enum normalization.
- Service workflow recreation.
- Product-specific result rendering.

### 2. GTM ANIP Package And Services

The GTM package/services own authoritative business behavior:

- Capabilities.
- Inputs and outputs.
- Scopes and grant policies.
- Side effects.
- contract-level composed business capabilities.
- Service-owned validation.
- Descriptive ANIP errors.
- Minimal contract metadata such as controlled business effects.

### 3. GTM Agent App

The GTM app layer may contain product glue:

- GTM-specific system prompt and product framing.
- Demo actors and UX choices.
- Result presentation.
- Small app-level routing only when it is product experience, not hidden service integration.
- Benchmark harness behavior outside the production runtime.

The GTM app must not duplicate:

- Endpoint paths when discoverable.
- Token scopes when declared.
- Approval protocol.
- Hidden service workflows.
- Registry/package contract facts.

## Studio Coverage Identification

Studio should bring back the original intent: identify whether a desired solution is fully supported by native ANIP or needs glue/custom work.

For each product requirement or capability, Studio should classify implementation fit:

- `native_anip`: fully covered by declared ANIP capabilities, metadata, grants, composition, and generated code.
- `contract_gap`: desired behavior is clear, but the contract is missing capability/input/effect/approval metadata.
- `custom_service_logic`: requires domain/business logic inside a service implementation.
- `agent_app_glue`: requires prompt, UX framing, ranking, result presentation, memory, or product-specific orchestration.
- `external_integration`: requires a non-ANIP backend, database, SaaS API, or MCP service.
- `unsupported`: out of scope, unsafe, or not represented by this package.

Project-level Studio output should include:

- A coverage summary.
- A list of native ANIP areas.
- A list of required custom service implementations.
- A list of required agent-app glue.
- Unsupported requests or effects.
- Contract gaps that should be fixed before publication.

## Minimal Metadata Addition Now

Do not implement the full agent consumability metadata proposal yet.

Implement only controlled `business_effects` first:

```json
{
  "business_effects": {
    "produces": ["content.draft"],
    "does_not_produce": ["external_dispatch", "system.mutation", "raw_data_export"]
  }
}
```

Initial controlled effect vocabulary:

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

- Avoid phrase-list rabbit holes.
- Help agents distinguish draft vs send, summary vs raw export, preview vs mutation.
- Keep semantics contract-backed without turning ANIP into a skill/prompt framework.

## Implementation Steps

1. Revert the generic runtime back to a clean ANIP substrate.
2. Create a `gtm_agent_app` layer separate from the generic runtime.
3. Move GTM prompt, framing, and result rendering into the GTM app layer.
4. Keep service integration generic through ANIP discovery, token issuance, invocation, and grants.
5. Add controlled `business_effects` as the only near-term metadata addition.
6. Use contract-level composition for real business capabilities, not agent-side workflow recreation.
7. Add Studio implementation-fit/coverage classification.
8. Rerun the GTM 350 tests and classify failures as contract gaps, custom service logic gaps, or acceptable GTM app glue.

## Behavior Contract Hardening

The generated stack must close the gap between declared behavior and implemented behavior.

The correct chain is:

```text
Studio intent -> locked contract behavior -> generated/service implementation -> verifier/conformance tests -> optional app glue
```

This is generic even when a domain package needs app glue. Generic means the platform has reusable mechanisms for declared behavior and explicit glue classification, not that every business app becomes zero-glue.

### What Must Be Generic

The platform should handle these declared behaviors mechanically across domains:

- input defaults
- required inputs
- allowed values
- input formats
- clarification rules
- side effects and business effects
- approval policies and grants
- contract-level composition
- output shape and display hints
- audit, scopes, lineage, and verification

When the contract says `ranking_basis` defaults to `risk_score`, services generated from that contract must apply that default. The agent should not need to know or invent it.

When the contract says `quarter` is an explicit label like `2017-Q2`, services should reject relative values such as `this quarter` with `clarification_required`. The app may help explain this, but the service remains authoritative.

### What Is Partially Inferred

Studio assistants may infer candidate domain intelligence, but the locked artifact must be reviewed and approved by PM/dev owners.

Examples:

- suggested defaults
- enum meanings
- safe clarification boundaries
- unsupported effects
- composition candidates
- app-glue recommendations

The assistant output is advisory. The deterministic locked contract is authoritative.

### What May Stay As Glue

App glue is acceptable when it is explicit and isolated:

- product framing and tone
- result presentation
- app-level UX flow
- domain-specific prompt hints
- ambiguous business request handling that is not contract semantics

This glue should be visible in Studio coverage output. It must not be hidden in the generic ANIP runtime, generator, verifier, or registry.

### Immediate Hardening Tasks

1. Add a Studio coverage gate for behavior completeness: defaults, formats, allowed values, clarification behavior, effects, grants, and output shape.
2. Add contract fields for input format/semantic validation where descriptions are currently carrying machine-relevant behavior.
3. Make generators apply input defaults before required-input checks in every target.
4. Make generators preserve input defaults and allowed values in all runtime declarations.
5. Add conformance fixtures that prove declared defaults, formats, and allowed values are enforced.
6. Use the manually created GTM service as a behavioral oracle, but only port behavior that is contract-backed or should become contract-backed.
7. Classify every generated-stack benchmark miss as `contract_gap`, `generator_gap`, `custom_service_logic_gap`, `app_glue_gap`, or `test_gap`.
8. Keep the benchmark runtime on `gpt-5.4-mini` unless an explicit model comparison is being run.

## Studio App-Glue Guidance

Studio should not stop at "this needs glue." It should suggest what kind of glue is expected.

Initial recommended app-glue categories:

- `capability_framing`: role, tone, product context, and capability ranking preferences.
- `result_display`: how the app should present drafts, summaries, recommendations, evidence, and rationale.
- `app_boundaries`: effect-level boundaries such as draft vs dispatch or summary vs raw export.
- `input_meanings`: compact value meanings for app-level parameter grounding where enum values need business interpretation.

These recommendations are app-layer guidance. They are not protocol requirements unless repeated usage proves they should become durable ANIP metadata.

## Registry And Package Hardening Follow-Up

The registry package should become more practical and safer before broader distribution.

Package metadata:

- Implemented: registry publication accepts a package README and source/project links, normalizes them into the signed manifest, and exposes them on package records.
- Implemented: source links are constrained to HTTP(S) URLs with bounded titles and URLs.
- Keep these metadata fields signed as part of the manifest/registry record so consumers can trust what they inspect.

Abuse controls:

- Implemented: registry publish requests have a hard size ceiling.
- Implemented: README and source-link fields have explicit registry-side limits.
- Add finer-grained limits for manifests, service definitions, lock files, and optional attachments.
- Reject packages with excessive nesting, excessive capability counts, oversized examples, or suspicious binary payloads.

Generator and validator hardening:

- Treat package metadata as untrusted input.
- Validate identifiers, paths, package names, module names, service names, ports, Docker image names, and generated filenames against strict allowlists.
- Prevent path traversal, shell injection, template injection, import/module name abuse, and generated Dockerfile command injection.
- Avoid executing package-provided code during validation or generation.
- Add malicious fixture tests for unsafe names, paths, scripts, environment variables, Docker directives, and custom bundle declarations.

Custom code bundle sharing:

- Keep custom code bundles separate from the signed ANIP behavior contract unless explicitly attached as implementation material.
- Implemented: support a generator flag such as `--custom-code-bundle` for local filesystem bundles.
- Implemented: reserve and validate `--custom-code-bundle-ref` for immutable references such as git commit URLs, registry artifact references, or object-store digests.
- Implemented: require digest pinning for remote bundle refs and reject floating branches, `latest`, credentials, query strings, path traversal, unsafe characters, and missing digests.
- Implemented: keep remote refs metadata-only by default; generation reports declared refs and warnings without fetching or applying remote code.
- Implemented: local custom bundles produce a normalized tree digest and can be blocked with `--verify-custom-code-bundle-digest` or package-declared `bundle_tree_sha256`.
- Implemented: registry publication accepts typed `implementation_materials`, validates pinned custom bundle refs, stores them in signed manifest metadata, and exposes them on package records.
- Not implemented yet: fetching or applying remote bundle refs.
- Make generator behavior explicit: the bundle may fill extension points, but it must not rewrite generated substrate files or bypass contract validation.

Open question:

- Whether the registry stores custom code bundles directly, stores only immutable references, or supports both under different trust modes.

## Non-Goals

- No claim that any agent can consume any ANIP service perfectly with zero context.
- No full implementation of the eight-point agent consumability proposal in this phase.
- No GTM-specific behavior in generic generator, verifier, registry, or substrate runtime.
- No hidden benchmark hacks.
