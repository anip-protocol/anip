# Public Registry Multi-Publisher Plan

## Purpose

Turn ANIP Registry from an ANIP-operated publication endpoint into a public multi-publisher registry where external users and organizations can own namespaces, create scoped publish tokens, publish packages/templates, and manage publication authority without relying on one global registry token.

This plan implements GitHub issue #213.

## Current State

The registry already has a solid artifact trust core:

- Public read APIs for packages, templates, receipts, keys, downloads, and listings.
- Immutable package and template version records.
- Server-side manifest, service definition, lock, template, and package digests.
- Ed25519 registry receipts.
- Postgres migrations owned by `packages/go/registryapi`.
- Abuse controls for package size, nesting, suspicious binary payloads, and invalid contract shapes.
- Download counters and public UI grouping by package/template id and version.
- `publisher_id` and `publisher_type` fields on packages, templates, receipts, and listing summaries.

The main gap is publication authority.

Today publication writes are protected by a single deployment-level bearer token:

```text
ANIP_REGISTRY_PUBLISH_TOKEN
```

The backend then stamps publisher identity from deployment config:

```text
ANIP_REGISTRY_PUBLISHER_ID
ANIP_REGISTRY_PUBLISHER_TYPE
```

That is acceptable for ANIP-owned registry bootstrapping. It is not acceptable for a public ecosystem.

## Non-Negotiable Security Properties

- Publishing must not depend on one global token.
- Publisher identity must come from authenticated principal/token context, not from request body or deployment defaults.
- Publish tokens must be scoped by publisher, namespace, artifact kind, and operation.
- Package/template ids must be authorized by namespace ownership.
- Existing immutable version semantics must remain unchanged.
- Existing registry URLs must continue to resolve.
- Existing ANIP-owned packages/templates must migrate under an official ANIP publisher without digest drift.
- Suspended publishers and revoked tokens must not publish.
- Every account, token, namespace, publication, suspension, and transfer action must be auditable.

## MVP Boundary

The first public registry release should not try to become a full marketplace.

### In Scope

- User accounts.
- Publisher profiles for individuals and organizations.
- Publisher memberships with roles.
- Namespace reservation and ownership.
- Scoped publish tokens.
- Publisher-aware package/template publish APIs.
- Public publisher identity and trust status on package/template pages.
- Admin suspension and token revocation.
- Audit events.
- Migration of current ANIP-owned artifacts to an official `anip` publisher.

### Out of Scope

- Billing.
- Paid/private packages.
- Ranking or recommendation systems.
- Complex legal/takedown automation.
- Dependency vulnerability scanning.
- Automated brand verification beyond initial namespace policy.

## Proposed Auth Direction

Use external identity for login instead of building password storage first.

Recommended MVP:

- GitHub OAuth for users.
- Optional email field for contact and publisher recovery.
- Registry-issued publish tokens for CLI/Studio publication.
- Admin bootstrap via deployment-configured allowlist.

Why GitHub OAuth first:

- Most early publishers are developers or organizations already using GitHub.
- Avoids password reset, credential stuffing, and passkey UX work in the first cut.
- Keeps registry-owned secrets limited to publish tokens.

Future additions:

- Passkeys.
- Email/password if there is a product reason.
- Organization verification beyond GitHub ownership.

## Data Model

Add migrations after the existing registry schema.

### `registry_users`

Represents a human account.

Fields:

- `user_id` UUID primary key.
- `github_user_id` text unique nullable.
- `github_login` text nullable.
- `display_name` text not null.
- `email` text nullable.
- `status` text not null: `active`, `suspended`.
- `created_at`, `updated_at`, `last_login_at`.

### `registry_publishers`

Represents a publishing identity.

Fields:

- `publisher_id` text primary key.
- `publisher_type` text not null: `individual`, `organization`, `official`.
- `display_name` text not null.
- `description` text not null default empty.
- `website_url` text not null default empty.
- `status` text not null: `active`, `pending_review`, `suspended`.
- `trust_level` text not null: `unverified`, `verified`, `official`.
- `created_by_user_id` UUID references `registry_users`.
- `created_at`, `updated_at`.

### `registry_publisher_memberships`

Connects users to publishers.

Fields:

- `publisher_id` text references `registry_publishers`.
- `user_id` UUID references `registry_users`.
- `role` text not null: `owner`, `maintainer`, `publisher`, `viewer`.
- `created_at`, `updated_at`.
- Primary key: `(publisher_id, user_id)`.

Role meaning:

