# GTM Agent Benchmark

This benchmark compares two ways of letting an agent answer the same GTM questions:

- **ANIP agent:** the agent discovers governed capabilities, selects one declared capability, and the service enforces input resolution, permissions, approvals, denial, and audit.
- **Recipe/tool baseline:** the agent receives tool schemas plus client-side recipes/policy text and must decide how to route, validate, stop, or call tools from the consumer side.

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

## Initial Scope

The first baseline focuses on GTM prioritization and outreach questions because the repository already includes deterministic backend fixtures for those surfaces.

The ANIP agent can run broader GTM question banks. The recipe/tool baseline should only be scored on cases where equivalent raw tool fixtures exist.

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

## Start The Recipe/Tool Baseline

From the repository root:

```bash
python3 benchmarks/gtm-agent-comparison/agents/recipe_tool_agent.py
```

The baseline agent defaults to:

```text
http://127.0.0.1:9313/api/ask
```

It uses the same OpenAI-compatible chat API shape as the GTM ANIP agent. It does not store API keys.

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
  --agent recipe_tool_baseline \
  --agent-url http://127.0.0.1:9313/api/ask \
  --cases benchmarks/gtm-agent-comparison/cases/gtm-smoke.json \
  --output-dir /tmp/anip-benchmark/recipe-tool \
  --pricing benchmarks/gtm-agent-comparison/config/openai-pricing.example.json
```

The result JSON can be compared directly because both agents return the normalized fields used by the runner.

## Build The Full GTM ANIP Benchmark Suite

The checked-in GTM release gate is `350 + 140` questions:

- `350` broad question-bank entries in `docs/examples/gtm-showcase/question-banks/`
- `140` variation-bank entries in `docs/examples/gtm-showcase/variation-question-banks-v3/`

The benchmark harness is currently single-turn. The builder therefore converts the single-turn entries and skips the five multi-turn clarification follow-up entries from the 350 bank.

```bash
python3 benchmarks/gtm-agent-comparison/scripts/build_gtm_benchmark_cases.py \
  --suite all \
  --output /tmp/anip-benchmark/gtm-485-cases.json
```

Run the resulting ANIP benchmark:

```bash
python3 benchmarks/gtm-agent-comparison/scripts/run_http_agent_benchmark.py \
  --agent anip \
  --agent-url http://127.0.0.1:4310/api/ask \
  --cases /tmp/anip-benchmark/gtm-485-cases.json \
  --output-dir /tmp/anip-benchmark/anip-485 \
  --pricing benchmarks/gtm-agent-comparison/config/openai-pricing.example.json \
  --timeout-seconds 180
```

Do not compare the recipe/tool baseline against this full suite until equivalent raw tools, recipes, and backend fixtures exist for every covered GTM capability. The current baseline intentionally covers only the smoke subset.

## Compare Runs

```bash
python3 benchmarks/gtm-agent-comparison/scripts/compare_runs.py \
  --left /tmp/anip-benchmark/recipe-tool/recipe_tool_baseline-latest.json \
  --left-label recipe_tool_baseline \
  --right /tmp/anip-benchmark/anip/anip-latest.json \
  --right-label anip \
  --output /tmp/anip-benchmark/comparison.md
```

For public claims, fill `config/openai-pricing.example.json` with the exact provider pricing that applied at the time of the run and keep the pricing file with the run artifacts.

## Environment Variables

Use `OPENAI_API_KEY` and `OPENAI_MODEL` as the canonical benchmark variables.

The GTM showcase runtime also accepts `ANIP_AGENT_API_KEY` and `ANIP_AGENT_MODEL` for compatibility with the Docker compose examples. Do not set both unless you intentionally want the ANIP runtime to use different credentials or a different model than the recipe/tool baseline.

## Important Limits

This benchmark does not claim that every MCP implementation is inefficient or unsafe.

It compares:

- a service-owned ANIP contract path
- a consumer-owned recipe/tool path for the same GTM task family

The point is to measure where routing, policy, clarification, and approval logic live. When that logic lives in the consumer prompt/recipe, the agent generally needs more prompt context, more reasoning, and more repair loops. When that logic lives in the service contract, the agent can be smaller and more bounded.

## Next Steps

- Add a real MCP client adapter for the outreach backend instead of local fixture execution.
- Expand baseline coverage beyond prioritization/outreach.
- Add a summarizer that compares two run directories and produces a publishable table.
- Run the benchmark with `gpt-5.4-mini` first, then test smaller and larger model tiers.
