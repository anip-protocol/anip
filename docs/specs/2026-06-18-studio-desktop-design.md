# ANIP Studio Desktop Design

## Context

Issue: [#218 Package ANIP Studio as a standalone desktop app](https://github.com/anip-protocol/anip/issues/218)

ANIP Studio is currently distributed in two main shapes:

- Hosted or Docker Compose product mode, with Studio Web, Studio API, and Postgres.
- Embedded inspection mode, where generated ANIP services mount the static Studio assets.

That works for developers, but it is too heavy for first-time users who want to inspect showcase projects, author a contract, try Autopilot/Guided/Manual modes, export a package, or evaluate ANIP without cloning the repository and running Docker.

The desktop app should be a first-class local authoring and review path, not a thin wrapper around the hosted site.

## Goals

- Let a user install and launch ANIP Studio on macOS without Docker.
- Start Studio Web and Studio API automatically.
- Store workspaces, projects, artifacts, settings, snapshots, and local publications in a local app data directory.
- Preload curated showcase snapshots on first launch.
- Support creating and editing projects locally.
- Support import/export of Studio project snapshots.
- Support package/template export.
- Support optional Registry connection and publish flow.
- Support optional AI provider configuration for Studio assistant features.
- Preserve the existing Docker/hosted Studio deployment path.

## Non-Goals For The First Release

- No Windows or Linux installer in the first milestone.
- No automatic code-generation toolchain bundling unless it is already available on the host.
- No bundled local LLM runtime.
- No replacement for the hosted public read-only Studio.
- No cloud sync of local projects.
- No silent dependency on Docker or an externally running Postgres.

## Key Constraint

Studio API currently assumes Postgres:

- `studio/server/db.py` uses `psycopg_pool.ConnectionPool`.
- migrations are Postgres SQL files.
- Docker Compose starts `postgres:16-alpine`.
- read-only mode can switch to a read-only Postgres role.

A desktop app that simply launches the current API still needs a database. Bundling and managing Postgres would be faster to prototype, but it would make the desktop app operationally fragile: process lifecycle, ports, initialization, upgrades, backup, and recovery all become hidden infrastructure.

The recommended direction is to introduce a desktop storage mode backed by SQLite.

## Recommended Architecture

### Runtime Shape

The desktop app owns three local pieces:

- Studio Web assets.
- Studio API sidecar process.
- SQLite database file under the app data directory.

Example app data layout on macOS:

```text
~/Library/Application Support/ANIP Studio/
  config.json
  studio.sqlite
  logs/
  snapshots/
  exports/
  temp/
```

The desktop shell launches Studio API on a loopback port, waits for `/api/health`, then loads the bundled Studio Web UI pointing at that local API.

### Storage Layer

Introduce a database backend abstraction inside `studio/server`:

- `postgres` backend: current production/Docker behavior.
- `sqlite` backend: desktop/local behavior.

The first implementation should avoid a full ORM rewrite. Keep repository functions stable where possible, but isolate connection creation, transaction handling, JSON binding, timestamp functions, advisory locks, and migration execution behind a small adapter layer.

SQLite mode should use:

- one local database file
- WAL mode
- foreign keys enabled
- explicit migrations
- no network listener

### Migrations

Desktop SQLite migrations should be separate from Postgres migrations.

Recommended layout:

```text
studio/server/migrations/postgres/
studio/server/migrations/sqlite/
```

Postgres mode should continue using the existing migration semantics. SQLite mode should use equivalent schema, adapted only where necessary for SQLite types and syntax.

Migration parity should be tested by exercising the same API behavior against both backends, not by requiring byte-identical SQL.

### Desktop Shell

Start with Tauri unless Python sidecar packaging proves impractical.

Tauri advantages:

- smaller app bundle
- better native macOS feel
- lower memory overhead than Electron
- good long-term fit for a serious local tool

Fallback to Electron if Tauri cannot reliably bundle or supervise the Python API sidecar.

The shell is responsible for:

- selecting a free loopback port
- launching the API sidecar
- passing desktop env vars
- opening the local Studio Web UI
- terminating the API on app shutdown
- exposing logs and diagnostics
- storing user config

### API Sidecar Configuration

Desktop mode should run with explicit environment variables:

```bash
STUDIO_MODE=desktop
STUDIO_DB_BACKEND=sqlite
STUDIO_SQLITE_PATH=<app-data>/studio.sqlite
STUDIO_SEED_SHOWCASES=1
STUDIO_READ_ONLY=0
STUDIO_RUN_MIGRATIONS=1
```

Assistant configuration should stay optional:

```bash
STUDIO_ASSISTANT_PROVIDER=openai
STUDIO_ASSISTANT_MODEL=gpt-5.4
OPENAI_API_KEY=<user-provided-key>
```

If no provider is configured, Studio keeps deterministic/manual behavior available.

### First-Run Experience

First launch should show a setup screen, not a blank workspace:

- local data directory location
- AI provider configuration, optional
- Registry URL, optional
- preload showcase snapshots, enabled by default
- import snapshot, optional

The user should be able to skip AI setup and still inspect showcases, use manual mode, import/export snapshots, and review packages.

### Showcase Snapshots

The desktop app should bundle the same curated snapshot set used by public read-only Studio:

- GTM Agent showcase
- Jira fronting showcase
- GitHub fronting showcase
- GitLab fronting showcase
- Slack fronting showcase
- Linear fronting showcase
- Notion fronting showcase
- Superset fronting showcase

On first launch, Studio imports the latest snapshot per package id/version into a local editable workspace.

Snapshot import should be idempotent. It must not duplicate projects on repeated app launch.

### Registry Integration

Registry connection is optional.

Desktop Studio should support:

- browsing local packages/templates created from the project
- exporting package/template files
- configuring `STUDIO_REGISTRY_URL`
- configuring a publish token in desktop settings
- adding browser-linked publishing in a follow-up milestone
- verifying Registry receipts when publishing is used

The first desktop milestone does not need to solve browser OAuth inside the desktop shell. Exporting packages/templates locally is enough for the first release.

### Security And Secrets

Desktop mode must not store raw provider keys in project snapshots.

Secrets should be stored in platform secure storage when available. If secure storage is not implemented in the first milestone, store secrets only in a clearly named local config file and document that limitation.

Snapshot export must exclude:

- AI provider API keys
- Registry publish tokens
- local filesystem paths that are not required for restoration

### Logging And Diagnostics

Desktop should provide a simple diagnostics view or menu item that exposes:

- API sidecar status
- local API URL
- database path
- app version
- log file path
- last startup error

This is important because packaging failures otherwise look like a blank desktop window.

## Milestones

### Milestone 1: Desktop Storage Foundation

Deliverable: Studio API can run locally against SQLite outside Docker.

Work:

- Add `STUDIO_DB_BACKEND=postgres|sqlite`.
- Add SQLite connection adapter.
- Add SQLite migrations equivalent to current Postgres schema.
- Update repository helpers only where required for backend-neutral SQL.
- Add backend matrix tests for core Studio flows.
- Add CLI/dev command to start Studio API in desktop mode.

Acceptance:

- Studio API starts with `STUDIO_DB_BACKEND=sqlite`.
- migrations create a fresh local DB.
- showcase snapshots import successfully.
- core project flows pass against SQLite.
- Docker/Postgres tests still pass.

### Milestone 2: Desktop Launcher Prototype

Deliverable: local macOS dev build launches Studio without Docker.

Work:

- Add Tauri app scaffold under `studio/desktop`.
- Bundle Studio Web build assets.
- Launch the Python API sidecar.
- Pass desktop env vars.
- Wait for health before rendering UI.
- Shut down sidecar on app exit.

Acceptance:

- `npm run desktop:dev` opens Studio.
- no Docker process is required.
- first launch creates a local SQLite DB.
- app can be quit and reopened with state preserved.

### Milestone 3: First-Run Setup And Snapshot Preload

Deliverable: desktop app is usable by a new evaluator.

Work:

- Add first-run setup flow.
- Configure AI provider key/model optionally.
- Configure Registry URL optionally.
- Preload latest showcase snapshots once.
- Add import/export entry points.
- Add diagnostics panel.

Acceptance:

- first launch has curated showcase projects.
- user can create a new project manually without AI.
- user can configure OpenAI and run assistant flows.
- user can export a package/template/snapshot.

### Milestone 4: Signed macOS Release

Deliverable: downloadable macOS artifact.

Work:

- Build release app in GitHub Actions.
- Sign and notarize if credentials are available.
- Publish artifacts from release workflow.
- Add install documentation.

Acceptance:

- user downloads the app.
- app opens without local repo checkout.
- app runs without Docker.
- docs explain desktop vs Docker vs hosted Studio.

## Testing Strategy

### Backend

- Run existing Studio API tests against Postgres.
- Add a SQLite test lane for repository and route coverage.
- Add snapshot import/export tests against SQLite.
- Add migration idempotency tests for SQLite.

### Desktop

- Launch sidecar in a test harness.
- Verify `/api/health`.
- Verify Studio Web loads.
- Verify app restart preserves workspace state.
- Verify first-run snapshot preload is idempotent.

### Release

- Smoke a built macOS artifact on a clean machine or clean user profile.
- Verify no Docker dependency.
- Verify logs are available for startup failures.

## Risks

- SQL portability may be worse than expected because repository code has grown around Postgres behavior.
- Tauri sidecar packaging may be harder than Electron.
- SQLite parity work may expose implicit Postgres assumptions in tests and repository functions.
- Secret storage may need a second pass if secure platform storage is not available immediately.

## Decision

Proceed with SQLite/local desktop mode as the product direction.

Do not ship a Postgres sidecar desktop app unless SQLite work proves unexpectedly large and a temporary internal demo is needed. The public desktop app should remove setup friction, not hide infrastructure complexity behind a launcher.
