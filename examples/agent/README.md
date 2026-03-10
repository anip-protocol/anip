# ANIP Demo Agent

An AI agent that consumes an ANIP-compliant flight booking service, demonstrating why agent-native interfaces matter.

## What This Proves

The [reference implementation](../anip/) proves ANIP can be implemented. This demo proves something different: **an actual agent can use ANIP to do something better than it could with a normal API surface.**

Specifically:
- ANIP helps the agent **decide before acting** (discovery, cost awareness, prerequisite checking)
- **Failures are recoverable**, not opaque (structured resolution with actionable guidance)
- **Authorization survives into execution** (delegation chain, budget enforcement, purpose binding)
- **Auditability is part of the interface** (who acted, on whose authority, at what cost)

## The Demo

The agent is asked to book a SEA-to-SFO flight. It:

1. **Discovers** the service — learns capabilities, side effects, cost models
2. **Checks permissions** — confirms what it can do within its delegation
3. **Reasons before acting** — notes irreversibility, cost uncertainty, prerequisites
4. **Searches flights** — compares 3 options, prefers the nonstop at $420
5. **Gets blocked** — $420 exceeds its $300 budget authority; failure says who can fix it
6. **Receives fresh delegation** — human grants exactly enough ($450), purpose-bound
7. **Books successfully** — with full awareness of cost and irreversibility
8. **Verifies the audit trail** — confirms who acted, on whose authority, at what cost

## Running

Start the ANIP reference server:

```bash
cd examples/anip
pip install -e .
uvicorn anip_server.main:app
```

Run the demo (in a separate terminal):

```bash
cd examples/agent
pip install -r requirements.txt

# Simulated mode (default) — deterministic, no API key needed
python agent_demo.py

# Live mode — real LLM reasoning via Claude API
ANTHROPIC_API_KEY=sk-... python agent_demo.py --live
```

## Modes

**Simulated (default):** The agent follows the same 8-step flow with pre-written reasoning. Deterministic, reproducible, no API key required. This is the version you'd record for a demo video.

**Live (`--live`):** Same flow, but at each decision point the agent sends ANIP metadata to Claude and prints the model's actual reasoning. Proves the interface is usable by a real LLM, not just a hand-authored walkthrough.

In both modes, the ANIP HTTP calls are real — the agent talks to the actual reference server.