- `owner`: manage publisher, members, namespaces, tokens, transfers.
- `maintainer`: manage packages/templates and create publish tokens.
- `publisher`: publish versions for allowed namespaces.
- `viewer`: inspect private publisher settings if added later.

### `registry_namespaces`

Owns the id prefix policy.

Fields:

- `namespace` text primary key.
- `publisher_id` text references `registry_publishers`.
- `artifact_kinds` jsonb not null default `["package","template"]`.
- `status` text not null: `active`, `reserved`, `suspended`.
- `created_at`, `updated_at`.

Initial namespace policy:

- Official ANIP packages use namespace `anip`.
- Showcase packages may keep current ids during migration by assigning exact-name aliases where needed.
- New public package/template ids should use `namespace/name` or another explicit namespace form before broad public publishing is enabled.

### `registry_publish_tokens`

Stores hashed tokens only.

Fields:

- `token_id` UUID primary key.
- `publisher_id` text references `registry_publishers`.
- `token_hash` text unique not null.
- `label` text not null.
- `scopes` jsonb not null.
- `created_by_user_id` UUID references `registry_users`.
- `expires_at` timestamptz nullable.
- `last_used_at` timestamptz nullable.
- `revoked_at` timestamptz nullable.
- `created_at`, `updated_at`.

Scopes should be explicit:

```json
{
  "operations": ["publish:package", "publish:template"],
  "namespaces": ["anip", "jira-fronting"],
  "package_ids": [],
  "template_ids": []
}
```

Token format:

```text
anip_pat_<token_id>_<secret>
```

Only `secret` hash is stored. The full token is shown once.

### `registry_artifact_ownership`

Tracks package/template ownership separately from immutable versions.

Fields:

- `artifact_kind` text not null: `package`, `template`.
- `artifact_id` text not null.
- `publisher_id` text references `registry_publishers`.
- `namespace` text references `registry_namespaces`.
- `status` text not null: `active`, `transferred`, `suspended`.
- `created_at`, `updated_at`.
- Primary key: `(artifact_kind, artifact_id)`.

This lets existing public ids keep resolving while new versions are authorized through the ownership table.

### `registry_audit_events`

Append-only audit log.

Fields:

- `event_id` UUID primary key.
- `actor_user_id` UUID nullable.
- `actor_publisher_id` text nullable.
- `token_id` UUID nullable.
- `event_type` text not null.
- `target_type` text not null.
- `target_id` text not null.
- `metadata` jsonb not null default `{}`.
- `ip_hash` text nullable.
- `user_agent_hash` text nullable.
- `created_at`.

Minimum event types:

- `user.login`
- `publisher.created`
- `publisher.suspended`
- `membership.added`
- `membership.removed`
- `namespace.reserved`
- `namespace.suspended`
- `token.created`
- `token.used`
- `token.revoked`
- `package.published`
- `template.published`
- `artifact.transferred`

## API Plan

Keep public read APIs stable.

### Public Read APIs

Existing routes remain:

- `GET /registry-api/v1/publications`
- `GET /registry-api/v1/templates`
- `GET /registry-api/v1/packages/{packageID}/{version}`
- `GET /registry-api/v1/templates/{templateID}/{version}`
- `GET /registry-api/v1/packages/{packageID}/{version}/receipt`
- `GET /registry-api/v1/keys`

Add:

- `GET /registry-api/v1/publishers/{publisherID}`
- `GET /registry-api/v1/publishers/{publisherID}/packages`
- `GET /registry-api/v1/publishers/{publisherID}/templates`

### Auth APIs

MVP GitHub OAuth:

- `GET /registry-api/v1/auth/github/start`
- `GET /registry-api/v1/auth/github/callback`
- `POST /registry-api/v1/auth/logout`
- `GET /registry-api/v1/me`

Session cookies should be HTTP-only, secure in production, same-site lax or strict.

### Publisher Management APIs

- `POST /registry-api/v1/publishers`
- `GET /registry-api/v1/publishers/{publisherID}/settings`
- `PATCH /registry-api/v1/publishers/{publisherID}`
- `POST /registry-api/v1/publishers/{publisherID}/members`
- `PATCH /registry-api/v1/publishers/{publisherID}/members/{userID}`
- `DELETE /registry-api/v1/publishers/{publisherID}/members/{userID}`
- `POST /registry-api/v1/publishers/{publisherID}/namespaces`
- `GET /registry-api/v1/publishers/{publisherID}/tokens`
- `POST /registry-api/v1/publishers/{publisherID}/tokens`
- `DELETE /registry-api/v1/publishers/{publisherID}/tokens/{tokenID}`

