# Studio to Registry Phase 1 Design

## Purpose

Studio revision lineage is now becoming internally coherent, but it is still too local.

If the only place that can interpret, generate from, or verify a saved ANIP Service Definition is the Studio instance that authored it, the model is not practical for real delivery.

Phase 1 starts the registry implementation so that:

- Studio remains the authoring and review surface
- selected revisions become portable immutable published records
- generation and verification can target those published records
- later Studio instances, CI jobs, and verifier tooling can resolve the same identities

This is not a full public marketplace design.

It is the minimum registry slice that makes the trust model operational.

## Decision

The canonical lineage model remains layered:

- Product Revision
- Developer Baseline pinned to a Product Revision
- Developer Revision pinned to that baseline
- Generation Run pinned to that Developer Revision
- Verification / PM Review pinned to that Developer Revision

The registry does not replace that model.

The registry publishes selected lineage from that model as immutable portable records.

Hard rule:

**Artifact lineage remains the source of truth. Registry publication makes that lineage portable.**

## What Phase 1 Must Solve

Phase 1 only needs to answer four questions:

1. What exact selected Product and Developer lineage was published?
2. What immutable registry identity represents it?
3. Can generation target that registry identity instead of only local Studio state?
4. Can verification target that registry identity from another environment?

If those four things work, the architecture becomes practically useful.

## What Phase 1 Does Not Solve

Not in scope for the first slice:

- full user management / publisher organizations
- public package discovery
- extension pack marketplace
- verifier pack marketplace
- distributed transparency log
- cross-registry federation
- release management beyond selected published lineage
- deployment inventory

Those should come after the portable immutable record flow exists.

## Published Unit

The published unit should be a selected blueprint-style package, not a raw Studio workspace snapshot.

Phase 1 published package:

- `manifest.json`
- `anip-service-definition.json`
- `anip.recommended.lock`
- `registry-receipt.json`

Optional later:

- signatures directory
- regression pack references
- extension pack manifests
- compatibility matrices

The Service Definition remains the behavior authority.

The manifest and receipt add portability, provenance, and resolution metadata.

## Minimal Registry Record Model

Phase 1 should introduce three identities:

### 1. Published Lineage Record

Represents the selected Studio lineage that was published.

Minimum fields:

- `id`
- `project_id`
- `project_name`
- `product_revision_artifact_id`
- `product_revision_number`
- `developer_revision_artifact_id`
- `developer_revision_number`
- `contract_signature`
- `contract_signature_algorithm`
- `definition_digest`
- `manifest_digest`
- `status` (`published`, later `superseded`, `archived`)
- `published_at`

### 2. Registry Package Record

Represents the portable published package identity.

Minimum fields:

- `package_id`
- `package_version`
- `published_lineage_id`
- `publisher_ref`
- `schema_version`
- `build_pack_name`
- `build_pack_version`
- `verifier_pack_name`
- `verifier_pack_version`
- `recommended_lock`
- `manifest`
- `service_definition`
- `created_at`

### 3. Registry Receipt

Represents registry acceptance of the package.

Minimum fields:

- `receipt_id`
- `package_id`
- `package_version`
- `artifact_digests`
- `publisher_ref`
- `accepted_at`
- `registry_signature`

## Selection Rule Before Publish

Registry publication should only happen from selected lineage, not arbitrary drafts.

Phase 1 selection rule:

- Product revision must be immutable
- Developer revision must be immutable
- Developer revision must be the currently selected candidate for that project
- PM review state for that developer revision must be acceptable for publish

This avoids publishing multiple equally-current candidates by accident.

## Generation and Verification Target Model

Today Studio generation and verification are still largely local-artifact based.

Phase 1 should add a portable target form:

- `registry://<package_id>@<package_version>`

Generation metadata should record:

- `registry_package_id`
- `registry_package_version`
- `registry_receipt_id`
- `developer_revision_artifact_id`
- `developer_revision_number`
- `contract_signature`

Verification metadata should record the same target.

This allows verification to say:

- this evidence is aligned to the currently selected published lineage
- this evidence is superseded because a newer published lineage exists
- this evidence is stale because it does not match the published target it claims to verify

## Repo Mapping

The implementation should map onto current repo seams instead of introducing a separate conceptual stack.

### Studio frontend

Primary files:

- `studio/src/design/project-types.ts`
- `studio/src/design/project-api.ts`
- `studio/src/design/use-developer-definition-editor.ts`
- `studio/src/views/DeveloperDefinitionView.vue`
- `studio/src/views/DeveloperDesignHomeView.vue`
- `studio/src/views/ProjectVerificationView.vue`
- `studio/src/views/PmReviewView.vue`

Phase 1 frontend responsibilities:

- show selected Product and Developer revision lineage
- show published registry status for the selected lineage
- offer a publish action from the selected Developer revision
- show registry identity in generation and verification surfaces
- distinguish:
  - local immutable revision
  - selected revision
  - published registry record

### Studio backend

Primary files:

- `studio/server/models.py`
- `studio/server/repository.py`
- `studio/server/routers/artifacts.py`
- `studio/server/migrations/*.sql`

New backend modules to add:

- `studio/server/registry_service.py`
- `studio/server/registry_manifest.py`
- `studio/server/registry_receipts.py`
- `studio/server/routers/registry.py`

Phase 1 backend responsibilities:

- build publishable package payloads from selected lineage
- validate required lineage references exist
- compute deterministic digests
- persist published lineage and package records
- issue registry receipts
- resolve published packages by identity

### Generator path

Current implementation:

- `packages/typescript/generator/*`
- `studio/server/generator_cli.py`

