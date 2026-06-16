# GTM Agent Benchmark

This benchmark compares two ways of letting an agent answer the same GTM questions:

- **ANIP agent:** the agent discovers governed capabilities, selects one declared capability, and the service enforces input resolution, permissions, approvals, denial, and audit.
- **MCP-style skill/recipe baseline:** the agent receives raw tool schemas plus client-side skills, recipes, and policy text. It must decide how to route, validate, stop, recover, or call tools from the consumer side.

The benchmark is intentionally separate from the GTM release-gate question-bank runner. The release gate proves the generated ANIP services behave correctly. This benchmark measures the operational cost of different consumption patterns.

## What We Measure

For each case, the runner records:

- selected model
- wall-clock latency
- agent loop count
- service/tool invocation count
- prompt/completion/total tokens when the runtime exposes usage
- estimated tokens from prompt character counts when usage is unavailable
- expected outcome versus observed outcome
- selected capability or tool
- failure type, if any

Do not publish cost claims until a run includes real token usage or a clearly stated pricing model. Estimated token counts are useful for engineering comparison, not billing claims.

## What The Baseline Is Testing

The MCP-style baseline intentionally does **not** consume ANIP manifests, ANIP capability metadata, ANIP runtime helpers, or ANIP service contracts.

It models the common alternative architecture:

- raw tools expose names, descriptions, and schemas;
- skills/recipes carry business routing, clarification, permission, approval, and denial guidance;
- the agent implementation owns repair logic when the model chooses the wrong tool or overclaims an effect;
- backend tools execute raw operations without a provider-owned governed capability contract.

This is the comparison we want to measure. With ANIP, the service contract owns execution semantics. Without ANIP, the agent implementation team has to recreate those semantics in prompts, skills, recipes, validators, and post-planner guardrails.

Early sample runs exposed exactly that pressure: the MCP-style planner needed extra consumer-side logic to deny "draft and send now", stop provider-selected target drafting at approval, avoid silently mapping vague cohorts, and avoid selecting read-only tools for compound approval-gated requests.

## Baseline Guardrail Rules

The MCP-style baseline should not be tuned to pass every benchmark case at any cost. It is allowed to fail when the failure reflects a realistic limit of client-side skills, recipes, prompts, and guardrails.

Acceptable MCP-style guardrails are generic policy rules that an implementation team could defend outside this benchmark:

- require explicit quarters instead of resolving vague phrases such as "this quarter";
- clarify unknown cohorts instead of guessing the nearest known cohort;
- deny raw exports, external dispatch, or unsupported financial-detail requests;
- enforce actor scope and role boundaries;
- stop provider-selected target flows at clarification or approval boundaries;
- route known lead or account cohorts only when the user names a known cohort or uses an accepted synonym.

Do not add benchmark-specific branches for exact question strings, fixture-only phrasing, or one-off regression failures. If a failing case only passes by adding a phrase-shaped exception, keep the failure and record it as a weakness of the MCP-style approach.

## Start The GTM Showcase Stack

From the repository root:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.4-mini

cd examples/showcase/gtm
docker compose -f docker-compose.language-parity-python.yml up --build
```

The ANIP LLM agent defaults to:

```text
http://127.0.0.1:4310/api/ask
```

## Start The MCP-Style Skill/Recipe Baseline

From the repository root:

```bash
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-5.4
export DATABASE_URL=postgresql://anip:anip@localhost:5461/anip_gtm

python3 benchmarks/gtm-agent-comparison/agents/mcp_skill_agent.py
```

The baseline agent defaults to:

```text
http://127.0.0.1:9323/api/ask
```

It uses an OpenAI-compatible chat API for planning and final response formatting. It does not store API keys.

Run this baseline with the same model used by the ANIP showcase first, for example `gpt-5.4-mini`, so the first comparison is not biased by model tier. A separate hard-mode suite should then push beyond this GTM showcase to measure where the consumer-side skill/recipe approach starts requiring stronger reasoning.

## Run A Smoke Benchmark

```bash
python3 benchmarks/gtm-agent-comparison/scripts/run_http_agent_benchmark.py \
  --agent anip \
  --agent-url http://127.0.0.1:4310/api/ask \
  --cases benchmarks/gtm-agent-comparison/cases/gtm-smoke.json \
  --output-dir /tmp/anip-benchmark/anip \
  --pricing benchmarks/gtm-agent-comparison/config/openai-pricing.example.json
