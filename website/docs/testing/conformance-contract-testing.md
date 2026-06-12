---
title: Conformance, Contract, and Scenario Testing
description: How ANIP separates protocol correctness, package trust, generator parity, behavioral claims, live smokes, and scenario validation.
---

# Conformance, Contract, and Scenario Testing

ANIP uses multiple validation layers because different failures look similar from the outside.

A service can speak the protocol correctly while implementing the wrong business behavior. A generated service can expose the right manifest while one language drifts from another. A fronting package can verify cryptographically while its backend code still leaks a raw API escape hatch.

Do not collapse these into one generic “tests passed” claim.

## Validation map

| Layer | Question it answers | Typical timing |
| --- | --- | --- |
| Package verification | Is this package/lock/signature/digest the artifact I intend to consume? | Before generation and CI release gates |
| Protocol conformance | Does this running service speak ANIP correctly? | Runtime/library release and service certification |
| Generator conformance | Does code generation preserve the contract shape across targets? | Generator changes and language-target releases |
| Manifest parity | Do generated services expose the same public contract? | Multi-language generated service checks |
| Contract testing | Does observed behavior match declared claims such as side effects and cost? | Service implementation validation |
| Execution scenario validation | Does the service produce the governed outcomes required by product scenarios? | Product/release behavior gates |
| Live smoke testing | Does this implementation work against the real or local backend? | Fronting/showcase/integration readiness |
| LLM question-bank testing | Can an agent runtime plan and invoke the right ANIP capability under realistic language? | Showcase and agent-consumption validation |

## Conformance suites shipped today

ANIP ships two distinct conformance suites. They test different boundaries and should both be part of release readiness.

| Suite | Repo location | What it validates | Language scope |
| --- | --- | --- | --- |
| Protocol conformance package | `conformance/` | A running service speaks ANIP correctly over the protocol surface: discovery, manifests, tokens, permission checks, invocation, audit, checkpoints, lineage, and v0.24 input-resolution metadata. | Language-agnostic HTTP tests that can run against Python, TypeScript, Go, Java, and C# generated services. |
| Generator conformance package | `packages/go/generator/testdata/generator-conformance-*.json` plus generator conformance tests | `anip generate` preserves the same contract semantics in generated source, runtime metadata, policy seams, backend adapter defaults, and agent-consumption artifacts. | Explicitly covers all five supported generation targets: Python, TypeScript, Go, Java, and C#. |

This distinction matters. Protocol conformance proves a running service obeys ANIP. Generator conformance proves generated code for every target preserves the same ANIP contract before the service is even exercised by a product-specific scenario bank.

## Package verification

**Question**: Am I consuming the intended signed package?

Package verification checks:

- Package identity and version.
- Manifest digest.
- Service definition digest.
- Recommended lock.
- Registry receipt and signing key.
- Optional implementation-material refs and digests.

Use this before generating code from a Registry package or bundle:

```bash
anip verify \
  --registry-url http://127.0.0.1:8200/registry-api/v1 \
  --package jira-fronting-showcase@0.2.3
```

Package verification is not behavior validation. It proves artifact integrity and trust posture.

## Protocol conformance

**Question**: Does this implementation speak ANIP correctly?

The conformance suite runs protocol-level tests against any ANIP HTTP service. It validates:

- Discovery document structure and required fields.
- Manifest format, signing, and SHA-256 integrity.
- Token issuance and JWT validation.
- Permission discovery response structure.
- Invocation request/response contract.
- Audit logging and queryability.
- Checkpoint format and Merkle root integrity.
- Input-resolution metadata shape.
- Authority, lineage, binding, recovery, and cross-service hints.

Run it against a running service:

```bash
pip install -e ./conformance
pytest conformance/ \
  --base-url=http://localhost:9100 \
  --bootstrap-bearer=demo-human-key
```

The suite is language-agnostic because it tests the HTTP protocol surface. It can run against Python, TypeScript, Go, Java, and C# services.

## Generator conformance and parity

**Question**: Does generation preserve the same ANIP contract across targets?

Generator conformance catches bugs before they become product-specific failures. It should not depend on the GTM question bank.

It checks that generated targets preserve:

- Capability IDs.
- Required and optional inputs.
- `semantic_type`, `entity_reference`, `catalog_ref`, and `input_meanings`.
- `resolution` metadata from `anip/0.24`.
- Side-effect posture.
- Minimum scopes.
- Approval/grant policy.
- Composition metadata.
- Agent-consumption artifacts.
- Transport choices such as HTTP and stdio.

Generator parity means the generated public manifest remains equivalent across Python, TypeScript, Go, Java, and C# for the same package.

Domain-specific custom bundles may implement behavior differently per language. They must not mutate the signed public declaration.

## Contract testing

