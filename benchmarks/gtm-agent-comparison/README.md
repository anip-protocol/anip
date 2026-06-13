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

MCP-style skill/recipe 60-case stratified sample:

- `gpt-5.4`: `60/60` passed, average loops `3.55`, total loops `213`, total tokens `201,096`, cached-token ratio `0%`, average elapsed time `4552.51ms`.
- `gpt-5.4-mini`: `60/60` passed, average loops `3.55`, total loops `213`, total tokens `197,328`, cached-token ratio `0%`, average elapsed time `3442.69ms`.

The important observation is not only token count. The MCP-style baseline did not pass this sample from raw tool schemas alone. It required additional consumer-side guardrails to:

- deny `draft and send now`;
- stop provider-selected target drafting at the approval boundary;
- avoid silently mapping vague `Q2 candidates` to a cohort;
- avoid selecting read-only tools for compound approval-gated requests;
- prevent final-response overclaims such as saying a draft was sent.

That is the implementation burden ANIP is designed to move from every agent consumer into the service-owned capability contract.

MCP-style skill/recipe full-bank iteration:

- Initial `gpt-5.4-mini` full-bank run: `516/540` passed.
- The `24` failures were not ANIP failures; they were consumer-side recipe/guardrail gaps: scope restriction classification, unknown entity handling, temporal parsing, vague cohort repair, compound flow policy, and final-response overclaims.
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

This is an important benchmark artifact: making the MCP-style path reliable means building and maintaining additional agent-side execution semantics that are not provided by the raw tool schema.

The fair conclusion from this GTM suite is precise:

- `gpt-5.4-mini` can pass the GTM task bank for both approaches.
- The MCP-style path only reached `540/540` after substantial consumer-side guardrails were added around raw tools.
- The ANIP path passed through provider-owned capability contracts, generated services, and service-side governance semantics.
- This suite proves governance-location and repair-burden differences more directly than model-tier differences.

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
- Add a hard-mode benchmark suite that does not modify the published GTM Agent package. It should push ambiguous multi-step planning, conflicting policies, tool-surface drift, and adversarial prompt pressure until `gpt-5.4-mini` struggles in the MCP-style path.
- Run hard-mode with `gpt-5.4-mini` and a stronger model to measure model-tier pressure separately from the current GTM showcase.
