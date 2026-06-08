# ANIP Public Release Readiness Plan

Date: 2026-05-14

This plan tracks the work needed before pushing the current ANIP platform public. The goal is a practical first public release that people can install, run locally, inspect through hosted demos, and use to generate governed ANIP services.

## Release Principles

- Public artifacts must be reproducible from repository state, not hand-built local output.
- Registry and Studio demo deployments must be safe by default. Public Studio must be read-only.
- Showcase apps must be generated from Studio-produced contracts, not manually divergent service definitions.
- GTM language parity means native ANIP services in each supported language, not proxy wrappers around another language implementation.
- GTM custom bundles must preserve the signed public manifest exactly; implementation shortcuts may fill execution seams but must not rewrite declaration shape, inputs, scopes, grant policy, side effects, or composition metadata.
- Custom implementation bundles stay outside the signed behavior contract unless attached as immutable implementation material with a digest.
- Local compose stacks should be useful without requiring private credentials.
- Hosted demos should expose browsing and learning surfaces, not mutation surfaces.

## Phase 0: Stabilize Current Branch

Status: in progress

Tasks:

- Keep the v0.24 strictness changes for Registry and Studio isolated from generated test output.
- Confirm no ignored generated artifacts are required for release.
- Commit the v0.24 strictness work before starting broad release packaging work.
- Rebase or merge main only after the working tree is clean.

Release gate:

- Registry validation tests pass against ANIP spec 0.24 only.
- Studio validation tests pass against ANIP spec 0.24 only.

## Phase 1: CLI Distribution

Status: implemented, pending release-run validation

Existing assets:

- `packages/go/scripts/build-anip-cli.sh` already builds:
  - `darwin/amd64`
  - `darwin/arm64`
  - `linux/amd64`
  - `linux/arm64`
  - `windows/amd64`
  - `windows/arm64`
- Windows archives include `.cmd` compatibility wrappers.
- `packages/go/homebrew/anip.rb.template` already exists.
- Release workflow builds CLI archives, attaches checksums and the rendered formula to the GitHub release, and optionally pushes `Formula/anip.rb` to `anip-protocol/homebrew-anip` when `HOMEBREW_TAP_TOKEN` is configured.
- Local dry run:
  - `DIST_DIR=/private/tmp/anip-cli-dist ANIP_CLI_BUILD_CACHE=/private/tmp/anip-cli-cache packages/go/scripts/build-anip-cli.sh 0.0.0-test`

Tasks:

- Confirm `HOMEBREW_TAP_TOKEN` is configured with write access to `anip-protocol/homebrew-anip`.
- Run the release workflow in dry-run or prerelease mode before public launch.

Release gate:

- `anip version`, `anip generate --help`, and `anip validate --help` work from every archive.
- Homebrew formula installs on macOS arm64 and validates the installed CLI.

## Phase 2: Registry Image, Compose, And Deployment

Status: partially implemented

Tasks:

- Add a Registry Docker image build path if one does not already exist. Done: `registry/Dockerfile`.
- Add a local Registry compose file with all required dependencies. Done: `registry/docker-compose.yml`.
- Provide a clean database bootstrap/reset path for local use. Done: `docker compose down -v --remove-orphans` and `registry/scripts/smoke-compose.sh`.
- Add Registry image build and publish to CI. Done: release workflow publishes `anipprotocol/registry`.
- Add deployment documentation for external Registry hosting.
- Keep package and template storage separated in the Registry UX and API.
- Keep Registry at ANIP spec 0.24 only for this release.

Release gate:

- `docker compose up` starts a clean local Registry. Verified locally.
- `registry/scripts/smoke-compose.sh` resets the Registry database, builds the image, runs the trust-loop smoke, and cleans up.
- Registry can publish, browse, download, and lock a package.
- Registry can publish, browse, and import a starter template.
- Registry rejects non-0.24 service definitions and templates.

## Phase 3: Studio Image, Read-Only Mode, And Deployment

Status: partially implemented

Existing assets:

- `studio/server/Dockerfile`
- `studio/Dockerfile`
- `studio/Dockerfile.standalone`
- `studio/docker-compose.yml`
- `STUDIO_READ_ONLY` support exists in assistant configuration code.

Tasks:

- Audit read-only coverage across every Studio API mutation route.
- Add a server-side write guard that blocks project, document, assistant, package, template, and publication mutations in read-only mode. Done for API mutation methods plus assistant/workbench invocation routes.
- Update UI to hide or disable mutating actions when read-only mode is enabled.
- Remove dogfooding-only logic from public Studio builds. Done in assistant/workbench service implementation.
- Add a local Studio compose file with all dependencies. Done: `studio/docker-compose.yml`.
- Add an option to seed showcase projects at startup. Done: `STUDIO_SEED_SHOWCASES`.
- Add a hosted-demo deployment mode that is read-only and preseeded. Done locally via `STUDIO_READ_ONLY=1 STUDIO_SEED_SHOWCASES=1`.
- Publish separate Studio API and web images. Done in release workflow as `anipprotocol/studio-api` and `anipprotocol/studio-web`; `anipprotocol/studio` remains a web-image compatibility alias.
- Add a repeatable read-only compose smoke. Done: `studio/scripts/smoke-compose.sh`.

Release gate:

- Public Studio can browse projects, contracts, packages, templates, and docs.
- Public Studio cannot create, update, delete, publish, generate, invoke assistant, or mutate registry state. Mutation guard smoke-verified with 403 for workspace creation.
- Local Studio compose can run with or without showcase seeds. Verified read-only seeded compose locally.
- `studio/scripts/smoke-compose.sh` resets the Studio database, starts read-only seeded compose, checks API/UI reachability, verifies seeded projects, verifies representative 403 mutation guards, and cleans up.

## Phase 4: Showcase Seeds

Status: implemented locally; fronting starter seeds and package bundles verified locally

Required Studio seeds:

- GTM Agent project.
- Jira fronting project.
- GitHub fronting project.
- Slack fronting project.
- Notion fronting project.
- Linear fronting project.
- Slite fronting project.
- GitLab fronting project.
- Superset fronting project.

Tasks:

- Ensure every seeded project is created through the same project/template/import path users can use.
- Ensure seeded projects are safe to publish publicly.
- Include source documents that are useful but not private. Done for Jira, GitHub, Slack, Notion, Linear, Slite, GitLab, and Superset fronting starters.
- Include canonical generated contracts and registry packages for the showcase projects. Done for Jira, GitHub, Slack, GitLab, Linear, Notion, Slite, and Superset fronting packages using `anip package build-local`.

Release gate:

- Fresh local Studio with showcase seeding can browse the full GTM project and fronting projects. Fronting starter seed smoke verified for Jira, GitHub, Slack, Notion, Linear, Slite, GitLab, and Superset projects in workspace `ws-fronting-starters`.
- Fronting package bundles verify with signed local development Registry receipts for Jira, GitHub, Slack, GitLab, Linear, Notion, Slite, and Superset.
- Read-only hosted Studio can browse the same state.

## Phase 5: GTM Agent Language Stacks

Status: partially implemented; committed parity baseline promoted; full-stack compose smoke verified

Target languages:

- Python
- TypeScript
- Go
- Java
- C#

Tasks:

- Generate each language implementation from the same GTM contract produced by the Studio seed.
- Keep each implementation self-contained and native to that language.
- Create one compose file per language stack. Done: `examples/showcase/gtm/docker-compose.language-parity-{python,typescript,go,java,csharp}.yml`.
- Include required data services, BI surface, agent question UI, and approval UI.
- Add Keycloak or another OAuth2 provider if it can be included without making the first release brittle.
- Keep the original hand-written Python showcase only as reference material, not as the parity target.
- Use `examples/showcase/gtm/generated/language-parity/` as the committed apples-to-apples generated baseline. Done: Python, TypeScript, Go, Java, and C# source/config trees promoted from the latest same-contract generated outputs with generated keys, dependency directories, build outputs, and caches excluded.
- Publish a reproducible strict `anip/0.24` GTM showcase package. Initial baseline: `gtm-pipeline-q2-review@0.4.0`. Current release baseline: `gtm-pipeline-q2-review@0.4.3` in `examples/showcase/gtm/registry-packages/`, generated from the promoted language-parity service definition and verified before registry publication.
- Add a reusable full-stack smoke gate. Done: `examples/showcase/gtm/scripts/smoke-language-compose.sh` uses dynamic host ports, starts a language compose stack, verifies all four service discovery documents, checks the 23-capability union, verifies agent runtime JSON, verifies the agent UI route, and tears the stack down.

Release gate:

