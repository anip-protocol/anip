# ANIP Implementer Skill

> Spec version: ANIP v0.8 | Skill version: 1.3 | Last validated: 2026-03-17

> For agents building ANIP-compliant services. Covers what to implement, in what order, and the common mistakes that break conformance.

## When to Use This Skill

Use this when you need to build a new ANIP-compliant service or add ANIP support to an existing service. This skill gives you the implementation checklist, schema references, and decision points for each primitive.

## Implementation Order

Build in this order. Each step depends on the previous ones.

```
 1. Models          Define your Pydantic/schema types for all ANIP primitives
 2. Capabilities    Declare your capabilities with full metadata
 3. Manifest        Build the manifest from capability declarations
 4. Discovery       Implement /.well-known/anip
 5. Handshake       Profile compatibility endpoint
 6. Delegation      Token registration and validation
 7. Permissions     Permission discovery endpoint
 8. Invocation      Capability execution with full validation
 9. Graph           Capability prerequisites and composition
10. Audit           Observability and audit log endpoint
```

---

## Step 1: Models

Define types for all ANIP primitives. These are the building blocks everything else uses.

**MUST implement (core primitives):**

| Model | Purpose | Reference |
|-------|---------|-----------|
| `CapabilityDeclaration` | Full capability metadata | Spec §4.1 |
| `SideEffect` | Side-effect type + rollback window | Spec §4.2 |
| `DelegationToken` | Authorization chain node | Spec §4.3 |
| `PermissionResponse` | Available/restricted/denied capabilities | Spec §4.4 |
| `ANIPFailure` | Structured error with resolution | Spec §4.5 |
| `InvokeRequest` | Delegation token + parameters | Spec §6.2 |
| `InvokeResponse` | Success/failure + result + cost actual | Spec §6.2 |

**SHOULD implement (contextual primitives):**

| Model | Purpose | Reference |
|-------|---------|-----------|
| `Cost` | Cost certainty model (fixed/estimated/dynamic) | Spec §5.1 |
| `CostActual` | Actual cost returned after invocation | Spec §5.1 |
| `SessionInfo` | State and session semantics | Spec §5.3 |
| `ObservabilityContract` | What's logged, retention, who can audit | Spec §5.4 |

**Side-effect types (enum):**

```
read          → no state changes
write         → reversible state changes
irreversible  → cannot be undone (financial transactions, sent emails)
transactional → atomic, all-or-nothing
```

**Cost certainty levels (enum):**

```
fixed         → exact cost known upfront (e.g., free API calls)
estimated     → approximate cost with range (use determined_by for exact)
dynamic       → cost depends on runtime factors (use upper_bound for max)
```

---

## Step 2: Capability Declarations

Each capability your service exposes needs a full declaration. This is the most important step — everything else derives from these.

**Checklist per capability:**

- [ ] `name` — unique identifier, snake_case
- [ ] `description` — one sentence, what it does
- [ ] `contract_version` — starts at `"1.0"`, bump on any schema change
- [ ] `inputs` — list of `{name, type, description, required, default}`
- [ ] `output` — `{type, fields}` describing the response shape
- [ ] `side_effect` — type + `rollback_window` (`"none"`, `"PT24H"`, `"not_applicable"`)
- [ ] `minimum_scope` — the delegation scopes needed to invoke (array)
- [ ] `cost` — certainty level + financial/compute details
- [ ] `requires` — list of prerequisite capabilities (if any)
- [ ] `composes_with` — capabilities that work well together (if any)
- [ ] `session` — session semantics (if stateful)
- [ ] `observability` — what's logged, retention period, who can access

**Common mistake:** Declaring `side_effect: read` for a capability that creates audit logs or analytics events. If the capability creates any persistent record visible to the user, it's `write`, not `read`. Reserve `read` for truly stateless queries.

---

## Step 3: Manifest

The manifest aggregates all capability declarations with protocol and profile metadata.

```python
manifest = ANIPManifest(
    protocol="anip/1.0",
    profile=ProfileVersions(
        core="1.0",           # MUST
        cost="1.0",           # SHOULD
        capability_graph="1.0",  # SHOULD
        state_session="1.0",  # SHOULD
        observability="1.0",  # SHOULD
    ),
    capabilities={
        "capability_name": DECLARATION,
        # ... all capabilities
    },
)
```

**Compliance rule:** If all 9 primitives are declared in the profile, your service is `anip-complete`. If only the 5 core primitives, it's `anip-compliant`. The discovery document must report this correctly.