### Publish APIs

Keep routes stable:

- `POST /registry-api/v1/publications`
- `POST /registry-api/v1/templates`

Change authorization:

- First try scoped publisher token auth.
- For a transition period, allow legacy `ANIP_REGISTRY_PUBLISH_TOKEN` only when `ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED=true`.
- Publisher identity must be derived from auth context.
- Request body `publisher_id` and `publisher_type` must be ignored or rejected if they conflict with auth context.

## CLI Plan

Update `anip package publish-bundle` and template publishing paths.

MVP:

- Keep `--publish-token`.
- Rename docs/examples to describe it as a scoped registry token, not a global registry token.
- Improve errors for missing namespace ownership, suspended publisher, expired token, revoked token, and insufficient scope.

Later:

- `anip registry login`
- `anip registry whoami`
- `anip registry token create`
- `anip registry token revoke`

## UI Plan

Add registry account surfaces without weakening public browsing.

Pages:

- `/registry/login`
- `/registry/account`
- `/registry/publishers/new`
- `/registry/publishers/:publisherId`
- `/registry/publishers/:publisherId/settings`
- `/registry/publishers/:publisherId/tokens`
- `/registry/publishers/:publisherId/namespaces`

Package/template detail pages should show:

- publisher display name
- publisher id
- trust level
- signature status
- artifact digest
- publication lineage
- current ownership status

## Migration Plan

Migration must not change existing package/template payload digests.

Steps:

1. Create official publisher:
   - `publisher_id = anip`
   - `publisher_type = official`
   - `trust_level = official`
2. Create namespaces and artifact ownership rows for all existing ANIP-owned packages/templates.
3. Backfill current `publisher_id`/`publisher_type` fields where needed only if record semantics require it.
4. Do not modify package/template manifest JSON unless publishing a new immutable version.
5. Verify all existing package/template detail, download, receipt, and lock URLs still resolve.

## Implementation Phases

### Phase 1: Design Lock and Migration Skeleton

Deliver:

- This plan.
- Migration file creating publisher/account/token/audit tables.
- Store methods for publisher lookup and audit append.
- Tests proving migrations run and existing package/template routes still work.

No public signup yet.

### Phase 2: Scoped Token Auth

Deliver:

- Token hashing and validation.
- Auth context resolved from bearer token.
- Publish APIs derive publisher from token.
- Namespace/artifact ownership checks for packages and templates.
- Legacy global token behind explicit transition flag.
- Tests for revoked, expired, wrong namespace, wrong operation, suspended publisher, and successful publish.

This phase closes the largest security gap.

### Phase 3: Official ANIP Migration

Deliver:

- Admin/bootstrap path to create the official `anip` publisher.
- Migration/backfill command or idempotent startup task for existing records.
- Tests showing existing registry packages/templates still resolve unchanged.
- Public UI displays official publisher identity.

### Phase 4: User Login and Publisher Dashboard

Deliver:

- GitHub OAuth login.
- Session management.
- Publisher create/manage UI.
- Token create/revoke UI.
- Namespace request/reservation UI.

### Phase 5: Admin and Moderation

Deliver:

- Admin allowlist.
- Suspend/restore publisher.
- Suspend namespace/artifact.
- Revoke token.
- Audit viewer.
- Abuse report endpoint and minimal review queue.

## Release Gates

- Existing public read APIs remain backward-compatible.
- Existing package/template records keep resolving.
- Publishing with no auth returns `401`.
- Publishing with legacy global token fails unless explicitly enabled.
- Publishing with scoped token succeeds only for owned namespace/artifact and allowed operation.
- Revoked/expired/suspended tokens fail closed.
- Request-supplied publisher identity cannot override token-derived publisher identity.
- Package/template pages show publisher identity and trust status.
- Audit events are emitted for all publish and token operations.

## Open Decisions

- Exact namespace syntax for public package ids: `namespace/name`, `namespace.name`, or current flat id plus ownership aliases.
- Whether new publishers start as `pending_review` or `active`.
- Whether GitHub organization membership should be used for publisher verification.
- Whether scoped tokens should support CIDR restrictions in the first public cut.
- Whether package and template namespaces should be shared or separately reservable.

## Recommended First PR

Start with Phase 1 only.

Do not include UI login or OAuth in the first PR. The first PR should add durable schema primitives and tests while preserving current runtime behavior. That keeps the existing registry deployment safe and gives later scoped-token work a stable foundation.

