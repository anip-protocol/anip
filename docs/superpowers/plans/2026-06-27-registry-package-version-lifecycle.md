# Registry Package Version Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-version lifecycle controls to Registry so a bad immutable package version can be deprecated, superseded, yanked, or taken down without affecting good versions in the same package family.

**Architecture:** Store lifecycle metadata directly on `registry_packages`, expose it through public package APIs, enforce access rules at package download/lock boundaries, and surface lifecycle status in Registry UI, CLI/generator, and Studio. Artifact ownership moderation remains package-family-level; package lifecycle is version-level.

**Tech Stack:** Go registry API/store/client/generator, PostgreSQL migrations, Vue Registry UI, Vue Studio UI, existing Go/Vitest/Maven/dotnet/npm test suites.

---

## File Map

- Create `packages/go/registryapi/migrations/009_package_lifecycle.sql`: Adds lifecycle columns and indexes to `registry_packages`.
- Modify `packages/go/registryapi/types.go`: Adds lifecycle structs, request types, and lifecycle fields to package records and summaries.
- Modify `packages/go/registryapi/store.go`: Adds lifecycle validation helpers and in-memory lifecycle behavior.
- Modify `packages/go/registryapi/postgres.go`: Reads/writes lifecycle metadata and adds admin update support.
- Modify `packages/go/registryapi/http.go`: Adds lifecycle admin endpoint and enforces yanked/takedown access rules.
- Modify `packages/go/registryapi/http_test.go` and `packages/go/registryapi/postgres_test.go`: Covers lifecycle API/storage behavior.
- Modify `packages/go/registryclient/client.go`: Parses lifecycle metadata and exposes warning/failure state to generator.
- Modify `packages/go/generator/resolver.go`: Warns for superseded/deprecated, fails for yanked/takedown unless explicitly allowed where supported.
- Modify `packages/go/internal/clicommands/generate/generate.go`: Adds `--allow-yanked-package` and passes it into package resolution.
- Modify `registry/src/api.ts`, `PublicationListView.vue`, `PackageDetailView.vue`, `AdminModerationView.vue`: Adds lifecycle badges, banners, and admin controls.
- Modify `studio/src/design/project-api.ts` plus Registry-facing Studio views: Surfaces lifecycle warnings for Registry package consumption.

---

## Task 1: Backend Lifecycle Model And Migration

**Files:**
- Create: `packages/go/registryapi/migrations/009_package_lifecycle.sql`
- Modify: `packages/go/registryapi/types.go`
- Modify: `packages/go/registryapi/store.go`
- Test: `packages/go/registryapi/http_test.go`

- [ ] **Step 1: Add failing lifecycle default test**

Add a test in `packages/go/registryapi/http_test.go` that publishes a package and asserts the public detail response includes `lifecycle.status == "active"`.

```go
func TestPackageDetailIncludesDefaultLifecycle(t *testing.T) {
	store := NewMemoryStore()
	request := validPublishPackageRequest(t)
	result, err := store.PublishPackage(request)
	if err != nil {
		t.Fatalf("publish package: %v", err)
	}

	record, ok := store.GetPackage(result.Package.PackageID, result.Package.PackageVersion)
	if !ok {
		t.Fatalf("expected package to exist")
	}
	if record.Lifecycle.Status != PackageLifecycleActive {
		t.Fatalf("expected active lifecycle, got %q", record.Lifecycle.Status)
	}
}
```

Run: `go test ./packages/go/registryapi -run TestPackageDetailIncludesDefaultLifecycle -count=1`

Expected before implementation: compile failure for missing `Lifecycle` / `PackageLifecycleActive`.

- [ ] **Step 2: Add lifecycle types**

In `packages/go/registryapi/types.go`, add:

```go
const (
	PackageLifecycleActive     = "active"
	PackageLifecycleSuperseded = "superseded"
	PackageLifecycleDeprecated = "deprecated"
	PackageLifecycleYanked     = "yanked"
	PackageLifecycleTakedown   = "takedown"
)

type PackageLifecycleReplacement struct {
	PackageID      string `json:"package_id"`
	PackageVersion string `json:"package_version"`
}

type PackageLifecycle struct {
	Status      string                       `json:"status"`
	Reason      string                       `json:"reason,omitempty"`
	Replacement *PackageLifecycleReplacement `json:"replacement,omitempty"`
	UpdatedAt   string                       `json:"updated_at,omitempty"`
	UpdatedBy   string                       `json:"updated_by,omitempty"`
}

type UpdatePackageLifecycleRequest struct {
	Status                    string `json:"status"`
	Reason                    string `json:"reason,omitempty"`
	ReplacementPackageID      string `json:"replacement_package_id,omitempty"`
	ReplacementPackageVersion string `json:"replacement_package_version,omitempty"`
}
```

