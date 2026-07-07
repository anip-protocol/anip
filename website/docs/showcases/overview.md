---
title: Showcase Apps
description: Generated ANIP showcase projects for GTM, governed fronting, and introductory domains.
---

# Showcase Apps

ANIP showcases are designed to prove different adoption paths:

- Build a native ANIP service from scratch.
- Generate the same service in multiple languages.
- Put ANIP in front of existing systems.
- Publish packages to Registry.
- Run local stacks through Docker Compose.
- Validate behavior through scenario tests.

## Start From A Clean Machine

Most showcase commands assume you have cloned the ANIP repository and are
running from the repository root. If you are starting fresh:

```bash
git clone https://github.com/anip-protocol/anip.git
cd anip
```

For Docker Compose showcases, install Git and Docker with Docker Compose v2. The
GTM Agent UI also needs an OpenAI-compatible API key because it runs an actual
LLM-backed agent, not a canned response script.

For local service generation, install Go. Until published CLI binaries are
available for every platform, the docs use the repo-local CLI entry point:

```bash
cd packages/go
go run ./cmd/anip --help
```

If you have installed the `anip` CLI separately, replace
`go run ./cmd/anip` with `anip` in the examples.

If a showcase does not start cleanly, ask in the [ANIP Discord](https://discord.gg/5Kx7tWUF) and include the language stack, compose file, env file names, and the failing command. Do not share API keys or service tokens.

Useful source links:

| Area | Repository link |
| --- | --- |
| GTM showcase root | [examples/showcase/gtm](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm) |
| GTM Go Docker Compose file | [docker-compose.language-parity-go.yml](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/docker-compose.language-parity-go.yml) |
| GTM custom bundles | [examples/showcase/gtm/custom-code-bundles](https://github.com/anip-protocol/anip/tree/main/examples/showcase/gtm/custom-code-bundles) |
| GTM Registry package | [gtm-pipeline-q2-review-0.4.5.anip-package.json](https://github.com/anip-protocol/anip/blob/main/examples/showcase/gtm/registry-packages/gtm-pipeline-q2-review-0.4.5.anip-package.json) |
| Fronting showcase folders | [examples/showcase](https://github.com/anip-protocol/anip/tree/main/examples/showcase) |

## Model Choice Is Part Of The Proof

Studio authoring and showcase agent execution intentionally use different model tiers.

Studio project authoring was tested with `gpt-5.4` because authoring a governed contract is high-context design work: source interpretation, Product Design, Developer Design, diagnostics, composition, package material, and review readiness.

The showcase agents were intentionally validated with `gpt-5.4-mini` where an LLM is used for agent consumption. The GTM Agent runs its question-bank validation with `gpt-5.4-mini`, and the showcase consumption pattern is built around the same idea: the agent consumes already-governed ANIP services instead of inventing policy from a large prompt.

That is an ANIP advantage. If the package, manifest, input-resolution rules, approval boundaries, denial posture, and audit expectations are service-owned, the consuming agent has a smaller and safer action space. It can use a smaller model for routing, clarification, and invocation while the service still enforces authority and side effects.

This is not a promise that any small model works for every task. It is a design goal the showcases are meant to make visible: use stronger models for contract authoring when needed, then let smaller agents consume governed capabilities.

For the runtime architecture behind this pattern, see [Mixed Model Execution](/docs/concepts/mixed-model-execution). For current benchmark evidence and limitations, see [Benchmarks](/docs/testing/benchmarks).

## GTM Agent showcase

The GTM showcase is the deepest example. It models a revenue-operations agent that can answer pipeline, forecast, bottleneck, product pipeline, team performance, account risk, enrichment, outreach, follow-up, and routing questions through governed ANIP capabilities.

Key properties:

- Contract generated from Studio-produced project state.
- Strict `anip/0.24` package: `gtm-pipeline-q2-review@0.4.5`.
- Native generated services in five languages: Python, TypeScript, Go, Java, C#.
- Four-service topology.
- Agent UI for asking questions.
- Approval UI for gated behavior.
- Full-stack compose smoke for each language.
- Question-bank validation for LLM-dependent behavior.
- Custom bundles for language-specific implementation seams.

Before running the agent UI, configure an OpenAI-compatible key and model:

```bash
export OPENAI_API_KEY="sk-..."
export ANIP_AGENT_MODEL="gpt-5.4-mini"
```

Then run a language stack from the repository root:

```bash
examples/showcase/gtm/scripts/smoke-language-compose.sh python
examples/showcase/gtm/scripts/smoke-language-compose.sh typescript
examples/showcase/gtm/scripts/smoke-language-compose.sh go
examples/showcase/gtm/scripts/smoke-language-compose.sh java
examples/showcase/gtm/scripts/smoke-language-compose.sh csharp
```

The smoke verifies:

- All services start.
- Discovery documents are reachable.
- The 23-capability union is present.
- Agent runtime JSON is valid.
- Agent UI route is reachable.
- The stack tears down cleanly.

To keep a stack running locally instead of using the smoke script, use the
language-specific Docker Compose file. For example, the Go stack:

```bash
docker compose \
  -p anip-gtm-go-local \
  -f examples/showcase/gtm/docker-compose.language-parity-go.yml \
  up -d --build
```

Open `http://127.0.0.1:4330/` for the local entry page. It links to the Agent
UI, Metabase, runbook, and example questions.

For the full release-proof walkthrough, start with [GTM Agent Showcase](/docs/showcases/gtm-agent/overview), then see [GTM Language Parity](/docs/showcases/gtm-language-parity) for the five-language parity gate.

## Governed fronting showcases

Fronting showcases demonstrate ANIP as the governed layer in front of existing systems.

| Showcase | Backend posture | Package |
| --- | --- | --- |
| Jira | Native Jira REST API | `jira-fronting-showcase@0.2.3` |
| GitHub | Native GitHub REST/GraphQL APIs | `github-fronting-showcase@0.2.0` |
| Slack | Native Slack Web API | `slack-fronting-showcase@0.2.0` |
| GitLab | Native GitLab REST/GraphQL APIs | `gitlab-fronting-showcase@0.2.0` |
| Linear | Native Linear GraphQL API | `linear-fronting-showcase@0.2.0` |
| Notion | Native Notion API | `notion-fronting-showcase@0.2.0` |
| Superset | Native Superset REST API | `superset-fronting-showcase@0.2.0` |

These packages intentionally do not expose raw MCP tools as the ANIP behavior contract. MCP is useful as a comparison surface, but native APIs are the execution binding for these first-release showcase packages.

For a capability-by-capability walkthrough, see [Fronting Showcases](/docs/showcases/fronting) and the dedicated app pages for [Jira](/docs/showcases/fronting-apps/jira), [GitHub](/docs/showcases/fronting-apps/github), [GitLab](/docs/showcases/fronting-apps/gitlab), [Slack](/docs/showcases/fronting-apps/slack), [Linear](/docs/showcases/fronting-apps/linear), [Notion](/docs/showcases/fronting-apps/notion), and [Superset](/docs/showcases/fronting-apps/superset).

Generate one:

```bash
cd packages/go

go run ./cmd/anip generate \
  --package-bundle ../../examples/showcase/jira_fronting/registry-packages/jira-fronting-showcase-0.2.3.anip-package.json \
  --target python \
  --transport http,stdio \
  --dependency-source registry \
  --custom-code-bundle ../../examples/showcase/jira_fronting/custom-code-bundles/jira_fronting_python \
  --output ../../generated/jira-fronting \
  --force
```

If you have installed the CLI globally, use `anip generate ...` with the same
flags. Fronting live smokes also require provider-specific credential files
under `/tmp`; see [Fronting Showcases](/docs/showcases/fronting#test-credential-files).

The fronting showcase smokes prove:

- Package verification.
- Generated-service tests.
- Live read/preview behavior where backend credentials are configured.
- Approved mutation behavior where test credentials, explicit mutation flags, and approval grants allow it.
- The difference between contract parity, generated-service parity, adapter parity, and live backend parity.
- No stale MCP or hybrid backend refs in signed package metadata.

See [Fronting Showcases](/docs/showcases/fronting) for the validation levels used when describing whether a package is contract-ready, generated-service ready, adapter-ready, live-read ready, approved-mutation ready, or five-language live-adapter ready.

## Superset local stack

Superset is useful because people can run the backend locally:

```bash
cd examples/showcase/superset_fronting
./compose/setup.sh
cd ../../..
```

Then run the live smoke from the repository root:

```bash
set -a
source /tmp/anip-superset.env
set +a
PYTHONPATH="<generated src>:packages/python/anip-runtime-utils/src" \
  python3 examples/showcase/superset_fronting/scripts/live_smoke.py
```

The Superset package avoids raw SQL as an agent input. Governed analytics capabilities use bounded native API behavior such as catalog discovery, chart preview preparation, and dataset draft preparation.

## Introductory domain showcases

The original introductory showcases remain useful for understanding the protocol surface:

| Showcase | Domain | Key patterns |
| --- | --- | --- |
| Travel | Flight booking | Read vs irreversible, cost signaling, budget failure, audit. |
| Finance | Financial operations | High-risk actions, budget-bound delegation, restricted operations. |
| DevOps | Infrastructure operations | Transactional side effects, rollback, irreversible deletion. |

These examples are good for learning the protocol primitives. The GTM and fronting showcases are better for release-readiness and production-oriented architecture.

## What to inspect in a showcase

For any showcase, inspect:

- Source docs.
- Studio project or starter.
- Registry package.
- Service definition.
- Generated service output.
- Custom bundle.
- Live smoke scripts.
- Compose files.
- Scenario validation or question-bank evidence.

A showcase should teach where behavior belongs: in the contract and service enforcement, not in prompts or raw tool descriptions.

## Custom Bundle References

Registry packages can record immutable implementation-material refs such as
`git+https://...@<commit>#sha256:<digest>`. Today those refs are provenance and
verification metadata only. The CLI validates and reports them, but it does not
download or apply remote bundle code automatically.

For generation today, clone the repository and pass the reviewed local bundle
directory with `--custom-code-bundle`. This is intentional: implementation
material can run backend code, so it must be reviewed locally and pinned by
digest instead of fetched implicitly.
