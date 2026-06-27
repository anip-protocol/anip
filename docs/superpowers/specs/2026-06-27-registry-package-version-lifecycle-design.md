# Registry Package Version Lifecycle Design

## Context

Registry packages are immutable artifacts, but immutable does not mean every published version should remain recommended forever. A package family can have a bad version while later versions are valid. The Registry currently has artifact-level moderation for package/template ownership, suspension, abuse reports, and takedowns, but it does not expose a precise lifecycle state for a specific package version.

The immediate example is `gtm-pipeline-q2-review@0.4.4`: it should remain auditable, but users should be steered to the corrected package version. Suspending the whole `gtm-pipeline-q2-review` package family would also affect good versions, so that is too blunt.

## Goals

- Add lifecycle state per `(package_id, package_version)`.
- Preserve package immutability and auditability.
- Let Registry UI, CLI, generator, and Studio warn or fail consistently.
- Support a replacement pointer such as `gtm-pipeline-q2-review@0.4.5`.
- Avoid silent redirects. Explicit package references must stay deterministic.

## Non-Goals

- Do not delete published package rows.
- Do not mutate package manifests, service definitions, locks, or receipts.
- Do not suspend an entire package family when only one version is bad.
- Do not use lifecycle state as a substitute for package verification.
- Do not implement automatic dependency resolution to a replacement version.

## Lifecycle States

`active`
: The normal state. Package version appears in listings, can be downloaded, and can be generated from without lifecycle warnings.

`superseded`
: The version is immutable and still available, but a newer version is preferred. Registry and CLI show a warning and link to the replacement version when provided.

`deprecated`
: The version is available but should not be used for new generation. This is stronger than superseded and should show a prominent warning. CLI/generator warns by default.

`yanked`
: The version should not be consumed by default. Public listings hide it unless users choose to show yanked versions. Detail pages remain available for transparency. Download/generate fails unless an explicit override is provided.

`takedown`
: The version is unavailable to normal users. Admin/audit metadata remains retained. Public access returns a takedown response without package contents.

## Data Model

Add lifecycle columns to `registry_packages`:

- `lifecycle_status TEXT NOT NULL DEFAULT 'active'`
- `lifecycle_reason TEXT NOT NULL DEFAULT ''`
- `lifecycle_replacement_package_id TEXT`
- `lifecycle_replacement_package_version TEXT`
- `lifecycle_updated_at TIMESTAMPTZ`
- `lifecycle_updated_by TEXT`

Validation rules:

- Status must be one of `active`, `superseded`, `deprecated`, `yanked`, `takedown`.
- Replacement package/version is optional for `superseded` and `deprecated`.
- Replacement package/version should normally be present for `superseded`.
- Replacement cannot point to the same package version.
- Existing rows migrate to `active`.

## API Contract

Public package responses include:

```json
{
  "lifecycle": {
    "status": "superseded",
    "reason": "Later validation found behavior drift in hard-mode GTM cases.",
    "replacement": {
      "package_id": "gtm-pipeline-q2-review",
      "package_version": "0.4.5"
    },
    "updated_at": "2026-06-27T00:00:00Z"
  }
}
```

For compatibility, missing lifecycle in older clients should be treated as `active`.

Admin endpoints:

- `PATCH /registry-api/v1/admin/packages/{packageID}/{version}/lifecycle`
- Body: `status`, `reason`, optional replacement package/version.
- Requires admin auth.
- Records updater identity where available.

Public endpoints:

- `GET /packages/{id}/{version}` returns lifecycle metadata for all statuses except `takedown`, where it returns a limited public takedown payload.
- `GET /packages/{id}/{version}/download` returns lifecycle metadata and contents for `active`, `superseded`, and `deprecated`.
- `download` fails for `yanked` unless an override query/header is provided.
- `download` fails for `takedown`.
- `GET /packages/{id}/{version}/lock` follows the same access rules as download.

## Registry UI

Package list:

- Group versions by package id as today.
- Use the latest active version as the default version when present.
- Show lifecycle badges next to non-active versions.
- Hide yanked/takedown versions from default version lists unless "show unavailable versions" is enabled.

Package detail:

- Show a high-visibility lifecycle banner for `superseded`, `deprecated`, `yanked`, and `takedown`.
- If replacement is present, provide a link to the replacement package version.
- Keep receipt, digest, and lineage visible for superseded/deprecated/yanked where allowed.

Admin UI:

- Add per-version lifecycle controls separate from artifact ownership moderation.
- Require a reason for any non-active lifecycle change.
- Allow setting replacement package/version.
- Show lifecycle state in the package-version data grid.

## CLI and Generator Behavior

Registry client should parse lifecycle metadata.

Default behavior:

- `active`: proceed.
- `superseded`: warn and proceed.
- `deprecated`: warn and proceed.
- `yanked`: fail unless an explicit override is supplied.
- `takedown`: fail.

Proposed CLI option:

- `--allow-yanked-package`

The CLI should never silently replace a requested version with a replacement version. It may print a suggested command using the replacement version.

## Studio Behavior

Studio should surface lifecycle metadata when:

- browsing Registry packages/templates,
- verifying a Registry package,
- generating from a Registry package,
- promoting a local package to Registry,
- displaying a previously released package for a project.

For `superseded` and `deprecated`, Studio should show warnings. For `yanked` and `takedown`, Studio should block generation/promotion unless the backend explicitly supports an override for yanked versions.

## Testing

Backend tests:

- migration defaults existing package rows to `active`,
- lifecycle update requires admin auth,
- lifecycle update validates status and replacement,
- public package detail includes lifecycle,
- download behavior matches lifecycle state,
- yanked and takedown access rules are enforced.

Frontend tests:

- package list shows lifecycle badges,
- detail page shows replacement warning,
- admin UI can update lifecycle state,
- yanked/takedown versions are not shown as recommended.

CLI/generator tests:

- warning for `superseded` and `deprecated`,
- failure for `yanked` without override,
- failure for `takedown`,
- no silent replacement of explicit package references.

Studio tests:

- Registry package lifecycle warnings render in package browsing and verification surfaces,
- yanked/takedown packages block generation paths.

## Rollout

1. Add DB/API lifecycle support with default `active`.
2. Add Registry UI badges and admin lifecycle controls.
3. Add CLI/generator lifecycle enforcement.
4. Add Studio lifecycle warnings.
5. Mark `gtm-pipeline-q2-review@0.4.4` as `superseded` or `deprecated` in production Registry with replacement `gtm-pipeline-q2-review@0.4.5`.

## Open Decision

For `gtm-pipeline-q2-review@0.4.4`, the safest first action is `deprecated` if we believe users should not generate from it anymore, or `superseded` if we only want to steer them away while keeping it broadly usable. My recommendation is `deprecated` because we know it can produce incorrect generated-service behavior.