---

## Step 4: Discovery Endpoint

**Endpoint:** `GET /.well-known/anip`

This is the single entry point to your service. It must be lightweight and cacheable.

**Required fields:**

```yaml
anip_discovery:
  protocol: "anip/1.0"
  compliance: "anip-complete"    # derived from profile
  base_url: "https://your-service.com"  # from incoming request
  profile: { core: "1.0", cost: "1.0", ... }
  auth:
    delegation_token_required: true
    supported_formats: ["anip-v1"]
    minimum_scope_for_discovery: "none"
  capabilities:                  # summary, not full declarations
    your_capability:
      description: "What it does"
      side_effect: "read"
      minimum_scope: ["required.scope"]  # array, AND semantics
      financial: false
      contract: "1.0"
  endpoints:
    manifest: "/anip/manifest"
    handshake: "/anip/handshake"
    permissions: "/anip/permissions"
    invoke: "/anip/invoke/{capability}"
    tokens: "/anip/tokens"
    graph: "/anip/graph/{capability}"
    audit: "/anip/audit"
  metadata:                      # RECOMMENDED
    service_name: "Your Service"
    service_description: "What your service does"
    generated_at: "2026-03-07T..."
    ttl: "PT1H"
```

**Common mistakes:**
- Hardcoding `base_url` instead of deriving from the request
- `compliance` not matching actual profile contents
- `minimum_scope` as a string instead of an array
- Missing `financial` flag on capabilities that cost money

---

## Step 5: Handshake Endpoint

**Endpoint:** `POST /anip/handshake`

**Input:** `{ "required_profiles": { "core": "1.0", "cost": "1.0" } }`

**Logic:**
1. Compare each required profile against your manifest's profile versions
2. If all match → `compatible: true`
3. If any missing or version mismatch → `compatible: false` with details in `missing`

**Response:**
```json
{
  "compatible": true,
  "service_profiles": { "core": "1.0", "cost": "1.0", ... },
  "missing": null
}
```

---

## Step 6: Delegation Chain

**Endpoint:** `POST /anip/tokens`

**What to validate on registration:**
- Token has required fields (token_id, issuer, subject, scope, expires)
- Token ID is unique
- If `parent` is specified, the parent token exists and is registered

**What to validate on invocation (in the invoke endpoint):**
1. Token is not expired
2. Token scope includes the capability's `minimum_scope`
3. Token purpose matches the capability being invoked
4. Delegation depth does not exceed `max_delegation_depth`
5. Parent chain is valid (all ancestors are registered and not expired)
6. Budget authority is sufficient (if the capability has financial cost)

**Scope matching rules:**
- `travel.search` matches `minimum_scope: ["travel.search"]`
- `travel.book:max_$500` matches `minimum_scope: ["travel.book"]` with a $500 budget constraint

> **Open question:** Wildcard scope matching (e.g., `travel.*` matching all `travel.` scopes) is not defined in ANIP v0.8. Do not implement wildcards — two services implementing them differently will break agent interoperability. This is tracked as an open design question in Spec §13.

---

## Step 7: Permission Discovery

**Endpoint:** `POST /anip/permissions`

**Input:** A delegation token.

**Logic:** For each capability in the manifest:
1. Check if the token's scope covers the capability's `minimum_scope`
2. If yes → add to `available` with any constraints (e.g., budget limits)
3. If partially → add to `restricted` with reason
4. If no → add to `denied` with reason

---

## Step 8: Invocation

**Endpoint:** `POST /anip/invoke/{capability_name}`

**Validation order:**
1. Capability exists → if not, return `unknown_capability` failure
2. Delegation chain is valid → if not, return appropriate delegation failure
3. Parameters are valid → if not, return `invalid_parameters` failure
4. Execute the capability
5. Log the invocation to the audit trail (success or failure)
6. Return `InvokeResponse` with result and `cost_actual` (if applicable)

**Every failure must be an `ANIPFailure` object.** Never return a raw HTTP error for an ANIP-level problem. HTTP errors are for transport-level issues (service down, malformed JSON). ANIP failures are for protocol-level issues (insufficient scope, expired token, missing parameters).

**Failure object structure:**
```json
{
  "type": "insufficient_scope",
  "detail": "human-readable explanation",
  "resolution": {
    "action": "request_scope_upgrade",
    "requires": "travel.book",
    "grantable_by": "human:user@example.com"
  },
  "retry": true
}
```

