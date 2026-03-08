# ANIP Validator Skill

> Spec version: ANIP v0.1 | Skill version: 1.0 | Last validated: 2026-03-08

> For agents that need to test, validate, or audit ANIP-compliant services for conformance.

## When to Use This Skill

Use this when you need to verify that an ANIP service conforms to the spec — whether you're an implementer testing your own service, an agent evaluating a new service before trusting it, or an auditor checking conformance for a third party.

## Conformance Levels

ANIP defines three levels of validation rigor. Each level builds on the previous:

| Level | What It Tests | Can Test Externally? | Required? |
|-------|--------------|---------------------|-----------|
| **Structural** | Documents conform to schemas | Yes, fully | MUST pass |
| **Behavioral** | Edge cases handled correctly (expired tokens, purpose-binding, depth limits) | Yes, using adversarial inputs | SHOULD pass |
| **Semantic** | Declared behavior matches actual behavior (side-effects, costs) | Partially — requires sandbox or audit log | SHOULD (MUST in v2) |

## Compliance Detection

Before running tests, determine the service's compliance level:

```
GET /.well-known/anip → compliance field
```

| Compliance | Meaning | What to Test |
|-----------|---------|-------------|
| `anip-compliant` | 5 core primitives (Spec §4) | Categories 1-5 |
| `anip-complete` | All 9 primitives (Spec §4 + §5) | Categories 1-6 + audit |

**Verification rule:** If `compliance` is `anip-complete`, verify that ALL four contextual profile keys (`cost`, `capability_graph`, `state_session`, `observability`) are present in the `profile` block. If any are missing, the service is overclaiming compliance.

---

## Category 1: Discovery Validation

**What:** The discovery document is structurally valid and internally consistent.

**How to test:**

1. **Fetch and validate schema**
   ```
   GET /.well-known/anip
   ```
   Validate the response against the discovery schema. The response MUST contain: `protocol`, `compliance`, `base_url`, `profile`, `auth`, `capabilities`, `endpoints`.

2. **Check compliance consistency**
   - If `compliance: "anip-complete"`, verify `profile` contains `cost`, `capability_graph`, `state_session`, `observability`
   - If `compliance: "anip-compliant"`, verify `profile` contains at minimum `core`

3. **Check capability metadata**
   - Every capability MUST have: `description`, `side_effect`, `minimum_scope`, `financial`, `contract`
   - `minimum_scope` MUST be an array (not a string)
   - `side_effect` MUST be one of: `read`, `write`, `irreversible`, `transactional`
   - `financial` MUST be a boolean

4. **Check metadata consistency**
   - `capability_side_effect_types_present` MUST match the set of `side_effect` values across all capabilities
   - Example: if capabilities have `read` and `irreversible`, the metadata MUST contain `["irreversible", "read"]` (sorted)

5. **Check endpoint resolution**
   - For every endpoint in the `endpoints` map, construct the full URL using `base_url` + endpoint path
   - Verify each URL returns non-404 (a 401/403 is acceptable — it means the endpoint exists but requires auth)

**Common violations:**
- `minimum_scope` as a string instead of an array
- `financial` flag missing entirely
- `compliance: "anip-complete"` with missing profile keys
- `base_url` hardcoded instead of derived from request (test by hitting the service from different hostnames if possible)

---

## Category 2: Handshake Validation

**What:** The profile handshake correctly reports compatibility.

**How to test:**

1. **Matching profiles** — send a handshake requesting only profiles the service declares:
   ```json
   POST {endpoints.handshake}
   {"required_profiles": {"core": "1.0"}}
   ```
   Expected: `compatible: true`, `missing: null`

2. **Missing profile** — request a profile the service doesn't implement:
   ```json
   {"required_profiles": {"core": "1.0", "nonexistent_profile": "1.0"}}
   ```
   Expected: `compatible: false`, `missing` lists the unsupported profile

3. **Version mismatch** — request a profile version higher than what the service supports:
   ```json
   {"required_profiles": {"core": "99.0"}}
   ```
   Expected: `compatible: false`

4. **Full profile check** — verify the response's `service_profiles` matches what's in the discovery document's `profile` block

---

## Category 3: Capability Contract Validation

**What:** Manifest declarations are consistent with discovery summaries.

**How to test:**

1. **Fetch manifest**
   ```
   GET {endpoints.manifest}
   ```

