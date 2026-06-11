---
title: Troubleshooting
description: Common ANIP setup, generation, Registry, Studio, and runtime issues.
---

# Troubleshooting

Use this page when a command fails and you need to decide whether the problem is environment setup, package trust, generated code, runtime behavior, or scenario expectations.

## Fast triage

Start by identifying the failing layer:

| Symptom | Likely layer | First check |
| --- | --- | --- |
| CLI cannot find a package | Registry URL or package identity | Registry API base must end with `/registry-api/v1`. |
| Package verifies locally but not from Registry | Trust/lock mismatch | Compare package digest, key id, and Registry mode. |
| Generated service starts but agent gets `401` | Runtime token flow | The agent app must request an ANIP token from the selected service before invocation. |
| Studio cannot publish | Review/readiness/Registry trust | Check PM approval, release lineage, publish token, and trusted Registry key id. |
| Registry container starts then exits | Database/env/signing config | Check `ANIP_REGISTRY_DATABASE_URL`, migrations, and signing key env. |
| Hosted Studio allows writes when it should not | Deployment mode | Confirm `STUDIO_READ_ONLY=1` and mutation routes are blocked. |
| One language behaves differently from another | Generator/runtime parity | Compare manifest shape and run generator conformance before scenario banks. |

Do not fix product-specific behavior by adding phrases to shared runtime libraries. Shared ANIP code should implement protocol behavior. Domain interpretation belongs in the contract, scenario evidence, or custom implementation material.