- Each language stack starts locally through Docker Compose. Full-stack compose smoke verified for Python, TypeScript, Go, Java, and C# across all four generated services plus the agent UI.
- Each language stack exposes equivalent ANIP manifests. Current promoted baseline has 23 formalized capabilities and identical capability-id sets across all five languages.
- Public manifest shape stays identical to the signed contract; GTM custom bundles may fill execution seams but must not mutate declaration shape.
- GTM question-bank gates pass consistently for each language where the LLM-dependent test infrastructure is enabled.

## Phase 6: External Custom Bundles

Status: partially implemented; local bundle catalog and digest verification smoke complete

Tasks:

- Define the public bundle repository layout. Done locally in `examples/showcase/gtm/custom-code-bundles/README.md`: one GTM bundle set with five native language folders is the first-release shape.
- Decide whether first release uses one repository with five language folders or five separate repositories. Current recommendation: one repository with five folders for the GTM showcase bundle set, because the folders share one signed contract and one package lineage.
- Add bundle manifests with digestable immutable contents. Done locally in `examples/showcase/gtm/custom-code-bundles/bundle-catalog.json` with normalized tree digests for Python, TypeScript, Go, Java, and C# native bundles.
- Document how a package revision references a bundle via immutable ref and digest. Done in the GTM custom-bundle README using `anip package attach-implementation`.
- Ensure the generator can consume local bundles and digest-pinned remote bundle refs without automatic unsafe fetching. Done for local bundles and metadata-only remote refs; remote fetch remains explicitly disabled unless a future opt-in fetcher is implemented.

Release gate:

- A user can generate a GTM service implementation from the package plus an explicit local bundle. Verified by `examples/showcase/gtm/scripts/verify-custom-bundles.sh` for all five native language bundles.
- A user can validate a remote bundle ref digest before use. CLI validates immutable ref shape and records metadata; local tree digest verification is enforced through `--verify-custom-code-bundle-digest`.

## Phase 7: Fronting From CLI

Status: partially implemented; starter-to-scaffold CLI path added

Tasks:

- Ensure `anip` can create fronting service scaffolds without Studio. Done: `anip fronting scaffold --starter <starter.json> --target <language> --output <dir>`.
- Support OpenAPI, GraphQL, and MCP-derived starter inputs where practical. First pass supports a small reviewed `anip-fronting-starter/v0` JSON shape; OpenAPI/GraphQL/MCP discovery import can layer on later.
- Keep downstream integration details as generator inputs or implementation templates, not as core ANIP behavior truth.
- Generate integration extension templates for REST, GraphQL, MCP, dbt, Cube, Databricks, Snowflake, and similar seams.

Release gate:

- A user can run a CLI command that creates a fronting service scaffold from a starter input. Verified with a Jira-style starter JSON.
- The generated scaffold validates against ANIP 0.24 and clearly marks implementation extension points. Verified with `anip validate`; generated output includes `integration-fronting/adapter-bindings.json`, backend profile/selection examples, conformance evidence, and backend templates.

## Phase 8: Documentation

Status: not complete

Required documentation:

- ANIP 0.24 protocol changes, especially input resolution.
- CLI install and release artifact usage.
- Homebrew install flow.
- Registry package and template publishing.
- Registry lock files and trust model.
- Studio Autopilot Mode flow.
- Studio Guided Mode flow.
- Studio fronting express flow.
- Starter templates and safe template export/import.
- Custom code bundles and digest-pinned bundle refs.
- Showcase apps and local compose usage.
- Scenario-driven execution design.
- Execution scenario validation.
- Generated service extension templates.

Release gate:

- A new user can install the CLI, run Registry locally, run Studio locally, browse hosted demos, generate a service, and understand where customization belongs.

## Phase 9: Public Release Gates

Before publishing:

- Full CI matrix passes.
- Generator conformance passes across all supported languages and framework variants.
- Registry Docker smoke test passes.
- Studio Docker smoke test passes.
- Read-only hosted Studio mutation tests pass.
- GTM parity gates pass or are explicitly documented as LLM-dependent release gates.
- Docs site builds.
- Release workflow dry run succeeds.
- Homebrew formula dry run succeeds.

## Immediate Next Work

1. Commit current v0.24 strictness changes after final status review.
2. Verify the CLI/Homebrew release workflow with a prerelease or dry run.
3. Add Registry Docker/compose release path.
4. Add Studio read-only mutation guard and compose release path.