Add `Lifecycle PackageLifecycle 'json:"lifecycle"'` to `PublicationSummary` and `RegistryPackageRecord`.

- [ ] **Step 3: Add lifecycle normalization helpers**

In `packages/go/registryapi/store.go`, add helpers:

```go
func defaultPackageLifecycle() PackageLifecycle {
	return PackageLifecycle{Status: PackageLifecycleActive}
}

func normalizePackageLifecycle(lifecycle PackageLifecycle) PackageLifecycle {
	lifecycle.Status = strings.TrimSpace(lifecycle.Status)
	if lifecycle.Status == "" {
		lifecycle.Status = PackageLifecycleActive
	}
	lifecycle.Reason = strings.TrimSpace(lifecycle.Reason)
	lifecycle.UpdatedAt = strings.TrimSpace(lifecycle.UpdatedAt)
	lifecycle.UpdatedBy = strings.TrimSpace(lifecycle.UpdatedBy)
	if lifecycle.Replacement != nil {
		lifecycle.Replacement.PackageID = strings.TrimSpace(lifecycle.Replacement.PackageID)
		lifecycle.Replacement.PackageVersion = strings.TrimSpace(lifecycle.Replacement.PackageVersion)
		if lifecycle.Replacement.PackageID == "" && lifecycle.Replacement.PackageVersion == "" {
			lifecycle.Replacement = nil
		}
	}
	return lifecycle
}

func validatePackageLifecycleUpdate(packageID string, packageVersion string, request UpdatePackageLifecycleRequest) (PackageLifecycle, error) {
	status := strings.TrimSpace(request.Status)
	if status == "" {
		return PackageLifecycle{}, fmt.Errorf("lifecycle status is required")
	}
	switch status {
	case PackageLifecycleActive, PackageLifecycleSuperseded, PackageLifecycleDeprecated, PackageLifecycleYanked, PackageLifecycleTakedown:
	default:
		return PackageLifecycle{}, fmt.Errorf("unsupported lifecycle status %q", status)
	}
	reason := strings.TrimSpace(request.Reason)
	if status != PackageLifecycleActive && reason == "" {
		return PackageLifecycle{}, fmt.Errorf("lifecycle reason is required for non-active status")
	}
	replacementID := strings.TrimSpace(request.ReplacementPackageID)
	replacementVersion := strings.TrimSpace(request.ReplacementPackageVersion)
	var replacement *PackageLifecycleReplacement
	if replacementID != "" || replacementVersion != "" {
		if replacementID == "" || replacementVersion == "" {
			return PackageLifecycle{}, fmt.Errorf("replacement package id and version must be provided together")
		}
		if replacementID == packageID && replacementVersion == packageVersion {
			return PackageLifecycle{}, fmt.Errorf("replacement package cannot point to itself")
		}
		replacement = &PackageLifecycleReplacement{PackageID: replacementID, PackageVersion: replacementVersion}
	}
	return PackageLifecycle{Status: status, Reason: reason, Replacement: replacement}, nil
}
```

- [ ] **Step 4: Default lifecycle on package build and memory reads**

In `buildPublishedArtifacts`, set `pkg.Lifecycle = defaultPackageLifecycle()`.

In memory store `GetPackage`, `RecordPackageDownload`, and `ListPublications`, normalize lifecycle before returning records/summaries.

- [ ] **Step 5: Add migration**

Create `packages/go/registryapi/migrations/009_package_lifecycle.sql`:

```sql
ALTER TABLE registry_packages
    ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS lifecycle_reason TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS lifecycle_replacement_package_id TEXT,
    ADD COLUMN IF NOT EXISTS lifecycle_replacement_package_version TEXT,
    ADD COLUMN IF NOT EXISTS lifecycle_updated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS lifecycle_updated_by TEXT;

ALTER TABLE registry_packages
    DROP CONSTRAINT IF EXISTS registry_packages_lifecycle_status_check;

ALTER TABLE registry_packages
    ADD CONSTRAINT registry_packages_lifecycle_status_check
    CHECK (lifecycle_status IN ('active', 'superseded', 'deprecated', 'yanked', 'takedown'));

CREATE INDEX IF NOT EXISTS idx_registry_packages_lifecycle
    ON registry_packages(lifecycle_status, package_id, package_version);
```