```

```bash
python3 benchmarks/gtm-agent-comparison/scripts/run_http_agent_benchmark.py \
  --agent mcp_skill_baseline \
  --agent-url http://127.0.0.1:9323/api/ask \
  --cases benchmarks/gtm-agent-comparison/cases/gtm-smoke.json \
  --output-dir /tmp/anip-benchmark/mcp-skill \
  --pricing benchmarks/gtm-agent-comparison/config/openai-pricing.example.json
```

The result JSON can be compared directly because both agents return the normalized fields used by the runner.

## Build The Full GTM ANIP Benchmark Suite

The checked-in GTM release gate is `350 + 140` questions:

- `350` broad question-bank entries in `docs/examples/gtm-showcase/question-banks/`
- `140` variation-bank entries in `docs/examples/gtm-showcase/variation-question-banks-v3/`

The benchmark suite also includes a 55-case multi-turn extension:

- the five original clarification follow-up entries from the 350 bank
- 50 generated two-turn clarification/resolution scenarios across pipeline, enrichment, outreach, prioritization, routing, forecast, bottleneck, and reassignment

```bash
python3 benchmarks/gtm-agent-comparison/scripts/build_gtm_benchmark_cases.py \
  --suite all \
  --output /tmp/anip-benchmark/gtm-540-cases.json
```

Run the resulting ANIP benchmark:

```bash
python3 benchmarks/gtm-agent-comparison/scripts/run_http_agent_benchmark.py \
  --agent anip \
  --agent-url http://127.0.0.1:4310/api/ask \
  --cases /tmp/anip-benchmark/gtm-540-cases.json \
  --output-dir /tmp/anip-benchmark/anip-540 \
  --pricing benchmarks/gtm-agent-comparison/config/openai-pricing.example.json \
  --timeout-seconds 180
```

Before running the full suite against the MCP-style baseline, run a stratified sample. The baseline can fail for two different reasons that should be kept separate:

- the raw backend/tool surface is missing functionality;
- the consumer-side skills/recipes are insufficient, ambiguous, or too brittle for the model to apply reliably.

Those failures are part of the measurement. They should not be silently patched into ANIP services.

## Compare Runs

```bash
python3 benchmarks/gtm-agent-comparison/scripts/compare_runs.py \
  --left /tmp/anip-benchmark/mcp-skill/mcp_skill_baseline-latest.json \
  --left-label mcp_skill_baseline \
  --right /tmp/anip-benchmark/anip/anip-latest.json \
  --right-label anip \
  --output /tmp/anip-benchmark/comparison.md