Phase 1 generator changes:

- keep existing `anip-service-definition.json` generation path
- add the ability to generate from a resolved registry package record
- keep generator itself registry-agnostic where possible
- let Studio or a thin resolver fetch the Service Definition, then hand it to the generator

That means the generator package should not absorb registry business logic.

Instead:

- registry client resolves package
- generator consumes resolved `anip-service-definition.json`

### Crypto and verification

Current implementation:

- `packages/typescript/crypto/*`
- `packages/python/anip-crypto/*`

Phase 1 crypto responsibilities:

- deterministic digest helpers for package payloads
- receipt signature verification
- later blueprint signature verification

Phase 1 should not invent a second signing model if existing canonicalization and signature patterns can be reused.

## Recommended Package Placement

There are two plausible paths:

### Option A: Build the first registry service inside Studio server

Pros:

- fastest path to operational proof
- easy access to current project lineage and local artifacts
- lowest migration cost for current Studio work

Cons:

- risks reinforcing Studio as the runtime trust anchor
- later extraction is required

### Option B: Build a separate registry package now

Suggested future package:

- `packages/python/anip-registry`

Pros:

- cleaner long-term architecture
- clearer boundary between authoring and registry trust

Cons:

- more setup cost immediately
- Studio publish flow becomes cross-service from day one

### Recommendation

Use a hybrid approach:

- implement the first registry service in `studio/server/*`
- keep its logic in clearly isolated `registry_*` modules and routes
- avoid mixing registry logic into unrelated Studio authoring modules
- plan a later extraction into `packages/python/anip-registry` once the API stabilizes

This gives speed now without losing the eventual separation.

## Database Additions

Phase 1 should add dedicated tables rather than overloading `pm_artifacts`.

Suggested tables:

### `published_lineages`

- `id`
- `project_id`
- `product_revision_artifact_id`
- `product_revision_number`
- `developer_revision_artifact_id`
- `developer_revision_number`
- `contract_signature`
- `contract_signature_algorithm`
- `status`
- `published_at`
- `created_at`
- `updated_at`

### `registry_packages`

- `package_id`
- `package_version`
- `published_lineage_id`
- `publisher_ref`
- `manifest`
- `service_definition`
- `recommended_lock`
- `definition_digest`
- `manifest_digest`
- `status`
- `created_at`

Primary key can be composite on `package_id` and `package_version`.

### `registry_receipts`

- `receipt_id`
- `package_id`
- `package_version`
- `receipt`
- `receipt_signature`
- `created_at`

This keeps local Studio artifacts separate from portable published records.

## API Surface

Phase 1 API endpoints:

- `POST /api/projects/{project_id}/registry/publish`
- `GET /api/projects/{project_id}/registry/publications`
- `GET /api/registry/packages/{package_id}/{package_version}`
- `GET /api/registry/packages/{package_id}/{package_version}/receipt`

The publish endpoint should:

1. resolve the selected Product and Developer revisions
2. validate publish preconditions
3. build manifest, Service Definition, and recommended lock
4. compute digests
5. persist package + published lineage
6. issue registry receipt
7. return the published identity

## Recommended Lockfile for Phase 1

Phase 1 recommended lock can be intentionally narrow.

It should include:

- `service_definition_digest`
- `contract_signature`
- `build_pack`
  - name
  - version
- `verifier_pack`
  - name
  - version
- `generated_at`
- `publisher_ref`

For the first slice:

- build pack can be `@anip-dev/generator-typescript`
- verifier pack can initially point to Studio local proof / current verification flow metadata until the dedicated verifier pack exists

This is enough to establish the pattern without pretending the verifier-pack ecosystem already ships.

## Phased Implementation

### Phase 1A: Local registry publication from Studio

Deliver:

- selected lineage model in Studio UI
- publish selected lineage
- persist registry package records
- issue registry receipts
- show published identity in Studio

This makes publication real even if resolution is still local to the same deployed Studio backend.

### Phase 1B: Generator and verification target published identities

Deliver:

- generation runs record registry package identity
- verification runs record registry package identity
- Studio verification UI classifies evidence as aligned, superseded, or stale relative to published lineage

This is the point where the registry meaningfully affects delivery semantics.

### Phase 1C: External resolution

Deliver:

- package fetch by package id and version
- generator invocation from resolved package payload
- verification invocation against resolved package payload

At this point a second Studio instance or CI runner can resolve the same package and verify against it.

## Why This Is the Right Next Step

The repo already has:

- Studio authoring and review
- immutable local revision work underway
- standalone TypeScript generator package
- crypto packages in TypeScript and Python
- trust-model and build-pack design docs

What is missing is the portable immutable publication layer.

That is the next bottleneck.

Further expanding local-only revision behavior before adding publication would improve internal consistency while still leaving the overall workflow operationally trapped inside one Studio instance.

## Immediate Build Order

Recommended implementation order:

1. Add selected lineage semantics in Studio for Developer revisions.
2. Add `published_lineages`, `registry_packages`, and `registry_receipts` tables.
3. Add `registry_*` backend service modules and routes under `studio/server`.
4. Add Studio publish UI on Developer Definition / PM Review.
5. Record published registry identity on generation runs.
6. Record published registry identity on verification evidence.
7. Add external package resolution path.

## Open Questions To Defer Briefly

These matter, but should not block Phase 1:

- publisher org and auth model
- whether package ids are project-scoped or publisher-scoped
- whether package versioning should be semver, revision-based, or both
- whether registry receipts should be detached JWS or embedded signed JSON
- when to extract registry server into `packages/python/anip-registry`

The system becomes materially more practical before those answers are fully finalized.