- [ ] **Step 6: Verify backend default lifecycle**

Run: `go test ./packages/go/registryapi -run TestPackageDetailIncludesDefaultLifecycle -count=1`

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add packages/go/registryapi
git commit -m "feat: add registry package lifecycle model"
```

---

## Task 2: Backend Admin Endpoint And Access Enforcement

**Files:**
- Modify: `packages/go/registryapi/http.go`
- Modify: `packages/go/registryapi/store.go`
- Modify: `packages/go/registryapi/postgres.go`
- Test: `packages/go/registryapi/http_test.go`
- Test: `packages/go/registryapi/postgres_test.go`

- [ ] **Step 1: Add failing admin lifecycle tests**

Add tests proving:

- admin can set `deprecated` with replacement,
- non-admin cannot set lifecycle,
- yanked download fails without override,
- takedown detail/download does not expose package contents.

Use existing admin auth helpers in `http_test.go`; if helper names differ, follow adjacent admin endpoint tests.

- [ ] **Step 2: Extend admin store interface**

In `packages/go/registryapi/http.go`, add to `NamespaceAdminStore`:

```go
	UpdatePackageLifecycle(ctx context.Context, packageID string, version string, request UpdatePackageLifecycleRequest, updatedBy string) (RegistryPackageRecord, bool, error)
```

- [ ] **Step 3: Implement memory lifecycle update**

In `packages/go/registryapi/store.go`, add `UpdatePackageLifecycle` on `MemoryStore` using `validatePackageLifecycleUpdate`, setting `UpdatedAt` and `UpdatedBy`.

- [ ] **Step 4: Implement Postgres lifecycle update**

In `packages/go/registryapi/postgres.go`, update `GetPackage` and `ListPublications` SELECT/scan logic to include lifecycle columns.

Add:

```go
func (s *PostgresStore) UpdatePackageLifecycle(ctx context.Context, packageID string, version string, request UpdatePackageLifecycleRequest, updatedBy string) (RegistryPackageRecord, bool, error) {
	lifecycle, err := validatePackageLifecycleUpdate(packageID, version, request)
	if err != nil {
		return RegistryPackageRecord{}, true, err
	}
	now := time.Now().UTC()
	var replacementID any
	var replacementVersion any
	if lifecycle.Replacement != nil {
		replacementID = lifecycle.Replacement.PackageID
		replacementVersion = lifecycle.Replacement.PackageVersion
	}
	tag, err := s.pool.Exec(ctx, `
		UPDATE registry_packages
		SET lifecycle_status = $3,
		    lifecycle_reason = $4,
		    lifecycle_replacement_package_id = $5,
		    lifecycle_replacement_package_version = $6,
		    lifecycle_updated_at = $7,
		    lifecycle_updated_by = $8,
		    updated_at = now()
		WHERE package_id = $1 AND package_version = $2
	`, packageID, version, lifecycle.Status, lifecycle.Reason, replacementID, replacementVersion, now, updatedBy)
	if err != nil {
		return RegistryPackageRecord{}, false, err
	}
	if tag.RowsAffected() != 1 {
		return RegistryPackageRecord{}, false, nil
	}
	record, ok := s.GetPackage(packageID, version)
	return record, ok, nil
}
```

- [ ] **Step 5: Add admin HTTP endpoint**

In `packages/go/registryapi/http.go`, add:

```go
mux.HandleFunc("PATCH /registry-api/v1/admin/packages/{packageID}/{version}/lifecycle", func(w http.ResponseWriter, r *http.Request) {
	adminStore, ok := store.(NamespaceAdminStore)
	if !ok {
		writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry package lifecycle administration is not supported by this store"})
		return
	}
	if !authorizeRegistryAdminRequest(w, r, options) {
		return
	}
	var request UpdatePackageLifecycleRequest
	if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid lifecycle request"})
		return
	}
	updatedBy := registryAdminActor(r, options)
	record, exists, err := adminStore.UpdatePackageLifecycle(r.Context(), r.PathValue("packageID"), r.PathValue("version"), request, updatedBy)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
		return
	}
	if !exists {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "package version not found"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"package": record})
})
```

If `registryAdminActor` does not exist, add a helper that uses browser session GitHub login when present and falls back to `"admin"`.

- [ ] **Step 6: Enforce public access rules**

Add helper in `http.go`:

```go
func packageLifecycleBlocksDownload(r *http.Request, lifecycle PackageLifecycle) (int, string) {
	switch lifecycle.Status {
	case PackageLifecycleYanked:
		if r.URL.Query().Get("allow_yanked") == "true" || r.Header.Get("X-ANIP-Allow-Yanked-Package") == "true" {
			return 0, ""
		}
		return http.StatusGone, "package version has been yanked"
	case PackageLifecycleTakedown:
		return http.StatusGone, "package version is unavailable"
	default:
		return 0, ""
	}
}
```

Use it before `RecordPackageDownload` and before lock generation. For detail, return limited lifecycle metadata for `takedown`.

- [ ] **Step 7: Verify backend lifecycle enforcement**

Run:

```bash
go test ./packages/go/registryapi -count=1
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add packages/go/registryapi
git commit -m "feat: enforce registry package lifecycle"
```

---

## Task 3: Registry UI Lifecycle Display And Admin Controls

**Files:**
- Modify: `registry/src/api.ts`
- Modify: `registry/src/views/PublicationListView.vue`
- Modify: `registry/src/views/PackageDetailView.vue`
- Modify: `registry/src/views/AdminModerationView.vue`
- Test: `registry/src/**/*.test.ts` if an adjacent test file exists; otherwise rely on `npm test`/build.

- [ ] **Step 1: Add frontend lifecycle types**

In `registry/src/api.ts`, add:

```ts
export interface PackageLifecycleReplacement {
  package_id: string
  package_version: string
}