```

For public claims, fill `config/openai-pricing.example.json` with the exact provider pricing that applied at the time of the run and keep the pricing file with the run artifacts.

## Current Local Sample Results

These are engineering run notes, not final public benchmark claims.

ANIP full-bank reference:

- `540/540` passed against the generated GTM ANIP services.
- Average loops: `2.20`.
- Total loops: `1188`.
- Total tokens: `4,158,463`.
- Cached-token ratio: `75.41%`.
- Average elapsed time: `1366.76ms`.

ANIP compact-catalog optimization experiment:

- This is a local opt-in runtime experiment, not a protocol/package change.
- Enable with `ANIP_AGENT_COMPACT_CATALOG=true`.
- The runtime still loads the full ANIP catalog for validation and invocation, but sends only a locally retrieved compact candidate set to the planner.
- Naive top-12 retrieval passed smoke `7/7` but failed the 60-case stratified sample `58/60`, because “at risk” wording ranked approval-preparation capabilities above read-only risk summary.
- Top-16 retrieval passed the same 60-case stratified sample `60/60`.
- On the exact same 60 cases, full-catalog ANIP used `497,217` total tokens, compact top-16 ANIP used `179,443`, and the final MCP-style baseline used `199,808`.
- Top-16 retrieval also passed the full 540-case benchmark `540/540`.
- On the full 540-case benchmark, full-catalog ANIP used `4,158,463` total tokens, compact top-16 ANIP used `1,494,235`, and the final MCP-style baseline used `1,670,658`.
- Compact ANIP kept the same ANIP loop profile as full-catalog ANIP: average loops `2.20`, total loops `1188`.
- The engineering conclusion is that ANIP prompt/catalog packing is a real optimization opportunity. The compact routing result should still be treated as an opt-in runtime experiment until it is generalized beyond the GTM showcase.

MCP-style skill/recipe 60-case stratified sample:

- `gpt-5.4`: `60/60` passed, average loops `3.55`, total loops `213`, total tokens `201,096`, cached-token ratio `0%`, average elapsed time `4552.51ms`.
- `gpt-5.4-mini`: `60/60` passed, average loops `3.55`, total loops `213`, total tokens `197,328`, cached-token ratio `0%`, average elapsed time `3442.69ms`.

The important observation is not only token count. The MCP-style baseline did not pass this sample from raw tool schemas alone. It required additional consumer-side guardrails to:

- deny `draft and send now`;
- stop provider-selected target drafting at the approval boundary;
- avoid silently executing provider-selected target flows instead of stopping at the declared clarification or approval boundary;
- avoid selecting read-only tools for compound approval-gated requests;
- prevent final-response overclaims such as saying a draft was sent.

That is the implementation burden ANIP is designed to move from every agent consumer into the service-owned capability contract.

MCP-style skill/recipe full-bank iteration, before the generic-guardrail cleanup:

- Initial `gpt-5.4-mini` full-bank run: `516/540` passed.
- The `24` failures were not ANIP failures; they were consumer-side recipe/guardrail gaps: scope restriction classification, unknown entity handling, temporal parsing, provider-selected-target boundary handling, compound flow policy, and final-response overclaims.
- After adding those consumer-side rules, the targeted 24-case regression passed `24/24`.
- A second full-bank run exposed `14` remaining consumer-side policy gaps.
- A third full-bank run exposed `7` remaining gaps after targeted regression fixes.
- A fourth full-bank run exposed `2` remaining precedence gaps.
- Final `gpt-5.4-mini` full-bank run: `540/540` passed.
- Average loops: `3.31`.
- Total loops: `1785`.
- Total tokens: `1,670,658`.
- Cached-token ratio: `0%`.
- Average elapsed time: `2910.00ms`.

This is an important benchmark artifact, but it should be treated as a patched-to-green iteration rather than the final public baseline. It shows how much agent-side execution semantics can accumulate when the raw tool schema does not own governance.

MCP-style skill/recipe generic-policy cleanup:

- Removed exact benchmark-shaped branches such as one-off unknown cohorts, specific objection fixture names, and narrow continuation phrases.
- Replaced them with generic client-side policy rules for unknown cohorts, explicit-quarter requirements, raw/unsupported financial-detail denial, dispatch denial, known objection themes, explicit target continuation, account-context requests, and lead-scoring reads.
- Current full-bank mini run after cleanup: `536/540`.
- Preserved run note: `results/2026-06-16-mcp-cleaned-mini.md`.
- The current result should not be forced to `540/540` unless remaining failures expose a generic reusable policy gap. Otherwise, the failures are part of the measurement.

This is the safer public framing: making the MCP-style path reliable means building and maintaining additional agent-side execution semantics that are not provided by the raw tool schema, and some edge cases may remain brittle without moving policy to the service side.

The fair conclusion from this GTM suite is precise:

- `gpt-5.4-mini` can pass the GTM task bank for both approaches.
- The MCP-style path only reached `540/540` after substantial consumer-side guardrails were added around raw tools.
- The ANIP path passed through provider-owned capability contracts, generated services, and service-side governance semantics.
- This suite proves governance-location and repair-burden differences more directly than model-tier differences.

Hard-mode extension:

- Added `cases/gtm-hard-mode.json`, a 24-case suite for prompt injection, mixed safe/unsafe intent, actor-boundary pressure, provider-selected targets, approval bypass attempts, negated actions, and multi-turn ambiguity.
- Compact ANIP with `gpt-5.4-mini` passed `24/24`, average loops `2.33`, total loops `56`, total tokens `72,400`.
- MCP-style skill/recipe baseline with `gpt-5.4-mini` passed `20/24`, average loops `3.50`, total loops `84`, total tokens `75,162`.
- MCP-style skill/recipe baseline with `gpt-5.4` passed `19/24`, average loops `3.50`, total loops `84`, total tokens `76,968`.
- The failed MCP-style cases were consumer-side policy errors: draft-vs-send confusion, over-denial of safe draft-only requests, approval-bypass handling, provider-selected target continuation, and one safe-forecast/raw-SQL fallback conflict.
- The hard-mode result does not prove that a stronger model can never help. It shows that stronger reasoning alone is not a reliable substitute for provider-owned execution contracts when policy and recovery live in consumer prompts/recipes.

Mixed nano-to-mini routing experiment:

- The mixed runner first sends each request to a compact ANIP runtime using `gpt-5.4-nano`, then falls back to compact ANIP on `gpt-5.4-mini` only when the benchmark acceptance check fails.
- This is an engineering opportunity measurement, not a production routing policy. The fallback decision uses the benchmark's expected outcome oracle, so these results must not be presented as evidence that the runtime already has safe automatic nano-to-mini routing.
- A production mixed-model router must make the escalation decision from contract posture, requested effects, schema validity, confidence, clarification state, actor/scope boundaries, approval/denial/masking outcomes, and structured continuation state.
- On the hard-mode suite, mixed nano-to-mini passed `24/24` with `0` fallbacks.
- On the full 540-case benchmark, mixed nano-to-mini passed `540/540` with `7` fallbacks, a `1.3%` fallback rate.
- Full 540 mixed primary nano usage: `1,545,147` total tokens, `1,472,761` prompt tokens, `72,386` completion tokens.
- Full 540 mixed fallback mini usage: `18,492` total tokens, `17,736` prompt tokens, `756` completion tokens.
- Full 540 mixed total usage: `1,563,639` total tokens, `1,490,497` prompt tokens, `73,142` completion tokens.
- Full 540 mixed loop profile stayed the same as compact ANIP on mini: average loops `2.20`, total loops `1188`.
- Using the June 2026 list prices supplied for this benchmark (`nano` input `$0.20/M`, nano output `$1.25/M`, mini input `$0.75/M`, mini output `$4.50/M`), the measured suite cost was approximately `$0.4017`.
- For the same full 540 cases and the same pricing model, compact ANIP on mini was approximately `$0.9120`, full-catalog ANIP on mini was approximately `$1.2549`, and MCP-style on mini was approximately `$1.9031`.
- The practical conclusion is narrower: ANIP's structured service-owned outcomes make mixed-model routing worth implementing properly, but the production router still needs first-class runtime validators before this can become a public claim.

MCP-style mixed nano-to-mini comparison:

- The same mixed runner was also used against the MCP-style skill/recipe baseline, with `gpt-5.4-nano` as primary and `gpt-5.4-mini` as fallback.
- This uses the same benchmark-oracle fallback limitation as the ANIP mixed experiment.
- On the 60-case non-hard stratified sample, MCP-style mixed passed `60/60` with `6` fallbacks, a `10%` fallback rate, `240,341` total tokens, average latency `6018.70ms`, and total loops `213`.
- On the full 540-case non-hard benchmark, MCP-style mixed passed `540/540` with `22` fallbacks, a `4.07%` fallback rate, `1,831,222` total tokens, average latency `4592.92ms`, and total loops `1785`.
- Using the same June 2026 list prices, MCP-style mixed full-bank cost was approximately `$0.6858`.
- MCP-style mixed was cheaper than MCP-style mini-only by dollars, but not by tokens or latency: `1,831,222` tokens versus `1,670,658`, and `4592.92ms` average latency versus `2910.00ms`.
- MCP-style mixed did not fix hard-mode reliability. It passed `19/24` on hard-mode with `7` fallbacks, compared with MCP-style mini-only at `20/24` and MCP-style standard at `19/24`.
- The apples-to-apples conclusion is that mixed-model routing is possible in both approaches, but the economics differ. ANIP mixed used fewer tokens, fewer loops, lower latency, fewer fallbacks, and lower estimated cost because the smaller model consumed a compact governed capability contract instead of carrying policy and recovery behavior in consumer-side skills/recipes.

## Environment Variables

Use `OPENAI_API_KEY` and `OPENAI_MODEL` as the canonical benchmark variables.

The GTM showcase runtime also accepts `ANIP_AGENT_API_KEY` and `ANIP_AGENT_MODEL` for compatibility with the Docker compose examples. Do not set both unless you intentionally want the ANIP runtime to use different credentials or a different model than the recipe/tool baseline.

## Important Limits

This benchmark does not claim that every MCP implementation is inefficient or unsafe.

It compares:

- a service-owned ANIP contract path
- a consumer-owned MCP-style skill/recipe path for the same GTM task family

The point is to measure where routing, policy, clarification, and approval logic live. When that logic lives in the consumer prompt/recipe, the agent generally needs more prompt context, more reasoning, and more repair loops. When that logic lives in the service contract, the agent can be smaller and more bounded.

## Next Steps

- Add a summarizer that compares two run directories and produces a publishable table.
- Expand the hard-mode benchmark with tool-surface drift and additional adversarial recovery cases.
- Add a separate benchmark variant where the MCP-style baseline is allowed to keep iterating on consumer-side recipes, so we can measure maintenance cost and brittleness over time rather than only first-pass pass rate.