**Question**: Does this service behave as it declares?

A service can pass conformance while still being misleading about behavior. Contract testing verifies declared claims against observed reality.

| Check | What it verifies |
| --- | --- |
| Read purity | Capabilities declaring `side_effect.type = read` do not mutate state. |
| Event classification | Audit `event_class` matches the declared side-effect type. |
| Cost presence | Financial capabilities return `cost_actual` where declared. |
| Compensation workflow | Declared compensation paths actually work. |
| Approval boundary | Approval-gated capabilities stop before mutation. |

Run contract tests:

```bash
pip install -e ./contract-tests
anip-contract-tests \
  --base-url=http://localhost:9100 \
  --test-pack=contract-tests/packs/travel.json
```

Contract tests report confidence levels:

| Result | Meaning |
| --- | --- |
| `PASS (elevated)` | Both audit and storage probes agree. |
| `PASS (medium)` | Audit probe only; no violations found in audit trail. |
| `FAIL (elevated)` | Storage probe detected unexpected mutation. |
| `WARN` | Changes detected that may be unrelated background activity. |

## Execution scenario validation

**Question**: Does the service produce the governed outcomes the product scenarios require?

Scenario validation is higher-level than protocol conformance. It tests user-facing execution behavior:

| Scenario class | What it verifies |
| --- | --- |
| Happy path | Required inputs produce the expected available result. |
| Missing input | Service returns `clarification_required`, not a guess. |
| Ambiguous reference | Service follows declared input-resolution policy. |
| Unsupported request | Service returns restricted or denied behavior, not best-effort execution. |
| Approval path | Service stops at `approval_required` and resumes only with a valid grant. |
| Composition | Parent and child invocations preserve lineage, scope, and failure policy. |
| Fronting boundary | Backend options stay bounded and audited; raw API escape hatches are not exposed. |

For generated services, scenario validation also catches language drift:

- Same package.
- Same generated public manifest.
- Same custom-bundle intent.
- Same scenario pack.
- Same expected outcomes across Python, TypeScript, Go, Java, and C#.

See [Execution Scenario Validation](/docs/concepts/execution-scenario-validation) for the design pattern.

## Live smoke testing

**Question**: Does the service work against the real backend without bypassing ANIP?

Live smokes are especially important for fronting packages. They should prove:

- Read-only capabilities work with real credentials or local backend fixtures.
- Preview/prepare capabilities do not mutate backend state.
- Approved mutation paths require a real ANIP approval grant.
- Mutation guard flags are explicit, such as `ANIP_SLACK_ALLOW_SEND=true`.
- Backend errors are normalized into ANIP outcomes.
- Secrets are read from local env files or platform secrets, not package artifacts.

Examples include the Jira, GitHub, GitLab, Slack, Linear, Notion, and Superset fronting smoke scripts under `examples/showcase/*_fronting/scripts/`.

## LLM question-bank testing

**Question**: Can an agent runtime use the ANIP contract correctly under realistic language?

This is not protocol conformance. It tests the agent-consumption layer: capability selection, parameter grounding, clarification turns, approval boundaries, denial behavior, and response handling.

The GTM showcase currently uses:

| Bank | Purpose | Count |
| --- | --- | --- |
| Phase banks | Happy paths, clarification, denial, restriction, approval, actor variation, and composition. | 350 |
| Variation banks | Wording variation, unsupported effects, derived targets, approval boundaries, enum grounding, and raw-export denial. | 140 |
| Combined gate | Full GTM scenario behavior across generated stacks. | 490 |

Run phase-sized banks while debugging. Use full 350/140/490 runs as release gates.

If a question-bank case fails, do not immediately patch a phrase. First decide whether:

- The contract is missing a generic behavior primitive.
- The generated service violates the contract.
- The custom bundle violates the contract.
- The agent runtime is losing context or routing incorrectly.
- The scenario expectation is wrong.

## Recommended release gate

For a serious ANIP service release, require:

- Package verification passes against the intended Registry or bundle.
- Protocol conformance passes for the running service.
- Generated outputs preserve manifest parity if multiple languages/frameworks are claimed.
- Contract tests pass for declared side effects, approval boundaries, and cost/recovery claims.
- Scenario validation passes for product-critical behavior.
- Live smokes pass for fronting/backend integrations.
- Question-bank or agent-consumption tests pass when an agent runtime is part of the release claim.

## Why separation matters

A service can pass conformance while declaring `read` capabilities that actually write data. It can pass contract tests while asking for clarification when the product scenario requires an approval stop. It can pass a narrow GTM question bank while generator conformance misses an untested protocol field.

ANIP treats protocol correctness, artifact trust, generated-code parity, behavioral truthfulness, and scenario execution quality as separate concerns because they fail in different ways.
