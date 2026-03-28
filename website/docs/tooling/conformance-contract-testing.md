---
title: Conformance and Contract Testing
description: Two validation layers — protocol correctness and behavioral truthfulness.
---

# Conformance and Contract Testing

ANIP ships two distinct validation tools. They answer different questions and are used at different points in the development lifecycle.

## Conformance suite

**Question**: Does this implementation speak ANIP correctly?

The conformance suite runs 44 protocol-level tests against any ANIP HTTP service, validating:

- Discovery document structure and required fields
- Manifest format, signing, and SHA-256 integrity
- Token issuance and JWT validation
- Permission discovery response structure
- Invocation request/response contract
- Audit logging and queryability
- Checkpoint format and Merkle root integrity

### Running conformance

```bash
pip install -e ./conformance
pytest conformance/ --base-url=http://localhost:9100 --bootstrap-bearer=demo-human-key
```

The suite is language-agnostic — it tests the HTTP surface, so it works against Python, TypeScript, Java, Go, and C# implementations equally.

## Contract testing

**Question**: Does this service behave as it declares?

A service can pass conformance while still being misleading about behavior. Contract testing verifies that declared claims match observed reality:

| Check | What it verifies |
|-------|-----------------|
| **Read purity** | Capabilities declaring `side_effect.type = read` don't mutate state |
| **Event classification** | Audit `event_class` matches the declared side-effect type |
| **Cost presence** | Financial capabilities return `cost_actual` in responses |
| **Compensation workflow** | Declared compensation paths (e.g., book → cancel) actually work |

### Running contract tests

```bash
pip install -e ./contract-tests
anip-contract-tests \
  --base-url=http://localhost:9100 \
  --test-pack=contract-tests/packs/travel.json
```

### Confidence levels

Contract tests report results with confidence levels:

| Result | Meaning |
|--------|---------|
| `PASS (elevated)` | Both audit and storage probes agree — no violations detected |
| `PASS (medium)` | Audit probe only — no violations in audit trail |
| `FAIL (elevated)` | Storage probe detected unexpected mutation |
| `WARN` | Changes detected that may be background worker activity |

## Why both matter

A service can pass conformance (correct protocol implementation) while still declaring `read` capabilities that actually write data, or financial capabilities that never report cost. ANIP treats protocol correctness and behavioral truthfulness as separate concerns — because they are.