If you are stuck after the first triage pass, ask in the [ANIP Discord](https://discord.gg/5Kx7tWUF) with the command, package/version, target language, and relevant diagnostics. For durable bugs or missing docs, open a [GitHub issue](https://github.com/anip-protocol/anip/issues).

## CLI cannot find a package

Symptoms:

```text
package not found
404 from /registry-api/v1
```

Check:

- Registry URL ends with `/registry-api/v1`.
- Package ID and version are correct.
- Registry is running.
- The package was published to this Registry, not another local database.

Useful commands:

```bash
curl http://127.0.0.1:8200/registry-api/v1/packages
anip verify --registry-url http://127.0.0.1:8200/registry-api/v1 --package my-service@0.1.0
```

## CLI version or spec version looks wrong

Symptoms:

```text
unsupported spec version
expected anip/0.24
unknown field resolution
```

Check:

- CLI version is current.
- The package targets `anip/0.24`.
- Studio and Registry are running strict `anip/0.24` paths, not old local data.
- You are not generating from an old local bundle that predates input resolution.

Useful commands:

```bash
anip --version
anip verify --package-bundle ./package.anip-package.json
```

The CLI, Studio, and Registry have their own product versions. The ANIP protocol target is separate.

## Lock verification fails

Symptoms:

```text
manifest digest mismatch
definition digest mismatch
registry key mismatch
```

Meaning:

- The package at that ID/version is not the same artifact the lock expects.
- You are pointing at the wrong Registry.
- The package was republished incorrectly.
- The lock is stale.

Fix:

- Confirm the expected package digest in Registry.
- Regenerate the lock only if you intentionally accept the new artifact.
- Do not bypass lock failures in CI.

## Package or template publish fails

Symptoms:

```text
publish token missing
publisher not authorized
registry mode mismatch
trusted key mismatch
template targets newer spec
```

Check:

- `ANIP_REGISTRY_PUBLISH_TOKEN` is configured for Registry direct publishing.
- `STUDIO_REGISTRY_PUBLISH_TOKEN` is configured for Studio-mediated publishing.
- `STUDIO_REGISTRY_URL` points at the Registry API route, not the UI route.
- `STUDIO_REGISTRY_REQUIRED_MODE` matches the Registry mode.
- `STUDIO_REGISTRY_TRUSTED_KEY_ID` matches the Registry signing key id.
- Starter templates target a spec version that this Studio build supports.

For public registries, do not work around this by changing package metadata after publication. Publish a new package or template revision.

## Registry fails to start

Symptoms:

```text
initialize registry store: connect to postgres
cannot parse "${registry-db.DATABASE_URL}"
failed health checks
dial tcp ... connect: connection refused
```

Check:

- `ANIP_REGISTRY_DATABASE_URL` is the actual resolved Postgres connection string.
- Platform placeholders are not passed literally to the container.
- The managed Postgres database is attached to the app or reachable from the network.
- SSL mode matches the provider requirement.
- `ANIP_REGISTRY_ED25519_PRIVATE_KEY` is a base64 Ed25519 seed and is stored as a secret.
- `ANIP_REGISTRY_RUN_MIGRATIONS=1` for the first single-instance deployment, or a migrate-only job has already run.

Useful checks:

```bash
curl https://registry.example.com/registry-api/v1/readyz
curl https://registry.example.com/registry-api/v1/metrics
```

If tables are not created, look at run logs before health-check logs. Health checks often only show that the process never became ready; the run log usually contains the database or config error.

## Registry UI loads but root path does not redirect

Symptoms:

```text
https://registry.example.com opens a blank route or 404
https://registry.example.com/registry works
```

Fix:

- Configure the Registry server or ingress to redirect `/` to `/registry`.
- Keep `/registry-api/v1` routed to the same Registry service.
- Do not put the API behind the static UI rewrite rule.

## Registry shows old or wrong data

Check:

- You are connected to the intended database.
- Local compose volumes were not reused accidentally.
- `ANIP_REGISTRY_SEED_DEMO=0` for production unless demo data is intentional.
- Package IDs and versions are immutable; publishing a corrected artifact requires a new version.
- Browser cache is not hiding a freshly deployed UI.

For a clean local Registry database:

```bash
cd registry
docker compose down -v --remove-orphans
docker compose up --build
```

Do not run this against a production database.

## Generated service exposes different capabilities

Symptoms:

- Python, TypeScript, Go, Java, and C# generated outputs have different capability IDs.
- A custom bundle changes `kind`, required inputs, side-effect posture, or approval metadata.

Cause:

- Generator drift.
- Custom bundle mutating public declaration metadata.
- Different package versions.

Fix:

- Compare package digest and contract signature.
- Run generator conformance/parity tests.
- Remove runtime metadata overrides.
- Put domain-specific behavior in custom execution code, not manifest mutation.

If one generated target exposes a composed capability as `atomic` while another exposes it as `composed`, treat that as a parity bug unless the signed contract itself differs. Custom bundles may optimize execution, but they must not rewrite the public manifest.

## Generated service does not build

Check:

- Target language dependencies are installed.
- The generated service was created from the same package version and custom bundle revision.
- Framework variant is supported for the target language.
- Custom bundle namespace/package names match generated package names.
- The bundle report did not show blocked file overlays.

Useful commands:

```bash
anip generate --package-bundle ./package.anip-package.json --target typescript --output /tmp/anip-service --force
anip verify --package-bundle ./package.anip-package.json
```

If the generated service fails only after applying a custom bundle, inspect `custom-code-bundle-report.json` first. The generator should preserve generated substrate files and only overlay declared extension seams.

## Generated service returns `401 Unauthorized`

Symptoms:

```text
Client error '401 Unauthorized' for url 'http://service:4100/anip/tokens'
```

Check:

- The agent app is calling the correct service endpoint.
- The service token endpoint is enabled.
- The bootstrap/API key expected by the service is configured in the agent app.
- Service-to-service URLs inside Docker Compose use container names, not host-only `127.0.0.1`.
- You did not mix host ports and compose-internal ports.

For GTM showcase stacks, the agent should not ask the user to pick a service manually. It should discover capabilities, select the service, obtain a token, and invoke the capability.

## Service returns `clarification_required` unexpectedly

Check:

- Is the missing field required?
- Does the input declare `resolution.mode`?
- Is `on_missing` configured to clarify?
- Is this a follow-up turn that should preserve prior capability context?
- Is the test expecting approval when the contract says clarification?

Do not patch generic runtime code with domain-specific phrases. If the behavior is real and portable, update the contract. If it is domain-specific, implement it in custom code.

For `anip/0.24`, pay special attention to input resolution:

- `resolution.mode=clarify` means missing or unresolved input should ask the caller.
- `resolution.mode=actor_policy_or_explicit` may use actor policy when the user omits a scope.
- `resolution.mode=backend_resolved` means the service owns lookup/resolution.
- `resolution.mode=closed_values` should use declared values and defaults.

If a test expects approval without an explicit required input, verify the contract actually says that input is backend-resolved or derived. Do not make the planner guess around a required public input.

## Service returns `approval_required` but continuation fails

Check:

- Approval grant references the same approval request.
- Parameters digest matches.
- Capability ID matches.
- Grant is not expired.
- One-time grant was not already used.
- Session-bound grant is used in the same session.
- Approver identity is allowed by policy.

Approval should not be modeled as a loose string parameter. Use ANIP approval request/grant flow.

## Follow-up turns select the wrong capability

Symptoms:

- First turn asks a clarification.
- Second turn supplies the missing value.
- Planner selects a different capability because the previous assistant message mentioned another concept.

Check:

- Follow-up state preserves the prior selected capability and pending input.
- The planner receives continuation context separately from user intent.
- Previous assistant text is not treated as new user intent.

This is a runtime planning issue, not a reason to add more domain phrases to the contract.

## Studio says coverage is incomplete

Meaning:

- Product Design baseline contains items not mapped to Developer Definition sections.

Fix:

- Open Developer Design coverage mapping.
- Map every Product Design item to explicit capability, policy, scenario, risk, or non-goal sections.
- Regenerate or save Developer Definition after fixing coverage.

Do not publish by ignoring coverage errors. Coverage is how Studio proves Product Design did not get lost before generation.

## Studio project created from a template still takes work

Expected:

- Templates are safe starters, not pre-approved behavior contracts.
- Sensitive source docs may be omitted during template export.
- Studio still needs review, coverage, validation, and publication.

Check:

- Template spec version is compatible with the Studio spec target.
- Imported Markdown source docs are present if the template included them.
- Product Design and Developer Definition diagnostics are resolved.
- PM approval exists for the selected release lineage.

If a template silently imports private source material or targets a newer spec than Studio supports, that is a bug.

## Studio is public but still allows mutation

Symptoms:

- Public demo users can create projects.
- Assistant endpoints run from hosted demo.
- Package or template publication is possible from public Studio.

Fix:

- Set `STUDIO_READ_ONLY=1`.
- Use a read-only reason so the UI explains why actions are blocked.
- Confirm mutation API routes are blocked, not just hidden in the UI.
- Do not configure assistant/provider keys in public read-only demos unless the deployment intentionally supports them.

Public Studio should be for browsing seeded projects, packages, templates, and evidence. Internal Studio can be write-capable behind SSO or network controls.

## Studio assistant has no key

Symptoms:

```text
LLM key missing
```

Fix:

- Configure the assistant model/key in the environment or Studio settings.
- Use the intended assistant model for project drafting.
- Do not use test/evaluation model settings as Studio authoring settings unless that is intentional.

Keep API keys out of source documents, packages, templates, and commits.

## Studio assistant uses the wrong model

Check:

- Studio authoring uses `STUDIO_ASSISTANT_MODEL=gpt-5.4` or the intended high-quality authoring model.
- Simulator and generated-service tests use their own model settings, such as `STUDIO_SIMULATOR_MODEL`.
- Agent showcase testing can use a smaller model independently.

Do not reuse the GTM agent test model as the Studio project-authoring model unless that is an explicit quality tradeoff.

## Registry page loads but package metadata looks wrong

Check:

- Package README is generic and package-specific, not copied from another showcase.
- Source links are HTTP(S), portable, and safe.
- No machine-local Studio URLs are present.
- Custom bundle refs are immutable and digest-pinned.
- Agent readiness findings are shown as consumer guidance, not internal Studio diagnostics.

If metadata changes, publish a new package revision. Do not mutate signed package metadata in place.

## Package readiness is below 100

Meaning:

- Registry has at least one verifier/readiness finding.
- The number is a readiness score, not a runtime success percentage.

Check:

- Findings are shown as consumer-facing guidance.
- Findings avoid Studio-only wording.
- Optional inputs that affect business scope have defaults, clarification rules, or service-owned resolution.
- The finding maps to a specific capability/input.

Fix the contract and publish a new package revision when the finding affects consumer behavior.

## Docker cannot connect

Symptoms:

```text
permission denied while trying to connect to docker.sock
Cannot connect to the Docker daemon
```

Check:

```bash
docker ps
docker context show
docker context ls
```

Fix:

- Start Docker Desktop or OrbStack.
- Ensure the active context points to the running daemon.
- Remove stale containers only when they are known to belong to the ANIP local stack.

## Docker ports or stale services are confusing

Symptoms:

- A test hits the wrong service.
- Old compose stack responds on an expected port.
- Multiple language showcase stacks are running at once.

Check:

```bash
docker ps
docker compose ps
docker logs <container>
```

Fix:

- Stop stale stacks before starting a new language showcase.
- Prefer compose project names that include the language or showcase.
- Use compose-internal service names for container-to-container calls.
- Use host ports only for browser/UI entry points.

Do not assume a passing request means the current service is correct; confirm image tag, package version, and compose project.

## Scenario bank is slow

Expected:

- Full LLM-dependent scenario banks can be slow.
- Use phase-sized runs for debugging.
- Use full banks as release gates.

Check:

- Runtime is not loading duplicate manifests.
- Services are not misconfigured to point multiple aliases at one endpoint unless intended.
- Planner brief is compact and deduped.
- Manifest is cached safely by digest and expiry.

## Scenario bank fails in one language

Do not patch the failing phrase first. Compare layers in this order:

1. Same package digest and contract signature?
2. Same generated manifest capability count and shape?
3. Same custom bundle revision?
4. Same runtime planning brief?
5. Same follow-up/approval continuation behavior?
6. Same backend data and service URLs?

Only after those match should you debug language-specific execution code.

## Fronting smoke cannot reach backend API

Check:

- Env file exists outside the repository.
- Token has the minimum scopes for the smoke.
- Mutation flag is explicitly enabled for write tests.
- Resource IDs point at test projects/channels/pages/databases only.
- The downstream account shared the resource with the integration.

Typical local env files:

```text
/tmp/anip-jira.env
/tmp/anip-slack.env
/tmp/anip-github.env
/tmp/anip-gitlab.env
/tmp/anip-linear.env
/tmp/anip-notion.env
```

Do not commit these files or paste their secrets into docs.

## Fronting service behaves like raw API or MCP

That is a design problem.

Check:

- Capability names describe governed business actions, not raw backend operations.
- Mutations have preview/approval behavior where appropriate.
- Sensitive scopes are explicit.
- Backend options are named governed inputs, not invisible pass-through bags.
- Native API or MCP details are implementation metadata, not the agent-facing product contract.

Fronting should make Jira, Slack, GitHub, GitLab, Linear, Notion, or Superset safer for agents. It should not merely rename backend tools.

## Superset fronting exposes raw SQL

For the showcase, this should be treated as a boundary issue.

Preferred posture:

- Agent-facing capabilities are governed analytics actions.
- Raw `execute_sql` is not the public ANIP capability boundary.
- Dataset, metric, grain, chart preview, and publish approval rules are explicit.
- Backend execution can use Superset REST/native APIs or provider-owned semantic execution.

If a package implies `execute_sql` behind a broad `analytics.answer_question` capability, revise the contract/package metadata.

## What to include in a bug report

Include:

- ANIP spec version.
- CLI version.
- Package ID/version and digest.
- Target language/framework.
- Registry URL if relevant.
- Exact command.
- Error output.
- Whether this is conformance, contract test, scenario validation, Studio, Registry, or generated runtime.
- Whether custom bundles were used.

Do not include:

- API tokens.
- Private source documents.
- Unredacted customer data.
- Local env files.
