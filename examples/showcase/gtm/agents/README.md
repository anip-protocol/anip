# Agents

This directory contains the manually maintained GTM agent benchmark.
Do not treat these runtimes as generated output.

Planned runtimes:

- baseline custom tool-calling loop
- manifest-aware deterministic runtime
- LLM runtime over a live ANIP capability brief
- LangGraph

The purpose is to show that ANIP is generic across agent runtimes.

Preservation rule:

- `examples/showcase/gtm/agents/*` is benchmark source.
- Generated services may be tested through these agents, but generation should not overwrite these files.
- Run `python3 examples/showcase/gtm/scripts/verify_manual_benchmark.py` before and after GTM generator work.