2. **Cross-reference with discovery** — for each capability:
   - Manifest `name` matches discovery key
   - Manifest `side_effect.type` matches discovery `side_effect`
   - Manifest `contract_version` matches discovery `contract`
   - Manifest `required_scope` when wrapped as `[required_scope]` matches discovery `minimum_scope`

3. **Financial flag consistency**
   - If manifest `cost.financial` is non-null → discovery `financial` MUST be `true`
   - If manifest `cost.financial` is null → discovery `financial` MUST be `false`
   - Do NOT check based on amount values — the flag is about presence of financial cost declaration, not its magnitude

4. **Input/output schemas** — verify each capability's `inputs` and `output` fields are present and well-formed

**Common violations:**
- Contract version mismatch between discovery and manifest (discovery shows stale version)
- `financial: false` for capabilities with estimated or dynamic costs (the amount-based check bug)
- Missing capabilities in manifest that appear in discovery (or vice versa)

---

## Category 4: Delegation Chain Validation

**What:** The service correctly enforces delegation chain rules.

**How to test:** Register tokens and attempt invocations with various invalid configurations.

1. **Expired token rejection**
   - Register a token with `expires` in the past
   - Attempt invocation → MUST fail with `delegation_expired`

2. **Purpose-binding enforcement**
   - Register a token with `purpose.capability: "search_flights"`
   - Attempt to invoke `book_flight` with that token → MUST fail with `purpose_mismatch`

3. **Delegation depth enforcement**
   - Register a chain of tokens exceeding `max_delegation_depth`
   - Attempt invocation with the deepest token → MUST fail with `delegation_depth_exceeded`

4. **Unregistered parent rejection**
   - Register a token with `parent: "nonexistent_token_id"`
   - Expected: registration fails or invocation fails with an invalid parent error

5. **Scope narrowing enforcement**
   - Register a root token with scope `["travel.search"]`
   - Register a child token with scope `["travel.search", "travel.book"]` (broader than parent)
   - Expected: registration fails or invocation fails — scope can only narrow, never widen

6. **Budget authority**
   - Register a token with scope `["travel.book:max_$100"]`
   - Invoke a capability that costs more than $100
   - Expected: fail with `budget_exceeded`

---

## Category 5: Failure Semantics Validation

**What:** All failures return structured objects, not raw HTTP errors.

**How to test:**

1. **Unknown capability**
   ```
   POST {endpoints.invoke}/nonexistent_capability
   ```
   Expected: `ANIPFailure` with `type: "unknown_capability"` and `resolution.action: "check_manifest"`

2. **Insufficient scope**
   - Register a token with scope `["travel.search"]`
   - Invoke a capability requiring `travel.book`
   - Expected: `ANIPFailure` with `type: "insufficient_scope"`, `resolution.requires`, and `resolution.grantable_by`

3. **All failure fields present**
   - Every failure response MUST include: `type`, `detail`, `resolution`, `retry`
   - `resolution` MUST include at minimum: `action`
   - Validate against the ANIPFailure schema

4. **HTTP status codes**
   - ANIP-level failures (scope, delegation, budget) MUST return structured failure objects, not bare 401/403/500
   - HTTP errors are only appropriate for transport-level issues (malformed JSON, service down)

**Common violations:**
- Returning `{"error": "unauthorized"}` instead of a structured `ANIPFailure`
- Missing `resolution` field in failures
- `retry: true` on failures that are genuinely permanent (e.g., `denied` capabilities)

---

## Category 6: Behavioral Contract Testing

**What:** Declared behavior matches actual behavior. This is the hardest category to test.

### 6a: Sandbox Testing (when available)

Check `metadata.test_mode_available` in the discovery document.

If `true`, the service supports contract testing via the test endpoint:

```yaml
test_mode:
  available: true
  isolation: sandboxed         # sandboxed | recorded | dry-run
  side_effects: suppressed     # actual charges don't occur
  fidelity: behavioral         # responses reflect real logic, not stubs
```

**Fidelity levels:**
- `behavioral` — service runs real logic in a sandboxed context. Most trustworthy.
- `dry-run` — service returns plausible responses without executing real logic. Less trustworthy but better than nothing.

**Tests to run in sandbox:**
1. Invoke a `read` capability → verify no state changes (check audit log before and after)
2. Invoke a `write` capability → verify state changes are isolated to the sandbox
3. Invoke a capability with `estimated` cost → verify `cost_actual` falls within declared `range_min`–`range_max`

### 6b: Audit-Based Verification (when sandbox unavailable)

When `test_mode_available: false`, use the audit endpoint for post-invocation verification:

```
GET {endpoints.audit}?capability=book_flight&since=2026-03-07T00:00:00Z
```

**What to verify:**
1. **Invocations are logged** — after invoking a capability, query the audit log and confirm the entry exists with correct capability name, timestamp, and success/failure status
2. **Cost reconciliation** — compare `cost_actual` from the invocation response with the audit log entry's cost data
3. **Side-effect consistency** — for `read` capabilities, verify the audit log shows no state-changing result (no booking IDs, no mutation markers)
4. **Retention compliance** — query audit entries older than the declared `retention` period in the observability contract. They SHOULD be absent (purged).
5. **Access control** — attempt to query audit records using a token from a different delegation chain. The service SHOULD return only records matching your root principal.

### 6c: When `test_mode_available: false`

Check `test_mode_unavailable_policy`:

| Policy | What It Means | How to Proceed |
|--------|--------------|---------------|
| `proceed_with_caution` | You may invoke capabilities but should apply extra validation | Run Categories 1-5, use audit for Category 6 verification |
| `require_explicit_authorization_for_irreversible` | You MUST get human authorization before irreversible actions | Do NOT invoke irreversible capabilities during automated testing |

---

## Common Spec Violations

These are the most frequently seen violations across ANIP implementations:

| # | Violation | Category | How to Detect |
|---|-----------|----------|--------------|
| 1 | `minimum_scope` as string instead of array | 1 | Schema validation on discovery document |
| 2 | `financial` flag computed from amount instead of presence | 3 | Compare manifest `cost.financial` nullability with discovery `financial` |
| 3 | `compliance: "anip-complete"` with missing profile keys | 1 | Check all 4 contextual profile keys present |
| 4 | Raw HTTP errors instead of `ANIPFailure` objects | 5 | Send invalid requests and check response structure |
| 5 | Purpose-binding not enforced | 4 | Use a token for wrong capability |
| 6 | Scope widening allowed in child tokens | 4 | Register child with broader scope than parent |
| 7 | `base_url` hardcoded | 1 | Access from different hostnames, compare `base_url` values |
| 8 | Manifest/discovery contract version mismatch | 3 | Cross-reference contract versions |
| 9 | `capability_side_effect_types_present` inconsistent | 1 | Compare with actual per-capability side_effect values |
| 10 | Audit log not respecting retention period | 6 | Query for entries older than declared retention |

---

## Validation Report Format

When reporting validation results, use this structure:

```json
{
  "service_url": "https://example.com",
  "validated_at": "2026-03-08T10:00:00Z",
  "compliance_declared": "anip-complete",
  "compliance_verified": "anip-compliant",
  "categories": {
    "1_discovery": {"pass": true, "violations": []},
    "2_handshake": {"pass": true, "violations": []},
    "3_capability_contract": {
      "pass": false,
      "violations": [
        "book_flight: financial flag is false but cost.financial is non-null"
      ]
    },
    "4_delegation_chain": {"pass": true, "violations": []},
    "5_failure_semantics": {"pass": true, "violations": []},
    "6_behavioral": {"pass": null, "violations": [], "note": "test_mode unavailable"}
  },
  "structural_conformance": true,
  "behavioral_conformance": true,
  "semantic_conformance": null
}
```

`pass: null` means the category could not be tested (e.g., no sandbox available).

`compliance_verified` may differ from `compliance_declared` if violations are found — this is the most important output of validation.

---

## Validation Workflow

```
1. Fetch discovery document
2. Validate schema (Category 1)
3. Run handshake tests (Category 2)
4. Fetch manifest, cross-reference (Category 3)
5. Register test tokens, run delegation tests (Category 4)
6. Trigger failures, validate structure (Category 5)
7. If test_mode available → run sandbox tests (Category 6a)
   If audit endpoint available → run audit verification (Category 6b)
8. Generate validation report
```

Steps 1-6 require no service cooperation and can be run against any ANIP service. Step 7 requires either sandbox support or audit access.

---

## References

- **Spec:** https://github.com/anip-protocol/anip/blob/main/SPEC.md
- **Schema (all types):** https://github.com/anip-protocol/anip/blob/main/schema/anip.schema.json
- **Schema (discovery):** https://github.com/anip-protocol/anip/blob/main/schema/discovery.schema.json
- **Consumer skill:** https://github.com/anip-protocol/anip/blob/main/skills/anip-consumer.md
- **Implementer skill:** https://github.com/anip-protocol/anip/blob/main/skills/anip-implementer.md
