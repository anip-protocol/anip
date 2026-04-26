# ANIP v0.23 — Composition & Approval Grants Implementation Plan

**Goal:** Bump ANIP to `anip/0.23` adding two protocol-visible capabilities — (1) **composed capabilities** with declarative composition metadata so business-level capabilities can declare internal step composition, empty-result behavior, and failure policy without pushing orchestration into agents; (2) **approval grants** as bounded post-approval authorization objects (`one_time` / `session_bound`) with parameter-digest binding and audit linkage.

**Architecture:** Spec-first protocol bump following the same discipline as v0.20–v0.22. Add `kind` (`atomic`/`composed`) and `composition` block to `CapabilityDeclaration`. Extend the `approval_required` failure response with `preview_digest`, `requested_parameters_digest`, and `grant_policy`. Introduce a token-bound `ApprovalGrant` object referenced by an `approval_grant` field on the invocation request. Service runtime validates grants pre-execution (signature → expiry → uses → capability/scope/digest match → session binding), consumes one-time grants atomically, and writes audit linkage connecting request → grant → continuation → child invocations. v0.22 `parent_token` semantics are preserved unchanged.

**Tech Stack:** All 5 runtimes (Python pydantic, TypeScript zod, Go structs, Java POJOs, C# records). PostgreSQL for grant storage in the server runtime. JSON Schema (draft 2020-12) for protocol schema.

**Design docs:**
- `/Users/samirski/Development/codex/docs/plans/2026-04-25-v023-spec-implementation-design-for-claude-code.md` (handoff design)
- `feat/integration-fronting-projects:docs/specs/2026-04-25-anip-v0.23-composition-and-approval-grants.md` (composition + grant note)

**Source for prior pattern:** `/Users/samirski/Development/codex/docs/plans/2026-04-06-v022-spec-implementation-design-for-claude-code.md`

**Branch:** `feat/anip-v023-composition-and-grants`

**Phase-to-handoff-step mapping:** The Codex handoff doc lists 9 sequential implementation steps. This plan splits that into a Decisions block plus 10 numbered phases for finer-grained execution tracking. Mapping:

| Handoff Step | Plan Phase |
|---|---|
| Step 1 — Finalize normative delta | Decisions Block |
| Step 2 — Update SPEC.md | Phase 1 |
| Step 3 — Update schemas | Phase 2 |
| Step 4 — Bump core constants | Phase 3 (gated on PR 2 per §"Branch & PR Strategy") |
| Step 5 — Update core models | Phase 4 |
| Step 6 — Add runtime validation | Phases 5, 6, 7 |
| Step 7 — Update/add helpers | Phase 7 |
| Step 8 — Update tests + examples | Phases 7.5, 8, 9 |
| Step 9 — Dogfood | Phase 10 |

---

## Decisions Block — Lock Normative Choices Before Touching Code

These shape every later phase. Resolve and write into the spec text in Phase 1.

**Decision 0.1 — Approval grant representation.**
Recommend **token-bound grant object**: a standalone signed grant referenced by `grant_id`, validated independently of `parent_token`. Keeps v0.22 token semantics clean (parent_token still means "the delegation token whose authority this child inherits"). The grant lives alongside the token, not inside it.

**Decision 0.2 — Compatibility for old declarations.**
Capability declarations missing `kind` are interpreted as `atomic`. New v0.23 declarations SHOULD set `kind` explicitly. Schema enforces enum on `kind` when present but does not require it.

**Decision 0.3 — Authority boundary scope for v0.23.**
Ship `same_service` only. `same_package` and `external_service` are reserved enum values; runtimes MUST reject composed declarations using them with `composition_unsupported_authority_boundary` until follow-up work lands.

**Decision 0.4 — Continuation field name.**
`approval_grant` on the invocation request body. Value is the `grant_id` string. The grant object itself is fetched/validated server-side from storage.

**Decision 0.5 — Rejection error types.**
Add to failure type registry:
- `grant_not_found`
- `grant_expired`
- `grant_consumed`
- `grant_capability_mismatch`
- `grant_scope_mismatch`
- `grant_param_drift`
- `grant_session_invalid`
- `approval_request_not_found`
- `approval_request_already_decided`
- `approval_request_expired`
- `approver_not_authorized`
- `grant_type_not_allowed_by_policy`
- `composition_invalid_step`
- `composition_unknown_capability`
- `composition_unsupported_authority_boundary`
- `composition_empty_result_clarification_required`
- `composition_empty_result_denied`

**Decision 0.6 — Approval request and grant storage.**

v0.23 introduces TWO new persistent collections: `approval_requests` (created when a capability returns `approval_required`) and `grants` (created when an approver issues a grant against an approval_request). Same lifecycle: in-memory for InMemoryStorage, PostgreSQL for PostgresStorage. Both are required for grant issuance to work; they are co-evolving.

**`approval_requests` schema:**
```
approval_requests:
  approval_request_id          text PRIMARY KEY
  capability                   text NOT NULL
  scope                        jsonb NOT NULL          -- scopes the approved action would consume
  requester                    jsonb NOT NULL          -- principal that triggered approval_required
  parent_invocation_id         text NULL               -- the original invoke that returned approval_required (audit linkage)
  preview                      jsonb NOT NULL          -- the preview content shown to approvers
  preview_digest               text NOT NULL           -- SHA-256 of canonical preview JSON (Decision 0.7)
  requested_parameters         jsonb NOT NULL          -- the parameters the requester submitted
  requested_parameters_digest  text NOT NULL           -- SHA-256 of canonical parameters JSON
  grant_policy                 jsonb NOT NULL          -- allowed_grant_types, default_grant_type, expires_in_seconds, max_uses
  status                       text NOT NULL           -- "pending" | "approved" | "denied" | "expired"
                                                       -- enforced via CHECK constraint
  approver                     jsonb NULL              -- set when status transitions to "approved" or "denied"; NULL for "expired"
  decided_at                   timestamptz NULL        -- set when status transitions away from "pending"
  created_at                   timestamptz NOT NULL DEFAULT now()
  expires_at                   timestamptz NOT NULL    -- approval request expiry (separate from grant expiry)
  CHECK (status IN ('pending', 'approved', 'denied', 'expired'))
  -- pending: no decided_at, no approver
  CHECK ((status <> 'pending') OR (approver IS NULL AND decided_at IS NULL))
  -- approved/denied: human/principal-driven decisions require approver AND decided_at
  CHECK ((status NOT IN ('approved', 'denied')) OR (approver IS NOT NULL AND decided_at IS NOT NULL))
  -- expired: time-driven transition; decided_at MUST be set (timestamp of expiry processing) but approver MUST be NULL (no human decided)
  CHECK ((status <> 'expired') OR (approver IS NULL AND decided_at IS NOT NULL))
```

**`grants` schema:**
```
grants:
  grant_id                     text PRIMARY KEY
  approval_request_id          text NOT NULL UNIQUE    -- FK to approval_requests; UNIQUE prevents double-issue
  grant_type                   text NOT NULL           -- "one_time" | "session_bound"
  capability                   text NOT NULL           -- copied from approval_request at issuance
  scope                        jsonb NOT NULL          -- copied from approval_request at issuance
  approved_parameters_digest   text NOT NULL           -- copied from approval_request.requested_parameters_digest
  preview_digest               text NOT NULL           -- copied from approval_request.preview_digest
  requester                    jsonb NOT NULL          -- copied from approval_request.requester
  approver                     jsonb NOT NULL          -- the approving principal
  issued_at                    timestamptz NOT NULL
  expires_at                   timestamptz NOT NULL    -- grant expiry (per grant_policy.expires_in_seconds at issue time)
  max_uses                     integer NOT NULL CHECK (max_uses >= 1)
  use_count                    integer NOT NULL DEFAULT 0
  session_id                   text NULL               -- required when grant_type='session_bound'
  signature                    text NOT NULL
  FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id)
```

**Key invariants:**
- An `approval_request` is created at the moment a capability raises `approval_required`. The handler returning the failure response is the trigger for persistence.
- `requester` on the request and grant come from the parent invocation's principal; `approver` comes from the authenticated approver bearer token at issuance time.
- The `expired` status is a time-driven transition, not a human decision. It MAY be materialized lazily (set on the next read after `expires_at` passes) or eagerly (by a background sweep). The CHECK constraints permit both: `decided_at` records when the system observed/recorded the expiry; `approver` stays NULL because no principal made the decision. Implementations MAY also choose to leave the row in `status='pending'` past `expires_at` and treat it as expired purely via the `expires_at` field at read time — in that case the `expired` status is never written, and reads compare `expires_at` against `now`. Either approach is acceptable; the atomic primitive `approve_request_and_store_grant` MUST treat both `status != 'pending'` and `expires_at <= now` as non-grantable.
- A `grant`'s `capability`, `scope`, `approved_parameters_digest`, `preview_digest`, and `requester` MUST be copied from the linked `approval_request` at issuance. They are NOT taken from the approver's request body. This prevents an approver from approving for a different capability/scope than the requester previewed.
- Approver-controlled fields are: `grant_type` (must be in `grant_policy.allowed_grant_types`), `expires_at` (≤ `now + grant_policy.expires_in_seconds`), `max_uses` (≤ `grant_policy.max_uses`), `session_id` (required when `grant_type='session_bound'`).
- The `UNIQUE` constraint on `grants.approval_request_id` plus the FK provides defense-in-depth against double-issue (Decision 0.9a covers the primary atomicity mechanism).
- `approval_request_id` is REQUIRED on the grant and is signed into the grant content (Decision 0.7).

**Decision 0.7 — Digest algorithm and grant signing scope.**
SHA-256 over canonical JSON (sorted keys, no whitespace). Same algorithm used for manifest signing in v0.18+. Grant signing covers ALL stored fields except `signature` and `use_count` (the latter is mutable post-issuance and tracked separately). The signed payload explicitly includes `approval_request_id` so a recipient can verify request → grant linkage cryptographically without storage round-trips.

**Decision 0.8 — Composition step output addressing.**
Use JSONPath-style references with `$.input.X`, `$.steps.<step_id>.output.Y`, `$.steps.<step_id>.error.Y`. Limit to single-segment property access — no filters, no wildcards, no recursion. Anything more complex is a composition_invalid_step error.

**Decision 0.9 — Approval grant issuance surface.**
The protocol must define how an `ApprovalGrant` comes into existence after a capability returns `approval_required`. The current v0.22 approval flow is service-internal and out-of-band; v0.23 must make grant issuance explicit.

Adopt **HTTP as the canonical wire surface for grant issuance + helper SPI for non-HTTP approval workflows**:

1. **Canonical wire surface: HTTP only.** `POST /anip/approval_grants` is the canonical wire surface for v0.23. Other transports (gRPC, stdio, REST adapter, GraphQL adapter, MCP adapter) are NOT required to expose grant issuance. Rationale: agents never call grant issuance; the role is approver-side and predominantly uses web tooling (admin UI, dashboards, webhooks). A single canonical surface avoids fragmenting authorization-issuance code across transports while v0.23 stabilizes. Future versions MAY add issuance to additional transports if real demand appears.
   - Request body: `{ approval_request_id, grant_type, session_id?, expires_in_seconds?, max_uses? }`
   - Authentication: bearer token with `approver` capability or scope (defined in §1 below)
   - Response: signed `ApprovalGrant` object
   - Side effect: marks the underlying approval request as `approved` and records the approver principal in audit
   - Failure modes: `approval_request_not_found`, `approval_request_already_decided`, `approver_not_authorized`, `grant_type_not_allowed_by_policy`

2. **Helper SPI:** `service.issue_approval_grant(approval_request_id, grant_type, approver_principal, ...)` (internal API)
   - Used by the HTTP endpoint above
   - **Required for non-HTTP approval workflows.** Service operators who need to issue grants from contexts where HTTP is impractical (Slack bot integrations, queue consumers, CLI tools, on-call escalation systems, custom non-HTTP transports) call the helper directly. The helper is the integration point for any non-HTTP approver path; v0.23 does not standardize those non-HTTP wire surfaces.
   - Centralizes signing, persistence, audit linkage
   - Caller is responsible for authority enforcement (the helper trusts that approver authority has been verified before invocation — see Phase 7.2a "helper SPI vs HTTP handler" note)

3. **Approver authentication.** Approvers authenticate using a normal ANIP delegation token whose scope includes `approver:<capability>` for the capabilities they may approve, OR a service-defined approver scope (e.g. `approver:finance.transfer_funds`). Services MAY further restrict approval rights via principal allowlist; that policy lives in the service, not the protocol.

4. **Audit.** A new audit event `approval_grant_issued` is emitted with `{approval_request_id, grant_id, approver_principal, requester_principal, grant_type, capability, scope}`. This event is the linkage from request to grant.

5. **Discovery.** The ANIP discovery document advertises the approval grant endpoint at `endpoints.approval_grants` (consistent with existing endpoint naming).

**Agent-side ergonomics.** Agents do NOT call this endpoint. After receiving `approval_required`, an agent surfaces the approval boundary to a human/approver via whatever channel the application provides (UI, Slack, email, etc.). The approver — authenticated separately — calls the endpoint and receives the grant. The grant_id is then conveyed back to the agent (out-of-band or via long-poll/callback that's outside ANIP scope) and the agent resubmits the original invocation with `approval_grant: <grant_id>`.

**Decision 0.9a — Atomic approve-and-issue (security-critical).**

Two approvers calling `POST /anip/approval_grants` concurrently for the same `approval_request_id` MUST NOT both succeed. A naive read-then-write flow (load request → check pending → mark approved → insert grant) is race-prone: both calls observe `pending`, both insert grants, both mark approved, leaving the system with two valid grants for one approval request.

The state transition from `pending` → `approved` AND the corresponding grant insertion MUST be atomic. The canonical primitive is a single storage operation `approve_request_and_store_grant(approval_request_id, grant)` implemented as either:

1. **Conditional UPDATE on the approval request** (preferred when the storage backend supports it):
   ```sql
   BEGIN;
   UPDATE approval_requests
     SET status = 'approved', approver = $1, approved_at = $2
     WHERE approval_request_id = $3 AND status = 'pending'
     RETURNING approval_request_id;
   -- If 0 rows returned: ROLLBACK and raise approval_request_already_decided
   INSERT INTO grants (...) VALUES (...);  -- UNIQUE on approval_request_id is the second line of defense
   COMMIT;
   ```
   The conditional `WHERE status = 'pending'` ensures only one transaction wins. The losing transaction sees 0 rows returned and aborts before any grant is inserted.

2. **`SELECT ... FOR UPDATE` with row locking** (also acceptable):
   ```sql
   BEGIN;
   SELECT status FROM approval_requests
     WHERE approval_request_id = $1 FOR UPDATE;
   -- If status != 'pending': ROLLBACK and raise approval_request_already_decided
   UPDATE approval_requests SET status = 'approved', ...;
   INSERT INTO grants (...);
   COMMIT;
   ```

3. **InMemoryStorage** uses a single mutex covering the read-state, mutate-state, insert-grant sequence.

The grants table's `UNIQUE` constraint on `approval_request_id` (Decision 0.6) provides defense-in-depth: even if a flawed implementation slips through review, the second `INSERT` fails with a unique-violation, preventing two grants for one approval.

**Decision implication for Phase 5 storage interface:** the canonical primitive is `approve_request_and_store_grant(approval_request_id, grant)` returning either the stored grant or `APPROVAL_REQUEST_ALREADY_DECIDED` / `APPROVAL_REQUEST_NOT_FOUND`. A naive multi-step API like `mark_approved` + `store_grant` is INSUFFICIENT and MUST NOT be the public storage API.

---

## Phase 1 — Update SPEC.md

**File:** `SPEC.md`

**Changes:**
1. Title: `# ANIP Specification v0.22` → `v0.23`
2. Update version table / changelog at top
3. Add new subsection in §4 (Capability Declaration): **Capability Kind** introducing `atomic`/`composed` with the compatibility default
4. Add new top-level §X **Capability Composition** covering:
   - Composition metadata structure (`steps`, `input_mapping`, `output_mapping`, `empty_result_policy`, `failure_policy`, `audit_policy`, `authority_boundary`)
   - Authority boundary semantics (only `same_service` supported in v0.23)
   - Empty-result policies: `return_success_no_results`, `clarify`, `deny`
   - Failure policies for each child outcome (clarification/denial/approval/error → `propagate` | `fail_parent` | etc.)
   - Audit policy: `record_child_invocations`, `parent_task_lineage`
   - Worked example using `gtm.at_risk_account_enrichment_summary`
5. Extend §6 (Failure Semantics) approval-required section with:
   - `approval_request_id` field
   - `preview_digest` field
   - `requested_parameters_digest` field
   - `grant_policy` object: `allowed_grant_types`, `default_grant_type`, `expires_in_seconds`, `max_uses`
   - The runtime obligation: persist the `ApprovalRequest` to storage before returning the failure to the caller (this is what allows approvers to load the request)
5a. Add new top-level §W **Approval Requests** covering:
   - The `ApprovalRequest` object schema (all fields per Decision 0.6 storage)
   - Lifecycle: created when a capability handler raises `approval_required`, transitions `pending → approved` atomically when a grant is issued, `pending → denied` when an approver rejects (denial flow may be deferred to a future version), `pending → expired` when `expires_at` passes without a decision
   - Persistence requirement: services advertising `anip/0.23` MUST persist approval requests; in-memory-only is acceptable for embedded services but the request MUST be retrievable for the duration of `expires_at`
   - Audit event: `approval_request_created`
6. Add new top-level §Y **Approval Grants** covering:
   - Grant object schema (all fields from Decision 0.1)
   - `one_time` semantics: consumed atomically on first successful execution
   - `session_bound` semantics: reusable in declared session, bounded expiry, finite max_uses
   - Signing & integrity (signature scheme matches existing manifest signing)
   - Continuation invocation: `approval_grant` field on request body
   - Validation order: signature → expiry → uses → capability → scope → digests → session
   - Atomic reservation requirement: validation MUST atomically reserve the grant before side-effect execution (per Decision 0.1 atomicity rule)
   - Rejection error types (Decision 0.5)
7. Add new top-level §Z **Approval Grant Issuance** (per Decision 0.9) covering:
   - The `POST /anip/approval_grants` endpoint contract
   - Request body shape and required/optional fields
   - Approver authentication: bearer token + required scopes
   - Response: signed `ApprovalGrant`
   - Side effects: approval request marked approved, audit event `approval_grant_issued`
   - Failure modes: `approval_request_not_found`, `approval_request_already_decided`, `approver_not_authorized`, `grant_type_not_allowed_by_policy`
   - Discovery advertisement at `endpoints.approval_grants`
   - Compatibility: services advertising `anip/0.23` MUST expose this endpoint
   - Note: out-of-band approval workflows (admin UIs, queue workers) MAY call the runtime helper directly instead of the endpoint; both paths produce identical signed grants
8. Audit linkage requirements: every approval flow audit entry MUST link `invocation_id` → `approval_request_id` → `grant_id` → continuation `invocation_id` → child `invocation_id`s for composed capabilities. The `approval_grant_issued` event provides the request → grant link; the continuation invocation's audit entry provides the grant → execution link.
9. Compatibility note: services declaring `anip/0.22` MUST NOT receive `approval_grant` field; services declaring `anip/0.23` MUST handle missing `approval_grant` (treats as no continuation) and MUST expose the issuance endpoint

**Acceptance:** SPEC.md is concrete enough that an external implementation team could ship v0.23 from it without referencing this plan or any source code.

---

## Phase 2 — Update Schemas

**Files:**
- `schema/anip.schema.json`
- `schema/discovery.schema.json`

**Changes:**
1. Bump `$id` and `version` references from `0.22.0` → `0.23.0`
2. Add `CapabilityKind` enum: `["atomic", "composed"]`
3. Add `EmptyResultPolicy` enum: `["return_success_no_results", "clarify", "deny"]`
4. Add `AuthorityBoundary` enum: `["same_service", "same_package", "external_service"]`
5. Add `FailurePolicyOutcome` enum: `["propagate", "fail_parent", "ignore"]` (or per spec final text)
6. Add `CompositionStep` object:
   - `id` (required, string, unique within composition)
   - `capability` (required, string)
   - `empty_result_source` (optional, boolean, default false) — flags this step's output as the trigger for `empty_result_policy`
   - `empty_result_path` (optional, JSONPath string, scoped to this step's output) — explicit path used to detect emptiness when `empty_result_source: true`. If absent, the runtime uses the first downstream `input_mapping` reference to this step's output
7. Add `Composition` object:
   - `authority_boundary` (required, `AuthorityBoundary` enum)
   - `steps` (required, array of `CompositionStep`, minItems 1)
   - `input_mapping` (required, object: step_id → { param_name → JSONPath ref })
   - `output_mapping` (required, object: parent_field → JSONPath ref) — used when no empty-result branch is taken
   - `empty_result_policy` (optional, `EmptyResultPolicy` enum)
   - `empty_result_output` (optional, object: parent_field → JSONPath ref or literal value) — used when the empty-result branch is taken with `return_success_no_results`. References must resolve only against `$.input.X` and the `empty_result_source` step's output
   - `failure_policy` (required, object: outcome_type → `FailurePolicyOutcome`)
   - `audit_policy` (required, object: `record_child_invocations`, `parent_task_lineage`)
7a. **JSON Schema validation rules** (structural — enforced by `if`/`then`/`else`, `allOf`, `oneOf`, `not`, etc., directly in the schema document):
   - Composition with `empty_result_policy: return_success_no_results` MUST include `empty_result_output` → enforced via `if/then` on `empty_result_policy` value
   - Composition with `empty_result_policy: clarify` or `deny` MUST NOT include `empty_result_output` → enforced via `if/then` with `not` clause. **Presence is a validation error, not silently ignored.**
   - A step with `empty_result_source: true` requires the composition to set `empty_result_policy` → enforced via `if/then` on the step's `empty_result_source` value (with composition-level required field assertion)
   - `kind: composed` requires `composition` to be present → enforced via `if/then`
   - `kind: atomic` permits `composition: null` or absent (does not require it)
   - All scalar field types, enums, required/optional flags, regex constraints

7b. **Runtime semantic validation rules** (cross-reference / referential integrity — enforced at capability registration time, not by JSON Schema):
   - Step IDs MUST be unique within a composition (rejected at registration → `composition_invalid_step` "duplicate step id")
   - At most one step per composition MAY have `empty_result_source: true` (rejected at registration → `composition_invalid_step` "multiple empty_result_source steps")
   - `input_mapping` keys MUST exist as declared step IDs (rejected at registration → `composition_invalid_step` "input_mapping references unknown step")
   - `input_mapping` JSONPath references in `$.steps.<id>.output.*` MUST resolve to declared step IDs that appear earlier in the steps array (forward-reference only) (rejected → `composition_invalid_step` "forward reference")
   - `output_mapping` JSONPath step references MUST resolve to declared step IDs (rejected → `composition_invalid_step` "output_mapping references unknown step")
   - `empty_result_output` JSONPath references MUST be limited to `$.input.*` and `$.steps.<empty_result_source_step>.output.*` — references to other step outputs rejected (→ `composition_invalid_step` "empty_result_output references skipped step")
   - Step `empty_result_path`, when set, MUST be a valid JSONPath against the step's own output type
   - Composed step capabilities MUST be `kind: atomic` (rejected → `composition_invalid_step` "composed step capability") (per Phase 6.1)
   - Step capabilities MUST exist in the same service when `authority_boundary: same_service` (rejected → `composition_unknown_capability`)

The split matters because plain JSON Schema (draft 2020-12) cannot reliably enforce cross-property references, JSONPath validity, or target-resolution checks. Implementations MUST run both layers — schema validation rejects malformed structure; registration-time semantic validation rejects valid-but-incoherent references.
8. Add to `CapabilityDeclaration`:
   - `kind`: `CapabilityKind`, optional, default `atomic`
   - `composition`: `Composition`, optional, required when `kind=composed`
9. Add `GrantType` enum: `["one_time", "session_bound"]`
10. Add `GrantPolicy` object: `allowed_grant_types`, `default_grant_type`, `expires_in_seconds`, `max_uses`
11. Add `ApprovalRequestStatus` enum: `["pending", "approved", "denied", "expired"]`
12. Add `ApprovalRequest` object (mirrors the `approval_requests` storage schema in Decision 0.6): `approval_request_id`, `capability`, `scope`, `requester`, `parent_invocation_id` (optional), `preview`, `preview_digest`, `requested_parameters`, `requested_parameters_digest`, `grant_policy`, `status`, `approver` (optional), `decided_at` (optional), `created_at`, `expires_at`. Conditional-presence rules per the storage CHECK constraints (Decision 0.6), enforced via JSON Schema `if`/`then` on `status`:
    - `status = 'pending'` → `approver` MUST be absent/null AND `decided_at` MUST be absent/null
    - `status IN ('approved', 'denied')` → `approver` MUST be present AND `decided_at` MUST be present (human/principal decision)
    - `status = 'expired'` → `approver` MUST be absent/null AND `decided_at` MUST be present (time-driven transition; no human decided)
13. Add `ApprovalRequiredMetadata`: extend existing approval-required failure response with `approval_request_id`, `preview_digest`, `requested_parameters_digest`, `grant_policy`. The runtime constructs this metadata, persists the underlying `ApprovalRequest`, and returns the metadata on the failure.
14. Add `ApprovalGrant` object: all fields from Decision 0.6 (including required `approval_request_id`)
15. Add `approval_grant: { type: "string" }` to `InvocationRequest`
16. Add new failure types to existing failure type enum (Decision 0.5)
17. Add `IssueApprovalGrantRequest` (body for `POST /anip/approval_grants`): `approval_request_id`, `grant_type`, `session_id`, `expires_in_seconds`, `max_uses`
18. Add `IssueApprovalGrantResponse` (response shape): wraps `ApprovalGrant`
19. Add issuance failure types: `approval_request_not_found`, `approval_request_already_decided`, `approval_request_expired`, `approver_not_authorized`, `grant_type_not_allowed_by_policy`
20. Add `endpoints.approval_grants` field to discovery schema
21. JSON Schema validation: composed declarations must include valid composition (use `if`/`then`/`else` or `oneOf`)

**Acceptance:** schemas validate correctly against composed capability example + approval grant example. Schema descriptions do not contradict SPEC.md.

---

## Phase 3 — Bump Core Protocol Constants

**Files:**
- `packages/python/anip-core/src/anip_core/constants.py`
- `packages/typescript/core/src/constants.ts`
- `packages/go/core/constants.go`
- `packages/java/anip-core/src/main/java/dev/anip/core/Constants.java`
- `packages/csharp/src/Anip.Core/Constants.cs`
- `studio/src/version.ts` (`STUDIO_PROTOCOL_VERSION`)

**Changes:** `anip/0.22` → `anip/0.23` in each file.

**Acceptance:** Run `grep -rn "anip/0.22" packages/ studio/` → returns nothing. Existing protocol version tests pass after they're updated to expect `0.23`.

---

## Phase 4 — Update Core Models in 5 Runtimes

For each runtime, add the following models. The names below use the canonical SPEC.md naming; runtime-idiomatic casing applies.

### 4.1 Python (`packages/python/anip-core/src/anip_core/models.py`)

- `CapabilityKind` (Literal): `"atomic" | "composed"`
- `EmptyResultPolicy` (Literal): `"return_success_no_results" | "clarify" | "deny"`
- `AuthorityBoundary` (Literal): `"same_service" | "same_package" | "external_service"`
- `FailurePolicyOutcome` (Literal): `"propagate" | "fail_parent" | "ignore"` (final values per spec)
- `CompositionStep` with all fields per Phase 2 schema:
  - `id: str`
  - `capability: str`
  - `empty_result_source: bool = False`
  - `empty_result_path: str | None = None`
- `Composition` with all fields per Phase 2 schema:
  - `authority_boundary: AuthorityBoundary`
  - `steps: list[CompositionStep]`
  - `input_mapping: dict[str, dict[str, str]]` (step_id → param → JSONPath)
  - `output_mapping: dict[str, str]`
  - `empty_result_policy: EmptyResultPolicy | None = None`
  - `empty_result_output: dict[str, str] | None = None`
  - `failure_policy: dict[str, FailurePolicyOutcome]`
  - `audit_policy: AuditPolicy` (with `record_child_invocations`, `parent_task_lineage`)
- Extend `CapabilityDeclaration`: `kind: CapabilityKind = "atomic"`, `composition: Composition | None = None`
- `GrantType` (Literal): `"one_time" | "session_bound"`
- `GrantPolicy` with `allowed_grant_types`, `default_grant_type`, `expires_in_seconds`, `max_uses`
- `ApprovalRequestStatus` (Literal): `"pending" | "approved" | "denied" | "expired"`
- `ApprovalRequest` with all fields per the `approval_requests` schema in Decision 0.6: `approval_request_id`, `capability`, `scope`, `requester`, `parent_invocation_id`, `preview`, `preview_digest`, `requested_parameters`, `requested_parameters_digest`, `grant_policy`, `status`, `approver`, `decided_at`, `created_at`, `expires_at`
- Extend approval-required failure model with `approval_request_id`, `preview_digest`, `requested_parameters_digest`, `grant_policy`
- `ApprovalGrant` with all fields per the `grants` schema in Decision 0.6 (including required `approval_request_id`)
- `IssueApprovalGrantRequest` (Phase 2 item 15)
- `IssueApprovalGrantResponse` (Phase 2 item 16)
- Extend `InvokeRequest`: `approval_grant: str | None = None`
- Export new types from `__init__.py`

### 4.2 TypeScript (`packages/typescript/core/src/types.ts` + `models.ts`)

Same shape as Python, using `z.enum()`, `z.object()`, `z.infer<>`. All fields listed in 4.1 (especially `empty_result_source`, `empty_result_path`, `empty_result_output`) MUST be present. Export from index.

### 4.3 Go (`packages/go/core/models.go`)

Same shape as Python using Go structs + string constants for enums. Add JSON tags. All fields listed in 4.1 MUST be present.

### 4.4 Java (`packages/java/anip-core/src/main/java/dev/anip/core/`)

One file per type (existing convention): `CapabilityKind.java`, `Composition.java`, `CompositionStep.java`, `EmptyResultPolicy.java`, `AuthorityBoundary.java`, `FailurePolicyOutcome.java`, `AuditPolicy.java`, `GrantType.java`, `GrantPolicy.java`, `ApprovalRequestStatus.java`, `ApprovalRequest.java`, `ApprovalGrant.java`, `IssueApprovalGrantRequest.java`, `IssueApprovalGrantResponse.java`. `CompositionStep` MUST include `emptyResultSource` and `emptyResultPath`. `Composition` MUST include `emptyResultOutput`. `ApprovalGrant` MUST include `approvalRequestId`. Extend `CapabilityDeclaration.java`, `InvokeRequest.java`, and approval failure class (which gains `approvalRequestId`, `previewDigest`, `requestedParametersDigest`, `grantPolicy`).

### 4.5 C# (`packages/csharp/src/Anip.Core/Models.cs`)

Same shape as Python, using records + enums + System.Text.Json. All fields listed in 4.1 MUST be present.

**Acceptance:** Round-trip serialization tests pass for all new types in all 5 runtimes. Serialized JSON matches schema. A composition fixture with `empty_result_source`, `empty_result_path`, and `empty_result_output` round-trips through every runtime.

---

## Phase 5 — Server Storage for Approval Requests and Grants

### 5.1 Storage interface (canonical, per-runtime)

The storage interface covers two related collections — `approval_requests` and `grants` — and exposes six public operations. Two are atomicity boundaries (security-critical):
- `approve_request_and_store_grant` — atomic approval state transition + grant insertion (per Decision 0.9a)
- `try_reserve_grant` — atomic check-and-increment for grant consumption (per §7.3)

There is no public `mark_approved`, `consume_grant`, or `increment_grant_use` API. The naive split would be race-prone; the atomic primitives are the only public surface for state transitions.

```
# === Approval requests ===

store_approval_request(request: ApprovalRequest) -> void
  // Persist a freshly created approval request. Called by the service runtime
  // when a capability handler returns the approval_required failure
  // (Phase 7.1). Idempotent on approval_request_id when the content is
  // identical; conflicting re-store with the same id is an error.
  //
  // The runtime sets status='pending', created_at=now(), expires_at per
  // service policy or grant_policy.expires_in_seconds; approver and decided_at
  // remain NULL until issuance.

get_approval_request(approval_request_id: str) -> ApprovalRequest | None
  // Read-only fetch. Used for pre-flight validation in Phase 7.2 helper
  // and in the HTTP handler's approver-authority check (Phase 7.2a),
  // and for audit-trail reconstruction.
  //
  // MUST NOT mutate state. Returns the row regardless of status so callers
  // can distinguish pending/approved/denied/expired.

# === Atomic state transition (security-critical) ===

approve_request_and_store_grant(approval_request_id: str, grant: ApprovalGrant) -> ApproveResult
  // Atomic operation per Decision 0.9a. Used by Phase 7.2 helper.
  // SUCCESS: approval request transitioned pending → approved AND grant stored.
  //          Returns the stored grant.
  // FAILURE: returns one of:
  //   {APPROVAL_REQUEST_NOT_FOUND, APPROVAL_REQUEST_ALREADY_DECIDED,
  //    APPROVAL_REQUEST_EXPIRED}
  //
  // PostgreSQL implementation: single transaction with conditional UPDATE
  // (status='pending' AND expires_at > now() guard) followed by INSERT INTO
  // grants. 0 rows returned from UPDATE → ROLLBACK and return ALREADY_DECIDED
  // or EXPIRED depending on which condition failed (re-read to disambiguate).
  // Transaction guarantees both writes commit together or neither does.
  //
  // InMemoryStorage implementation: single mutex covering read-check-write of
  // both approval_requests and grants dicts.
  //
  // Defense-in-depth: grants.approval_request_id has a UNIQUE constraint and
  // a FK to approval_requests. Even if an implementation bug bypasses the
  // conditional UPDATE, the INSERT fails with unique-violation or FK error.

# === Grants ===

store_grant(grant: ApprovalGrant) -> void
  // Internal/test-only. NOT used by the issuance helper. The issuance helper
  // MUST use approve_request_and_store_grant. Exposed only for storage
  // unit tests that don't exercise the approval-request flow.

get_grant(grant_id: str) -> ApprovalGrant | None
  // Read-only fetch. Used for read-side validation in §7.3 Phase A.
  // MUST NOT mutate use_count.

try_reserve_grant(grant_id: str, now: datetime) -> ReserveResult
  // Atomic check-and-increment. Used for §7.3 Phase B.
  // SUCCESS: increments use_count by 1, returns new state
  // FAILURE: returns one of {GRANT_NOT_FOUND, GRANT_EXPIRED, GRANT_CONSUMED}
  //
  // PostgreSQL implementation:
  //   UPDATE grants
  //   SET use_count = use_count + 1
  //   WHERE grant_id = $1
  //     AND use_count < max_uses
  //     AND expires_at > $2
  //   RETURNING use_count, max_uses, expires_at
  //
  // 0 rows returned → re-fetch via get_grant to disambiguate
  // GRANT_EXPIRED (expires_at <= now) vs GRANT_CONSUMED (use_count >= max_uses)
  // vs GRANT_NOT_FOUND (no row exists).
  //
  // InMemoryStorage implementation:
  //   Acquire mutex; check expiry/uses; increment if valid; release.
```

**Lifecycle summary:**
1. Capability handler raises `approval_required` → service runtime calls `store_approval_request` (Phase 7.1)
2. Approver POSTs to `/anip/approval_grants` → handler calls `get_approval_request` for pre-flight validation (Phase 7.2a)
3. Helper builds + signs the grant → calls `approve_request_and_store_grant` (Phase 7.2 step 6 — the atomic boundary)
4. Agent resubmits invocation with `approval_grant: <grant_id>` → service runtime calls `get_grant` then `try_reserve_grant` (Phase 7.3)
5. Audit reconstruction: any reader can call `get_approval_request` and `get_grant` to walk the linkage

### 5.2 Python (`packages/python/anip-server/`)

- Add `ApprovalRequest` model (mirrors the `approval_requests` schema in Decision 0.6 — fields: `approval_request_id`, `capability`, `scope`, `requester`, `parent_invocation_id`, `preview`, `preview_digest`, `requested_parameters`, `requested_parameters_digest`, `grant_policy`, `status`, `approver`, `decided_at`, `created_at`, `expires_at`)
- Add `ApprovalGrant` model and the six storage interface methods above
- Implement `store_approval_request`, `get_approval_request`, `approve_request_and_store_grant`, `store_grant`, `get_grant`, `try_reserve_grant` in `InMemoryStorage` (two dicts + `threading.Lock` for atomicity across both)
- Implement same in `PostgresStorage` with new `approval_requests` and `grants` tables (Decision 0.6) — write migration creating BOTH tables alongside existing schema, with the FK from grants to approval_requests
- `approve_request_and_store_grant` MUST be a single transaction with conditional `UPDATE approval_requests ... WHERE status='pending' AND expires_at > now() RETURNING` followed by `INSERT INTO grants`. The grants table's `UNIQUE (approval_request_id)` constraint and FK are the second line of defense
- `try_reserve_grant` MUST use the SQL `UPDATE ... WHERE ... RETURNING` pattern shown above; do not implement as separate SELECT + UPDATE

### 5.3 TypeScript (`packages/typescript/server/`)

Same interface — extend storage interface, implement in InMemoryStorage and PostgresStorage (better-sqlite3 also if it's still supported; check current parity).

### 5.4 Go, Java, C#

Each runtime's server package: same storage interface extension. Match prior parity for which storage backends each runtime supports.

**Acceptance:**
- Grant storage CRUD tests pass per runtime
- Concurrent `try_reserve_grant` test: N (≥10) parallel calls against a one-time grant; exactly 1 returns SUCCESS, N-1 return GRANT_CONSUMED
- **Concurrent `approve_request_and_store_grant` test:** N (≥10) parallel calls for the same `approval_request_id` (different grant_ids); exactly 1 returns SUCCESS with a stored grant, N-1 return APPROVAL_REQUEST_ALREADY_DECIDED. Verify post-condition: exactly one row in `grants` with that `approval_request_id`, exactly one approval_request with `status='approved'`.
- Defense-in-depth test: directly attempt to insert a second grant with the same `approval_request_id`; storage rejects with unique-violation
- Expired grant returns GRANT_EXPIRED, missing grant returns GRANT_NOT_FOUND, exhausted session-bound grant returns GRANT_CONSUMED
- PostgreSQL migration is idempotent

---

## Phase 6 — Service Runtime: Composition Validation & Execution

### 6.1 Validation at registration time

In each runtime's service registration path (`service.py` / `service.ts` / `service.go` / `ANIPService.java` / `AnipService.cs`):

- If declaration has `kind=composed`:
  - Reject if `composition` is missing → `composition_invalid_step` at registration
  - Reject if any step's `capability` is unknown to this service (when `authority_boundary=same_service`) → `composition_unknown_capability`
  - Reject if `authority_boundary` is `same_package` or `external_service` → `composition_unsupported_authority_boundary`
  - Reject if step IDs are not unique within the composition → `composition_invalid_step` (duplicate id)
  - Reject if any step references its own parent capability (self-reference) → `composition_invalid_step` (self-reference)
  - **Composed-calling-composed restriction (v0.23):** composed capabilities MAY only invoke `kind=atomic` steps. Calling another composed capability is rejected at registration → `composition_invalid_step` (composed step capability). This eliminates cycle risk entirely for v0.23 and defers transitive composition to a follow-up.
  - Validate `input_mapping` and `output_mapping` JSONPath references resolve against declared step IDs (forward references only — a step may only reference earlier steps' outputs)

**Rationale for composed-calling-composed restriction:** Allowing composed-calling-composed introduces cycle detection complexity (DAG validation across the full transitive graph) and recursion depth concerns. For v0.23, restricting to single-level composition keeps the protocol bounded and easy to reason about. Multi-level composition can be added in a future version with explicit cycle detection if a real use case appears.

### 6.2 Composition execution

When a composed capability is invoked:
- Resolve `input_mapping` against parent invocation parameters
- Execute steps in declared order (no parallelism in v0.23)
- For each step, write child audit entry linked to parent `invocation_id` and `task_id`
- On child clarification/denial/approval-required: apply `failure_policy` (propagate by default → wrap as parent failure)
- On child error: apply `failure_policy` (default `fail_parent`)
- Empty-result detection: see §6.3 below
- After all steps complete (or empty-result policy applied): resolve `output_mapping` to build parent response

### 6.3 Empty-result trigger (normative)

A "selection step" is not implicit. Each `CompositionStep` MAY declare an explicit boolean field `empty_result_source: true`. When a step with `empty_result_source: true` returns a successful result whose primary output array (or scalar) is empty/null, the composition's `empty_result_policy` applies:
- `return_success_no_results` → skip subsequent steps that depend on this step's output, build the parent response from the dedicated `empty_result_output` mapping (see below), return success
- `clarify` → return parent failure `composition_empty_result_clarification_required`
- `deny` → return parent failure `composition_empty_result_denied`

If no step has `empty_result_source: true`, the policy is never triggered — empty intermediate results are passed through normally.

The "primary output" of a step is determined by its first reference in `input_mapping` for downstream steps, OR by an explicit per-step `empty_result_path` JSONPath if declared. Schema validation rejects `empty_result_source: true` without a resolvable path.

### 6.4 Empty-result output mapping (normative)

When `empty_result_policy: return_success_no_results` is in effect AND any step has `empty_result_source: true`, the composition MUST declare a dedicated `empty_result_output` mapping that defines the parent response shape for the empty-result case. This mapping:

- MUST resolve only against `$.input.X` (parent invocation parameters) and `$.steps.<source_step>.output.Y` (the empty source step's output, which by definition exists but is empty)
- MUST NOT reference outputs of any step skipped due to the empty source
- MUST produce a response shape that matches the parent capability's declared `output` schema (e.g. an empty array for list outputs, null for scalar outputs)

**Schema enforcement:** Schema validation rejects compositions where:
- `empty_result_policy: return_success_no_results` is set without an `empty_result_output` mapping
- `empty_result_output` references step outputs other than the `empty_result_source` step

**Runtime enforcement:** When the empty-result branch is taken, runtimes use `empty_result_output` exclusively to build the response. The normal `output_mapping` is NOT used. This makes the empty-result response shape fully deterministic and identical across runtimes.

Example:
```yaml
composition:
  steps:
    - id: select_at_risk_accounts
      capability: gtm.account_risk_summary
      empty_result_source: true
    - id: enrich_accounts
      capability: gtm.account_enrichment
  output_mapping:
    account_count: $.steps.enrich_accounts.output.account_count
    accounts: $.steps.enrich_accounts.output.accounts
  empty_result_policy: return_success_no_results
  empty_result_output:
    account_count: 0
    accounts: []
```

**Acceptance:** Per-runtime tests cover happy path, each empty-result policy branch (with explicit `empty_result_source` and `empty_result_output`), each failure-policy mode, registration rejection of duplicate step IDs, registration rejection of self-reference, registration rejection of composed-step references, registration rejection of `return_success_no_results` without `empty_result_output`, registration rejection of `empty_result_output` referencing skipped step outputs.

---

## Phase 7 — Service Runtime: Approval Grant Validation & Issuance

### 7.1 Approval-required response (creates the approval request)

The `approval_required` failure is the trigger that creates and persists the `ApprovalRequest`. The capability handler raises `approval_required` with a preview and a `grant_policy`; the service runtime is responsible for materializing the request into storage before returning the failure to the caller. This guarantees that by the time an agent surfaces "approval required" to a human, the corresponding request exists and can be loaded by an approver.

When a capability handler raises `approval_required`:
1. Compute `preview_digest` = SHA-256 of canonical JSON of the handler-supplied preview
2. Compute `requested_parameters_digest` = SHA-256 of canonical JSON of the original invocation parameters
3. Generate a fresh `approval_request_id` (UUID or service-defined collision-resistant ID)
4. Resolve the effective `grant_policy`:
   - If the capability declaration includes a `grant_policy`, use it
   - Otherwise use the service-level default (configured at service startup)
   - If neither exists, the capability MUST NOT be allowed to raise `approval_required` — registration-time validation (Phase 6.1) rejects this
5. Resolve the request `expires_at`:
   - Default: `now + grant_policy.expires_in_seconds`
   - Service MAY apply a stricter cap; MUST NOT exceed the policy value
6. Build the `ApprovalRequest`:
   - `approval_request_id`, `capability` (= invoked capability name), `scope` (= the scopes the action requires)
   - `requester` = current invocation's authenticated principal
   - `parent_invocation_id` = current invocation's ID (audit linkage)
   - `preview` = handler-supplied preview content; `preview_digest` = computed digest
   - `requested_parameters` = original invocation parameters; `requested_parameters_digest` = computed digest
   - `grant_policy` = effective policy from step 4
   - `status = "pending"`, `approver = null`, `decided_at = null`
   - `created_at = now`, `expires_at` per step 5
7. Call `storage.store_approval_request(request)` — persists the row with `status='pending'`
8. Return the `approval_required` failure to the caller with `ApprovalRequiredMetadata`: `approval_request_id`, `preview_digest`, `requested_parameters_digest`, `grant_policy`

**Audit:** A new audit event `approval_request_created` is emitted with `{approval_request_id, parent_invocation_id, capability, requester_principal, expires_at}`.

**Implementation note:** if `store_approval_request` fails (e.g. storage unavailable), the runtime MUST return a generic `service_unavailable` failure — never return `approval_required` to a caller without the underlying request being persisted. This invariant is what allows approvers to safely look up the request afterward.

### 7.2 Grant issuance helper (SPI)

Add per-runtime helper:
- Python: `service.issue_approval_grant(approval_request_id, grant_type, approver_principal, ...) -> ApprovalGrant`
- TypeScript: `service.issueApprovalGrant({...})`
- Go: `service.IssueApprovalGrant(opts)`
- Java: `service.issueApprovalGrant(opts)`
- C#: `service.IssueApprovalGrant(opts)`

Helper (note: the read-side checks below are advisory pre-flight; the atomic primitive at step 7 is the security boundary that prevents the race described in Decision 0.9a):

1. Calls `storage.get_approval_request(approval_request_id)`. If missing → `approval_request_not_found`
2. Validates the request is still pending. If already decided → `approval_request_already_decided` (advisory; final verdict comes from step 7)
3. Validates the request has not expired (`request.expires_at > now`). If expired → `approval_request_expired`
4. Validates `grant_type` is in the request's `grant_policy.allowed_grant_types`. If not → `grant_type_not_allowed_by_policy`
5. Validates approver-controlled fields against the request's `grant_policy`:
   - `expires_at` (computed) ≤ `now + grant_policy.expires_in_seconds`
   - `max_uses` ≤ `grant_policy.max_uses`
   - `session_id` is present iff `grant_type='session_bound'`
   - On violation → `grant_type_not_allowed_by_policy` with detail
6. Builds the `ApprovalGrant`. **Capability/scope/digests/requester are copied from the loaded approval request, NOT from the helper's caller arguments** (this prevents an approver from approving for a different capability than the requester previewed):
   - `grant_id` = freshly generated
   - `approval_request_id` = request.approval_request_id
   - `capability` = request.capability
   - `scope` = request.scope
   - `approved_parameters_digest` = request.requested_parameters_digest
   - `preview_digest` = request.preview_digest
   - `requester` = request.requester
   - `approver` = the authenticated approver principal passed in by the caller
   - `grant_type`, `expires_at`, `max_uses`, `session_id` per validated args
   - `use_count = 0`
   - `issued_at = now`
7. Signs the grant using the service's signing key over all stored fields except `signature` and `use_count` (per Decision 0.7)
8. Calls `storage.approve_request_and_store_grant(approval_request_id, grant)` — the atomic primitive (per Decision 0.9a). This is the race-safe state transition. If it returns `APPROVAL_REQUEST_ALREADY_DECIDED` → the helper raises `approval_request_already_decided` (a concurrent approver won; the current grant object is discarded — it was never persisted). If `APPROVAL_REQUEST_NOT_FOUND` → raises `approval_request_not_found`. If `APPROVAL_REQUEST_EXPIRED` → raises `approval_request_expired`.
9. Writes audit event `approval_grant_issued` with `{approval_request_id, grant_id, approver_principal, requester_principal, grant_type, capability, scope}`
10. Returns the signed grant

**Important:** Steps 1–5 are pre-flight validation that allows the helper to reject obviously-bad requests cheaply (don't bother building/signing a grant when the request is already decided). They do NOT replace the atomic primitive at step 8, which is the only race-safe arbiter. Implementations MUST NOT skip step 8 just because steps 1–5 passed — those reads happen before any state mutation and are racy by themselves.

### 7.2a Grant issuance endpoint (HTTP)

Add `POST /anip/approval_grants` handler in each runtime's service runtime. Validation order matters: approver authority is per-capability (e.g. `approver:finance.transfer_funds`), so the handler must know which capability is being approved before it can decide whether the caller is an approver for it. This means parse + load the approval request first, then check authority against the loaded request's `capability`.

1. Authenticate the caller's bearer token (transport-level auth). Reject if missing/invalid → existing `unauthorized` response. Extract the principal but do NOT yet enforce approver scope.
2. Parse request body: `IssueApprovalGrantRequest`. Reject malformed body → `invalid_parameters`
3. Call `storage.get_approval_request(approval_request_id)`. If missing → `approval_request_not_found`
4. Validate the request is still pending (not already approved/denied). If decided → `approval_request_already_decided`. Validate not expired. If expired → `approval_request_expired`.
5. **Now** validate the caller has approver authority for the loaded request's capability: token scope contains `approver:<request.capability>` OR service-defined approver scope covering that capability; service MAY further check principal allowlist via auth hook. If not → `approver_not_authorized`
6. Validate `grant_type` is in the loaded request's `grant_policy.allowed_grant_types`. If not → `grant_type_not_allowed_by_policy`
7. Call `service.issue_approval_grant(...)` with the loaded request + the parsed approver-controlled args (`grant_type`, `expires_in_seconds`, `max_uses`, `session_id`) + authenticated approver principal. The helper handles capability/scope/digest copy from the request, signing, atomic persistence via `approve_request_and_store_grant`, and the `approval_grant_issued` audit event
8. Return `IssueApprovalGrantResponse` (200) or structured failure (4xx)

**Note on helper SPI vs HTTP handler:** The `service.issue_approval_grant()` helper (Phase 7.2) trusts that authority has already been checked by the caller. The HTTP handler above performs the per-capability authority check. Out-of-band callers (admin UIs, queue workers) MUST perform their own equivalent authority enforcement before calling the helper — the helper is the central code path, but it is NOT the security boundary. Document this clearly in helper docstrings.

The HTTP route lives at the same level as `/anip/tokens` and `/anip/audit`. The discovery document advertises it at `endpoints.approval_grants`.

**Out-of-band issuance:** Service-local approval workflows (admin UIs, queue workers, on-call escalation tools) call `service.issue_approval_grant()` directly, bypassing the HTTP endpoint. Both paths produce identical signed grants and identical audit events. Both paths are responsible for authority enforcement.

### 7.3 Continuation validation

**Critical: grants MUST be atomically reserved BEFORE the capability handler executes.** Two concurrent requests with the same grant must not both pass validation. Reservation is the security boundary; side-effect execution is post-reservation. If the handler subsequently fails, the grant remains consumed — the caller must request a fresh approval. This is the correct semantic for one-time authorization on sensitive actions: better to "waste" a grant than to allow double-execution.

When `invoke()` receives a request with `approval_grant`:

**Phase A — Read-side validation (no state change):**
1. Fetch grant from storage by `grant_id`. Missing → `grant_not_found`
2. Verify signature/integrity. Invalid → `grant_not_found` (don't leak existence)
3. Check `expires_at` vs now. Expired → `grant_expired`
4. Compare `capability` to invoked capability. Mismatch → `grant_capability_mismatch`
5. Validate scope per **scope matching rule** (see 7.4 below). Mismatch → `grant_scope_mismatch`
6. Compute current request `parameters_digest`, compare to grant's `approved_parameters_digest`. Mismatch → `grant_param_drift`
7. If `grant_type=session_bound`: verify session_id from token matches grant's `session_id`. Mismatch → `grant_session_invalid`

**Phase B — Atomic reservation (state change before side effects):**
8. Call `storage.try_reserve_grant(grant_id, now)` (defined in Phase 5.1). The storage primitive performs the atomic check-and-increment in a single operation:
   - PostgreSQL: `UPDATE ... SET use_count = use_count + 1 WHERE grant_id = $1 AND use_count < max_uses AND expires_at > $2 RETURNING ...` (full SQL in Phase 5.1)
   - InMemoryStorage: mutex-protected check-and-increment
   - One-time grants (`max_uses=1`) become unreservable after the single successful call
   - Session-bound grants increment per use up to `max_uses`
9. Map `ReserveResult` to the runtime failure type:
   - `GRANT_CONSUMED` → return `grant_consumed`
   - `GRANT_EXPIRED` → return `grant_expired`
   - `GRANT_NOT_FOUND` → return `grant_not_found`

**Phase C — Side-effect execution:**
10. Execute capability handler
11. Write audit entry linking `invocation_id`, `approval_request_id`, `grant_id`, regardless of handler success/failure

**Failure handling:** If the handler raises, the grant stays consumed. The audit entry records the failure. The caller must request a new approval to retry. This is intentional and matches the security model: a successful reservation means "this grant has been spent on an attempt."

### 7.4 Grant scope matching rule (normative)

The grant's `scope` represents the bound authority approved for this specific action. The invocation token's scope MUST be a superset of the grant's scope:

```
forall s in grant.scope: s in invocation_token.scope
```

This means:
- Grant scope is exact-match ⊆ token scope
- Token MAY carry additional scopes the grant doesn't reference (the grant binds only the subset it approved)
- Grant scope MAY NOT exceed token scope (cannot use a grant to elevate beyond the caller's delegation)

Rejection: `grant_scope_mismatch` is returned when any element of `grant.scope` is absent from `invocation_token.scope`.

**Acceptance:** Per-runtime tests cover each rejection path, successful continuation, and a concurrent-reservation test that fires N parallel requests with the same one-time grant and asserts exactly one succeeds, N-1 receive `grant_consumed`. Scope subset/superset/exact-match cases all covered.

---

## Phase 7.5 — Transport Adapter Coverage

Adding `approval_grant` to the core `InvocationRequest` model is necessary but not sufficient. Each transport that translates between wire format and `InvocationRequest` MUST be updated so the field flows end-to-end. Same applies to composed-capability response shapes (composition adds no new transport-level fields, but tests must confirm parity).

**Scope split — invocation vs grant issuance:**
- **Invocation continuation** (carrying `approval_grant` on an invoke request): ALL transports must support this so an agent can resubmit on any transport it uses to invoke
- **Grant issuance** (`POST /anip/approval_grants`): HTTP only is the canonical wire surface for v0.23 (per Decision 0.9). Other transports do NOT need to expose a grant-issuance method. Non-HTTP approver workflows call the helper SPI (`service.issue_approval_grant`) directly.

Each subsection below specifies which scope applies.

### 7.5.1 HTTP route parsing

Per-runtime HTTP framework bindings must:
1. Accept `approval_grant` in the JSON request body for `POST /anip/invoke/{capability}` and pass it to `service.invoke()`
2. Expose the new `POST /anip/approval_grants` endpoint with proper auth + body parsing (per Phase 7.2a)

Bindings to update:
- Python: `anip-fastapi`, `anip-flask` (if present)
- TypeScript: `@anip-dev/hono`, `@anip-dev/express`, `@anip-dev/fastify`
- Go: `httpapi`, `restapi`
- Java: `anip-spring-boot`, `anip-quarkus`
- C#: `Anip.AspNetCore`

For each: confirm the request DTO includes the new field, the new endpoint route exists, and serialization tests cover present/absent cases.

### 7.5.2 gRPC (invocation only)

If the gRPC transport (`anip-grpc` Python, any other runtime parity) is in scope:
- Update `.proto` files: add `approval_grant` to invoke request message
- Add `Composition`, `CompositionStep`, `ApprovalGrant`, `GrantPolicy`, etc. proto messages (needed for serialization parity even though grant issuance over gRPC is not required)
- Regenerate generated client/server stubs in all languages that consume the proto
- Update gRPC service handlers to translate the new fields on invoke

**Grant issuance over gRPC is explicitly NOT required for v0.23.** Approvers using gRPC-only environments call the helper SPI directly. If gRPC is not currently shipping for v0.22, defer to a follow-up but document this as a gap.

### 7.5.3 stdio (invocation only)

The stdio transport wraps invocations in JSON-RPC. Confirm:
- The stdio request handler accepts `approval_grant` in the invoke method's params
- Composition responses round-trip without truncation
- Per-runtime: `anip-stdio` (Python), `@anip-dev/stdio` (TypeScript), Go/Java/C# equivalents

**Grant issuance over stdio is explicitly NOT required for v0.23.** stdio is primarily an agent-side transport; approvers do not interact via stdio.

### 7.5.4 REST adapter (invocation only)

The REST adapter translates ANIP semantics to traditional REST endpoints. For v0.23:
- Decide how `approval_grant` is carried: query param, body field, or header (recommend body field for POST/PUT, header `X-ANIP-Approval-Grant` for GET-translated reads)
- Composed capabilities expose the same single REST endpoint as atomic — internal composition is invisible to the REST consumer
- Document this in the REST adapter README

**Grant issuance via the REST adapter is explicitly NOT required for v0.23.** The canonical HTTP endpoint `POST /anip/approval_grants` already exists alongside the REST adapter on the same service; REST consumers can call it directly without translation.

### 7.5.5 GraphQL adapter (invocation only)

The GraphQL adapter translates ANIP capabilities to GraphQL fields. For v0.23:
- Add `approvalGrant: String` argument to mutation fields
- Composed capabilities translate to single GraphQL fields with declared composition invisible to the consumer
- Update GraphQL schema generation to emit the new argument

**Grant issuance via GraphQL is explicitly NOT required for v0.23.** GraphQL consumers needing an approver UI use the canonical HTTP endpoint.

### 7.5.6 MCP adapter (invocation only)

The MCP (Model Context Protocol) adapter exposes capabilities as MCP tools. For v0.23:
- Add `approval_grant` to tool input schema
- Composition is invisible to MCP consumers (tool surface stays bounded)

**Grant issuance via MCP is explicitly NOT required for v0.23.** MCP is an agent-side tool-consumption protocol; approvers do not use MCP.

**Acceptance:** Per-transport integration test exercises an approval-grant *continuation* flow end-to-end through that transport (i.e. invoke with `approval_grant` field). Grant issuance is exercised only over HTTP. All transports support the v0.23 invocation surface or have explicit documented gaps in the dogfooding findings doc.

---

## Phase 8 — Tests

### 8.1 Per-runtime unit tests

Each runtime adds tests for:

**Composition declaration & registration:**
- Atomic capability declaration round-trip (with explicit `kind=atomic`)
- Composed capability declaration round-trip
- Composed declaration missing `composition` → registration error
- Composed declaration with unknown step capability → registration error
- Composed declaration with `same_package` boundary → registration error
- Composed declaration with duplicate step IDs → registration error
- Composed declaration with self-reference → registration error
- Composed declaration referencing another `kind=composed` step → registration error
- Composed declaration with `empty_result_source: true` but no resolvable empty path → registration error

**Composition execution:**
- Happy path
- `empty_result_policy=return_success_no_results` (with explicit `empty_result_source`) returns 200 with empty array
- `empty_result_policy=clarify` returns `composition_empty_result_clarification_required`
- `empty_result_policy=deny` returns `composition_empty_result_denied`
- Empty intermediate result without `empty_result_source` flag passes through normally
- Child clarification propagates when failure_policy=propagate
- Child denial propagates when failure_policy=propagate
- Child error fails parent

**Approval requests — creation and persistence:**
- Capability handler raises `approval_required` → corresponding row exists in `approval_requests` with `status='pending'` before the failure response is returned to the caller
- Approval-required response includes `approval_request_id`, `preview_digest`, `requested_parameters_digest`, `grant_policy`
- `approval_request_created` audit event emitted
- Storage failure during `store_approval_request` → caller receives `service_unavailable`, NOT `approval_required` (no orphaned approval flow)
- Capability with no `grant_policy` and no service-level default → registration error (cannot raise approval_required)
- Approval request expiry: a pending request whose `expires_at` is past → `approve_request_and_store_grant` returns `APPROVAL_REQUEST_EXPIRED`; pre-flight helper check returns `approval_request_expired`
- Capability/scope/digest fields on issued grant are copied from the loaded approval request, NOT from the helper caller's args (test by calling helper with mismatched fields and verifying the stored grant matches the request, not the caller args)

**Approval grants — per-step rejection:**
- One-time grant: succeeds once, second use → `grant_consumed`
- Session-bound grant: succeeds in-session, fails out-of-session → `grant_session_invalid`
- Parameter drift: modified params after approval → `grant_param_drift`
- Capability mismatch: grant for X used on Y → `grant_capability_mismatch`
- Scope mismatch: grant scope not subset of token scope → `grant_scope_mismatch`
- Scope subset valid: token has more scopes than grant → success
- Scope superset invalid: grant requires scope not in token → `grant_scope_mismatch`
- Expired grant → `grant_expired`
- Missing/tampered grant → `grant_not_found`

**Approval grants — atomicity (security-critical):**
- **Concurrent reservation test:** fire N (≥10) parallel invocations with the same one-time grant. Assert exactly 1 succeeds, N-1 receive `grant_consumed`. Use real threading/async, not sequential calls.
- **Concurrent issuance test:** fire N (≥10) parallel `POST /anip/approval_grants` requests for the same `approval_request_id` from N approvers (each authenticated independently). Assert exactly 1 returns 200 with a signed grant, N-1 return `approval_request_already_decided`. Verify post-state: exactly one row in `grants` for that `approval_request_id`; exactly one row in `approval_requests` with `status='approved'`.
- **Helper-direct concurrent issuance test:** same as above but bypassing HTTP, calling `service.issue_approval_grant()` directly from N threads. Same invariants must hold.
- **Defense-in-depth test:** directly attempt to insert a second grant row with a duplicate `approval_request_id` via raw storage call; insertion fails with unique-violation error.
- **Signed approval_request_id test:** verify the grant's signature covers `approval_request_id` — tamper with `approval_request_id` in a stored grant and confirm signature validation rejects it.
- Handler failure after reservation: grant is consumed even though side-effect failed. Subsequent retry with same grant → `grant_consumed`.
- Session-bound grant with `max_uses=3`: 3 successful uses, 4th → `grant_consumed`.

**Audit linkage:**
- Audit entry exists linking request → grant → continuation
- Composed capability: audit entries link parent → children with shared `task_id`

### 8.2 Conformance tests

Add to `conformance/`:
- New conformance suite `test_composition.py` exercising a composed capability declaration + execution
- New conformance suite `test_approval_grants.py` exercising the full approval flow end-to-end

These run against all 5 runtimes via the existing conformance harness.

### 8.3 Schema validation tests

Add to schema test suites:
- Valid atomic declaration passes
- Valid composed declaration passes
- Composed missing `composition` fails
- Approval grant object validates
- Approval-required response with all v0.23 fields validates

**Acceptance:** All tests pass on all 5 runtimes. Conformance suite green.

---

## Phase 9 — Examples

### 9.1 Composed capability example

Add to one showcase (recommend `examples/showcase/travel/`):
- New composed capability `book_with_seat_selection` composing `search_flights` → `select_seat` → `book_flight`
- OR add `gtm.at_risk_account_enrichment_summary` to the GTM showcase if that's already wired

Show full composition declaration with all fields used realistically.

### 9.2 Approval grant example

Add to `examples/showcase/finance/`:
- Modify `transfer_funds` to require approval when `amount > $10,000`
- Demonstrate `one_time` grant flow: invoke → `approval_required` → approve → continuation with grant → success
- Demonstrate `session_bound` grant for batch transfers within a session

### 9.3 Agent demo updates

The agent and the approver are two distinct roles with two distinct client surfaces. Helpers are split accordingly.

**Agent-side helpers (`examples/agent/anip_client.py`):**
- Add `invoke_with_approval_grant(capability, parameters, grant_id)` — wraps a normal invoke that includes `approval_grant: <grant_id>` in the request body
- Agent does NOT call any grant-issuance API; it only consumes grants delivered out-of-band

**Approver-side helpers (new file: `examples/agent/approver_client.py`):**
- Add `issue_approval_grant(approval_request_id, grant_type, expires_in_seconds=None, max_uses=None, session_id=None)` — calls `POST /anip/approval_grants` with the approver's bearer token (per Decision 0.9)
- Authenticates as a separate principal with approver scope
- Returns the signed grant; the demo passes the `grant_id` back to the agent via a simple in-memory queue or stdin prompt

Update `examples/agent/agent_loop.py`:
- Handle `approval_required` failure → emit a "needs approval" event → wait for the approver demo to issue a grant (via the simple coordination mechanism above) → resubmit with `approval_grant` field
- Handle composed capability response (no special handling needed — agent sees one bounded result)

Add `examples/agent/approver_loop.py`:
- Polls or listens for pending approval requests
- For demo purposes: auto-approves matching requests, calls `issue_approval_grant`, returns grant to the coordination channel
- Demonstrates the approver-side flow without requiring a real approval UI

**Acceptance:** Examples runnable via existing showcase Docker setup. README documents the agent + approver split flows.

---

## Phase 10 — Dogfooding

Per the design doc §"Dogfooding Success Criteria":

1. **Composed capability end-to-end**
   - Run agent demo against the new composed capability
   - Verify agent invokes it as a single business action (no manual stitching)
   - Verify audit shows parent + child invocations linked
   - Verify empty-result policy works for the no-data case

2. **Approval grant end-to-end**
   - Run finance showcase, trigger high-value transfer
   - Receive `approval_required` with full v0.23 metadata
   - Issue grant via helper, persist
   - Submit continuation with `approval_grant` field
   - Verify success + grant consumption
   - Verify reuse fails with `grant_consumed`
   - Verify param drift fails with `grant_param_drift`

3. **Cross-runtime smoke**
   - Run conformance suite against all 5 runtimes' showcase implementations
   - All v0.23 conformance tests pass

4. **Write findings doc**
   - `docs/plans/2026-04-25-v023-dogfooding-findings.md`
   - Document remaining glue, follow-up items, anything that surprised us

**Acceptance:** Dogfooding doc written, all flows demonstrated successfully.

---

## Branch & PR Strategy

**One branch:** `feat/anip-v023-composition-and-grants`

**Critical constraint: `PROTOCOL_VERSION` constants must NOT be bumped to `anip/0.23` until composition execution and approval grant validation are actually implemented.** A service advertising `anip/0.23` MUST honor the v0.23 contract. Bumping the constant before behavior lands creates a window where services claim v0.23 support without honoring it.

**Recommended split (two PRs):**

**PR 1 — Spec + schema + models (no advertised protocol bump):**
- Phase 1: SPEC.md
- Phase 2: schemas
- Phase 4: core models (struct/class definitions, serialization)
- Phase 8.3: schema validation tests
- **Excludes Phase 3.** Constants stay at `anip/0.22`. Models for v0.23-only fields (`composition`, `approval_grant`, etc.) exist but are unreachable through service runtime code paths.

**PR 2 — Behavior + advertised version bump:**
- Phase 3: bump `PROTOCOL_VERSION` constants to `anip/0.23` (atomic with behavior)
- Phase 5: grant storage
- Phase 6: composition validation & execution
- Phase 7: approval grant validation & issuance helpers
- Phase 8.1, 8.2: per-runtime unit tests + conformance
- Phase 9: examples
- Phase 10: dogfooding

This split matches v0.20–v0.22 PR cadence and ensures `anip/0.23` advertising is atomic with v0.23 behavior support.

**Single-PR alternative:** If review burden permits, ship all phases in one PR. The constraint stays the same — version bump must be in the same commit as behavior.

---

## Out of Scope (Per Design Doc)

- Generic workflow engine (loops, branches, sagas, BPMN)
- Agent-side planning language
- Remote registry implementation or receipt signing
- Generator architecture work
- Studio project revisioning
- New service-to-service transport
- Replacing v0.22 delegated token issuance
- Broad cryptographic key management redesign
- Loops, parallel step execution, or arbitrary branching in composition

---

## Risk Watch

- **Drift risk:** If implementation starts changing registry, Studio, or generators, stop. Re-anchor against the design doc's "What Claude Code Must Not Do" list.
- **v0.22 regression risk:** Approval grants must not change how `parent_token` is interpreted. Run full v0.22 token test suite as part of v0.23 CI.
- **Schema breaking risk:** Compatibility default (`kind` absent → `atomic`) means v0.22 manifests still validate. Verify with a v0.22 fixture in v0.23 schema tests.
- **Grant storage migration risk:** PostgreSQL migration must be idempotent and not block service startup if grants table doesn't yet exist.