---

## Step 9: Capability Graph

**Endpoint:** `GET /anip/graph/{capability_name}`

Return the `requires` and `composes_with` lists from the capability declaration. Simple pass-through from the manifest.

---

## Step 10: Audit Endpoint

**Endpoint:** `GET /anip/audit`

**Purpose:** Expose the invocation audit log to authorized consumers. This is the queryable surface of your observability contract (Spec §5.4).

**Query parameters to support:**
- `capability` — filter by capability name
- `since` — ISO 8601 timestamp, return entries after this time
- `limit` — max entries to return (default: 100, cap at 1000)

**What to log per invocation:**
- Capability name
- Timestamp
- Root principal from the delegation chain
- Success/failure status
- Result summary (not full payload — avoid storing sensitive data)
- Delegation chain token IDs (for traceability)

**Access control:**
- Restrict access by delegation chain — a consumer should only see audit records where their root principal was in the chain
- In the reference implementation, this is simplified (all records returned), but production implementations MUST enforce this

**Storage:**
- Use the same persistence layer as your token store (SQLite for reference, database in production)
- Respect the `retention` period from your `ObservabilityContract` — purge entries older than the declared retention
- Index on `capability` and `timestamp` for efficient filtering

**Include in discovery:** Add `"audit": "/anip/audit"` to the `endpoints` map in your discovery document.

---

## Conformance Checklist

Before shipping, verify against Spec §8:

- [ ] `/.well-known/anip` returns valid discovery document
- [ ] `compliance` field matches profile contents
- [ ] `base_url` is derived from the incoming request, not hardcoded
- [ ] All declared endpoints resolve (return non-404)
- [ ] Handshake accepts/rejects profiles correctly
- [ ] Manifest capabilities match discovery summaries
- [ ] `minimum_scope` is an array in discovery, not a string
- [ ] `financial` flag is present and consistent with cost signaling (`cost.financial` non-null → `true`)
- [ ] `capability_side_effect_types_present` in metadata matches per-capability `side_effect` declarations
- [ ] `audit` endpoint is listed in discovery `endpoints` (if observability profile is implemented)
- [ ] All invocations (success and failure) are logged to the audit trail
- [ ] Audit log respects declared `retention` period from observability contract
- [ ] Audit endpoint restricts access by delegation chain root principal
- [ ] Expired tokens are rejected
- [ ] Purpose-binding is enforced
- [ ] Max delegation depth is enforced
- [ ] All failures return structured `ANIPFailure` objects
- [ ] No raw HTTP error codes for ANIP-level failures

---

## Reference Implementation

See `examples/anip/` in the ANIP repository for a complete working example (Python/FastAPI):

- `anip_server/primitives/models.py` — all Pydantic models
- `anip_server/primitives/manifest.py` — manifest construction
- `anip_server/primitives/delegation.py` — delegation chain validation
- `anip_server/primitives/permissions.py` — permission discovery
- `anip_server/capabilities/` — capability declarations and handlers
- `anip_server/main.py` — all endpoints
- `demo.py` — full 7-step agent interaction flow

See `examples/anip-ts/` for the TypeScript/Hono equivalent, `packages/go/examples/flights/` for the Go reference implementation, `packages/java/anip-example-flights/` for the Java/Spring Boot reference implementation, and `packages/csharp/src/Anip.Example.Flights/` for the C#/ASP.NET Core reference implementation.

## References

- **Spec:** https://github.com/anip-protocol/anip/blob/main/SPEC.md
- **Schema (all types):** https://github.com/anip-protocol/anip/blob/main/schema/anip.schema.json
- **Schema (discovery):** https://github.com/anip-protocol/anip/blob/main/schema/discovery.schema.json
- **Guide:** https://github.com/anip-protocol/anip/blob/main/GUIDE.md
- **Reference implementation (Python):** https://github.com/anip-protocol/anip/tree/main/examples/anip
- **Reference implementation (TypeScript):** https://github.com/anip-protocol/anip/tree/main/examples/anip-ts
- **Reference implementation (Go):** https://github.com/anip-protocol/anip/tree/main/packages/go/examples/flights
- **Reference implementation (Java):** https://github.com/anip-protocol/anip/tree/main/packages/java/anip-example-flights
- **Reference implementation (C#):** https://github.com/anip-protocol/anip/tree/main/packages/csharp/src/Anip.Example.Flights
