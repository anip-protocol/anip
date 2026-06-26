# GTM Showcase

This is the implementation root for the flagship GTM ANIP showcase.

It is intentionally separate from the earlier showcase examples.

The goal is to build a serious end-to-end GTM stack the ANIP way:

- `design`
  - Studio with preloaded business and developer design artifacts
- `implement`
  - bounded ANIP services over real GTM datasets
- `validate`
  - implementation metadata and runtime evidence compared against the intended design
- `execute`
  - multiple agent runtimes consuming the same ANIP services

The polished public docs for this showcase live in:

- `website/docs/showcases/gtm-agent/`

The raw source, evidence, question-bank, and historical proof documents live in:

- `docs/examples/gtm-showcase/`

Repo-local operator runbooks live in:

- `examples/showcase/gtm/docs/`

## Intended Stack

- Postgres
- dbt
- Cube
- Metabase
- `gtm-pipeline-service`
- `gtm-enrichment-service`
- `gtm-prioritization-service`
- `gtm-outreach-service`
- Studio
- simple agent UI
- multiple agent runtimes

## Current State

This directory now contains the live four-service GTM stack:

- Postgres + Maven CRM dataset
- dbt models
- Cube semantic layer
- Metabase verification surface
- `gtm-pipeline-service`
- `gtm-enrichment-service`
- `gtm-prioritization-service`
- `gtm-outreach-service`
- one baseline agent runtime
- one manifest-aware agent runtime
- one generic LLM-driven ANIP runtime over live capability briefs
- Phase 6 forecast, bottleneck, sales-team, product-pipeline, and
  reassignment-preview expansions on the pipeline service

Current live execution split:

- dbt owns modeling and joins
- Cube is now used in the live request path for aggregate pipeline summaries
  and bounded forecast and stage-bottleneck summaries
- ANIP services keep governance, actor boundaries, approval flows, audit, and orchestration
- the LLM runtime stays thin: service discovery, capability selection, token issuance, one invocation, generic ANIP failure handling, and response rendering

The later service split is intentional:

- pipeline and enrichment are warehouse/data-access services
- prioritization and outreach demonstrate generated ANIP services with
  provider-owned custom bundles behind the contract boundary

## Showcase Entry Points

Each language stack runs the same contract shape with four generated ANIP
services, the LLM agent UI, Postgres, dbt, and bundled Metabase.

| Language | Compose file | Entry Page | Agent UI | Metabase Page | Metabase |
| --- | --- | --- | --- | --- | --- |
| Python | `docker-compose.language-parity-python.yml` | `http://127.0.0.1:4310/` | `http://127.0.0.1:4310/agent` | `http://127.0.0.1:4310/metabase` | `http://127.0.0.1:3041/` |
| TypeScript | `docker-compose.language-parity-typescript.yml` | `http://127.0.0.1:4320/` | `http://127.0.0.1:4320/agent` | `http://127.0.0.1:4320/metabase` | `http://127.0.0.1:3042/` |
| Go | `docker-compose.language-parity-go.yml` | `http://127.0.0.1:4330/` | `http://127.0.0.1:4330/agent` | `http://127.0.0.1:4330/metabase` | `http://127.0.0.1:3043/` |
| Java | `docker-compose.language-parity-java.yml` | `http://127.0.0.1:4340/` | `http://127.0.0.1:4340/agent` | `http://127.0.0.1:4340/metabase` | `http://127.0.0.1:3044/` |
| C# | `docker-compose.language-parity-csharp.yml` | `http://127.0.0.1:4350/` | `http://127.0.0.1:4350/agent` | `http://127.0.0.1:4350/metabase` | `http://127.0.0.1:3045/` |

The agent UI does not ask users to choose a backend service. It discovers the
ANIP catalog, chooses a bounded capability, obtains a scoped token, and lets
the selected service enforce the governed outcome.

The release contract for this showcase is validated against a 490-question
bank across the five generated runtime stacks.

Good first questions:

- `Show pipeline health for 2017-Q2 in the East region.`
- `Show pipeline health for 2017-Q2 with stage breakdown.`
- `Rank the top at-risk accounts for 2017-Q2 in the East region.`
- `Prepare follow-up tasks for the top at-risk accounts in 2017-Q2 for the East region.`
- `Score the inbound leads from last week.`
- `Route the inbound leads from last week to sales.`
- `Draft outreach for Acme Corporation with a follow-up objective.`
- `Draft outreach for the top expansion candidate in Q2.`
- `Show lookalike accounts for Acme Corporation.`
- `Export the raw CRM records for 2017-Q2.`

## BI Verification Surface

The showcase includes `Metabase` as a verification layer. Use the language
matrix above for the correct local port.

Use Metabase to validate the same modeled GTM slices the ANIP services expose,
without writing SQL joins by hand.

Recommended database connection inside Metabase:

- host: `gtm-postgres`
- port: `5432`
- database: `${POSTGRES_DB:-anip_gtm}`
- user: `${POSTGRES_USER:-anip}`
- password: `${POSTGRES_PASSWORD:-anip}`
- schema: `analytics_gtm`

The first curated BI tables are:

- `bi_gtm__pipeline_stage_summary`
- `bi_gtm__forecast_stage_summary`
- `bi_gtm__stage_bottlenecks`
- `bi_gtm__risk_accounts`
- `bi_gtm__sales_team_performance`
- `bi_gtm__product_pipeline`
- `bi_gtm__account_enrichment`

These are intentionally shaped around the same quarter, region, stage, manager,
product, account, and ranking concepts the ANIP services already use.

The compose stacks include a `gtm-metabase-setup` one-shot service that
initializes Metabase, connects it to the GTM warehouse, and creates the curated
verification questions/dashboard. If you need to rerun setup manually, use the
Metabase URL for the language stack you started:

```bash
GTM_METABASE_URL=http://127.0.0.1:3041 \
  python3 examples/showcase/gtm/scripts/setup_metabase_verification.py
```

Default local admin credentials for the scripted Metabase setup:

- email: `admin@anip.local`
- password: `Anip-Demo-Admin-2026!`

## Layout

- `docker-compose.yml`
- `.env.example`
- `dbt/`
- `data/`
- `services/`
- `generated/`
- `scripts/`
- `agents/`
- `ui/`
- `studio/`

## Generated vs Extensions

Generated service bundles under `generated/` are treated as disposable output.

- generic behavior belongs in Studio specs, generators, or the thin runtime shell
- domain-specific refinements belong in explicit extension modules such as `backend_extensions.py` and `service_extensions.py`
- scaffold regeneration recopies those extension modules from the source service directories so working behavior is not trapped in overwritten generated files

## LLM Runtime

The showcase includes an OpenAI-compatible ANIP LLM app at:

- `http://127.0.0.1:4310` when using the Python language-parity compose stack
- `http://127.0.0.1:4320` when using the TypeScript language-parity compose stack
- `http://127.0.0.1:4330` when using the Go language-parity compose stack
- `http://127.0.0.1:4340` when using the Java language-parity compose stack
- `http://127.0.0.1:4350` when using the C# language-parity compose stack

The UI supports:

- question entry against the live GTM ANIP services
- actor selection with demo GTM identities
- streamed runtime events for planning, invocation, and final ANIP result
- approval listing and approval recording for approval-gated preview flows
- audit loading from services that expose approval/audit surfaces

Run the Python generated-service showcase locally:

```bash
export OPENAI_API_KEY=...
export ANIP_AGENT_MODEL=gpt-5.4-mini

docker compose \
  -p anip-gtm-local \
  -f examples/showcase/gtm/docker-compose.language-parity-python.yml \
  up -d --build
```

Open the entry page:

```text
http://127.0.0.1:4310/
```

Open the focused agent UI directly:

```text
http://127.0.0.1:4310/agent
```

The bundled Metabase instance is available at:

```text
http://127.0.0.1:3041/
```

Stop:

```bash
docker compose \
  -p anip-gtm-local \
  -f examples/showcase/gtm/docker-compose.language-parity-python.yml \
  down
```

Required environment for real model planning:

- `ANIP_AGENT_MODEL`
- `ANIP_AGENT_API_KEY`
- `OPENAI_API_KEY` may be used instead of `ANIP_AGENT_API_KEY` in the compose stacks
- `ANIP_AGENT_SERVICES_JSON`

Optional:

- `ANIP_AGENT_BASE_URL`
- `ANIP_AGENT_TEMPERATURE`
- `ANIP_AGENT_TIMEOUT_SECONDS`
- `ANIP_AGENT_COMPACT_CATALOG=true` to send the planner a locally retrieved compact capability candidate set while retaining the full discovered metadata for validation and invocation
- `ANIP_AGENT_COMPACT_CATALOG_TOP_N=16` to tune the compact candidate set size
- `ANIP_AGENT_FALLBACK_MODEL` to enable a second planner model when the primary model output fails deterministic selection validation
- `ANIP_AGENT_FALLBACK_API_KEY` and `ANIP_AGENT_FALLBACK_BASE_URL` when the fallback model uses different credentials or a different OpenAI-compatible endpoint
- `ANIP_AGENT_ACTORS_JSON`
- `ANIP_AGENT_DEFAULT_ACTOR_ID`
- `ANIP_AGENT_APP_MODULE`

The LLM runtime does not ingest the full ANIP spec. It uses:

- a generic ANIP substrate for discovery, token issuance, invocation, approvals, and standard failures
- an optional GTM app profile for product framing
- a compact capability brief derived from live ANIP discovery and manifest data

Domain-specific service URLs and demo actor tokens are deployment configuration.
Hardcoded capability routing, GTM regex normalization, pre-call helpers,
workflow special cases, and benchmark stop logic do not belong in the generic
substrate. GTM prompt/framing and temporary app-level business-effect metadata
belong in `agents/llm_runtime/gtm_agent_app.py` until Studio publishes those
semantics in contract metadata.

## Custom Bundles

The generated services are built from the GTM ANIP contract plus reviewed
custom-code bundles under:

```text
examples/showcase/gtm/custom-code-bundles/
```

Those bundles hold implementation seams such as backend access, fixture-backed
policy behavior, actor profiles, approval handling, and language-specific
runtime glue. They should not change the public ANIP contract shape. To replace
the demo implementation with your own code, keep the contract and generated
service substrate, then replace the custom bundle implementation behind the
same extension points.

## Validation And Package Promotion

Do not promote a GTM package or showcase snapshot because one LLM question-bank
run passed. The release gate is layered:

1. Run service conformance directly against generated ANIP services, with no
   LLM planner.
2. Run deterministic routing conformance against the generated agent profile,
   with no model call.
3. Run adversarial governance checks for denial, approval, actor scope,
   masking, requested effects, and forbidden effects.
4. Run the LLM question bank as a pass-rate and failure-class benchmark.
5. Only then publish the Studio package, registry package, generated images,
   and showcase snapshot.

Hard-mode behavior must be represented in the Studio project, package metadata,
and custom bundles before it is treated as official showcase behavior. Runtime
patches that only repair a benchmark phrase should be quarantined until the
deterministic routing gate proves they are contract-derived.

## Running The 490-Question Gate

The 490-question gate is split into the original 350-question bank and the
140-question variation bank. Run it against the agent UI for the language stack
you started.

For Python:

```bash
python3 examples/showcase/gtm/scripts/generated_stack/run_question_bank.py \
  --runtime-url http://127.0.0.1:4310 \
  --all

OUT=output/gtm-variation-question-runs
mkdir -p "$OUT"
for phase in 1 2 3 4 5 6 7; do
  python3 examples/showcase/gtm/scripts/generated_stack/run_phase1_regression.py \
    --runtime-url http://127.0.0.1:4310 \
    --cases "docs/examples/gtm-showcase/variation-question-banks-v3/phase${phase}-variation-bank-20.json" \
    --output-dir "$OUT"
done
```

Use the corresponding agent UI port for the other language stacks:

- TypeScript: `http://127.0.0.1:4320`
- Go: `http://127.0.0.1:4330`
- Java: `http://127.0.0.1:4340`
- C#: `http://127.0.0.1:4350`
