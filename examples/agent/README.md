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

# Agent mode — real autonomous agent
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent

# Agent mode with interactive human delegation
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent --human-in-the-loop
```

## Modes

**Simulated (default):** The agent follows the same 8-step flow with pre-written reasoning. Deterministic, reproducible, no API key required. This is the version you'd record for a demo video.

**Live (`--live`):** Same flow, but at each decision point the agent sends ANIP metadata to Claude and prints the model's actual reasoning. Proves the interface is usable by a real LLM, not just a hand-authored walkthrough.

### Agent (`--agent`)

Real autonomous agent. The model receives ANIP-generated tool definitions and chooses which tools to call, in what order, with which parameters. The runner fetches the ANIP manifest at startup and generates tool descriptions from the live capability declarations — side effects, costs, prerequisites, and scope requirements are embedded in the tool interface.

The agent gets:
- **Capability tools** (generated from manifest): `search_flights`, `book_flight`
- **Protocol tools** (static): `check_permissions`, `request_budget_increase`, `query_audit`
- **Initial tokens**: search (travel.search) + book (travel.book, max $300)

The agent must decide on its own to search first, handle the budget block, request escalation, retry, and verify the audit trail. The loop is capped at 15 tool calls.

**Human delegation modes:**
- Default: budget requests are auto-granted (simulated human)
- `--human-in-the-loop`: pauses and prompts you to approve/deny/modify budget requests

In all modes, the ANIP HTTP calls are real — the agent talks to the actual reference server.