export interface PackageLifecycle {
  status: 'active' | 'superseded' | 'deprecated' | 'yanked' | 'takedown'
  reason?: string
  replacement?: PackageLifecycleReplacement
  updated_at?: string
  updated_by?: string
}

export interface UpdatePackageLifecycleRequest {
  status: string
  reason?: string
  replacement_package_id?: string
  replacement_package_version?: string
}
```

Add `lifecycle?: PackageLifecycle` to `PublicationSummary` and `RegistryPackageRecord`.

Add:

```ts
export async function updateAdminPackageLifecycle(
  token: string | null,
  packageId: string,
  version: string,
  request: UpdatePackageLifecycleRequest,
): Promise<RegistryPackageRecord> {
  const payload = await api<{ package: RegistryPackageRecord }>(
    `/admin/packages/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/lifecycle`,
    {
      method: 'PATCH',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(request),
    },
  )
  return payload.package
}
```

- [ ] **Step 2: Show lifecycle badges in package list**

In `PublicationListView.vue`:

- Treat missing lifecycle as active.
- Use latest active version as group default when possible.
- Show badges for non-active versions.
- Keep explicit version links deterministic.

- [ ] **Step 3: Show lifecycle banner on package detail**

In `PackageDetailView.vue`, add computed lifecycle helpers and a banner above the package overview for non-active lifecycle states. If replacement exists, link to replacement detail.

- [ ] **Step 4: Add admin lifecycle grid**

In `AdminModerationView.vue`, add a package lifecycle section or extend artifact moderation with per-version package records. Prefer a separate section if adding package version rows; artifact ownership should remain family-level.

Fields:

- package id,
- version,
- current lifecycle,
- replacement,
- reason,
- update button.

- [ ] **Step 5: Verify Registry UI**

Run:

```bash
cd registry
npm test
npm run build
```

Expected: tests pass and Vite build completes.

- [ ] **Step 6: Commit**

```bash
git add registry
git commit -m "feat: show registry package lifecycle"
```

---

## Task 4: CLI And Generator Lifecycle Enforcement

**Files:**
- Modify: `packages/go/registryclient/client.go`
- Modify: `packages/go/generator/resolver.go`
- Modify: `packages/go/internal/clicommands/generate/generate.go`
- Test: `packages/go/registryclient/*_test.go` or `packages/go/generator/resolver_test.go`
- Test: `packages/go/cmd/anip-generate/main_test.go`

- [ ] **Step 1: Add failing resolver tests**

In `packages/go/generator/resolver_test.go`, add tests for:

- deprecated package resolves but records warning/check,
- yanked package fails by default,
- yanked package resolves with explicit allow option,
- takedown package fails.

- [ ] **Step 2: Parse lifecycle in registry client**

Mirror lifecycle types in `packages/go/registryclient/client.go` and add `Lifecycle PackageLifecycle 'json:"lifecycle"'` to `PackageRecord`.

- [ ] **Step 3: Add resolver option**

In generator registry resolution options, add:

```go
AllowYankedPackage bool
```

Then enforce:

```go
switch resolvedPackage.Package.Lifecycle.Status {
case "superseded", "deprecated":
	// Record warning in resolved metadata/trust checks.
case "yanked":
	if !options.AllowYankedPackage {
		return nil, fmt.Errorf("registry package %s@%s is yanked", packageID, packageVersion)
	}
case "takedown":
	return nil, fmt.Errorf("registry package %s@%s is unavailable", packageID, packageVersion)
}
```

- [ ] **Step 4: Add CLI flag**

In `packages/go/internal/clicommands/generate/generate.go`, add:

```go
fs.BoolVar(&allowYankedPackage, "allow-yanked-package", false, "Allow generation from a yanked Registry package version.")
```

Pass it to resolver options.

- [ ] **Step 5: Verify CLI/generator**

Run:

```bash
go test ./packages/go/registryclient ./packages/go/generator ./packages/go/cmd/anip-generate -count=1
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add packages/go/registryclient packages/go/generator packages/go/internal/clicommands packages/go/cmd/anip-generate
git commit -m "feat: enforce package lifecycle in generator"
```

---

## Task 5: Studio Lifecycle Surfacing

**Files:**
- Modify: `studio/src/design/project-api.ts`
- Modify: `studio/src/views/DeveloperDefinitionView.vue`
- Modify: Registry browsing/import views if lifecycle records flow there.
- Test: `studio/src/__tests__/api.test.ts`

- [ ] **Step 1: Add Studio types**

In `studio/src/design/project-api.ts`, add lifecycle interfaces matching Registry UI:

```ts
export interface RegistryPackageLifecycle {
  status: string
  reason?: string
  replacement?: {
    package_id: string
    package_version: string
  }
  updated_at?: string
  updated_by?: string
}
```

Add `lifecycle?: RegistryPackageLifecycle` to Registry package response types.

- [ ] **Step 2: Render lifecycle warning in release/package panels**

In `DeveloperDefinitionView.vue`, where latest Registry publication and verification status are shown, render lifecycle warning when status is not active.

For `deprecated` and `superseded`, show warning. For `yanked` and `takedown`, show blocking error.

- [ ] **Step 3: Add tests**

In `studio/src/__tests__/api.test.ts`, extend Registry package fixture parsing to include lifecycle metadata and assert it is preserved.

- [ ] **Step 4: Verify Studio UI build/tests**

Run:

```bash
cd studio
npm test
npm run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add studio
git commit -m "feat: surface package lifecycle in Studio"
```

---

## Task 6: End-To-End Verification And Production Action

**Files:**
- No source files expected unless verification exposes a defect.

- [ ] **Step 1: Run targeted backend and frontend checks**

Run:

```bash
go test ./packages/go/registryapi ./packages/go/registryclient ./packages/go/generator ./packages/go/cmd/anip-generate -count=1
cd registry && npm test && npm run build
cd ../studio && npm test && npm run build
```

Expected: all pass.

- [ ] **Step 2: Run smoke against local Registry**

Start local registry with Postgres or existing compose mode. Publish two versions of a fixture package. Mark the older version deprecated with replacement. Confirm:

- list shows latest active version,
- older detail shows warning,
- download still works for deprecated,
- yanked download fails without override,
- generator fails for yanked without `--allow-yanked-package`.

- [ ] **Step 3: Commit final verification notes if docs changed**

If any docs are updated during smoke, commit them. Otherwise do not create a no-op commit.

- [ ] **Step 4: Open PR**

```bash
git push -u origin registry-package-version-lifecycle
gh pr create --base main --head registry-package-version-lifecycle --title "Add Registry package version lifecycle controls" --body "Closes #261."
```

- [ ] **Step 5: After merge and deploy**

In production Registry, mark `gtm-pipeline-q2-review@0.4.4` as `deprecated` with replacement `gtm-pipeline-q2-review@0.4.5`.

Do not delete `0.4.4`.

---

## Self-Review

- Spec coverage: covered storage, API, UI, CLI/generator, Studio, testing, rollout, and the GTM `0.4.4` demotion use case.
- Placeholder scan: no TBD/TODO placeholders; implementation snippets and commands are concrete.
- Scope control: templates are not included yet. This plan is intentionally package-version lifecycle only. Template lifecycle can be added later with the same pattern if needed.
