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

In all modes, the ANIP HTTP calls are real — the agent talks to the actual reference server. The protocol supports streaming invocations (v0.6), but this demo uses unary mode for simplicity.

## Example Output (`--agent`)

This is real output from a single run. The agent autonomously discovers its authority, searches flights, hits the budget wall, escalates, books a nonstop flight, and verifies the audit trail — all from ANIP metadata, with no scripting.

```
ANIP Agent Mode
Server: http://127.0.0.1:9100
Human delegation: simulated

============================================================
SETUP: Fetching ANIP manifest and registering tokens
============================================================
Generated 5 tools from manifest: search_flights, book_flight, check_permissions, request_budget_increase, query_audit
Registered tokens:
  demo-b0995ff9: search_flights (travel.search)
  demo-f72e58e6: book_flight (travel.book:max_$300, budget: max $300)

============================================================
AGENT LOOP
============================================================

Agent: I'll help you book a SEA→SFO flight for 2026-03-10. Let me start by
checking my permissions and then searching for available flights.

[1/15] Tool: check_permissions
  Input: {"token_id": "demo-b0995ff9"}
  Result: available=['search_flights']

[2/15] Tool: check_permissions
  Input: {"token_id": "demo-f72e58e6"}
  Result: available=['book_flight']

Agent: Good! I can see that:
- Token demo-b0995ff9 allows me to search flights
- Token demo-f72e58e6 allows me to book flights with a budget of $300

Now let me search for flights from SEA to SFO on 2026-03-10:

[3/15] Tool: search_flights
  Input: {"token_id": "demo-b0995ff9", "origin": "SEA", "destination": "SFO",
          "date": "2026-03-10"}
  Result: SUCCESS

Agent: Perfect! I found 3 flights:

1. AA100 (nonstop): Departs 08:00, arrives 10:15 - $420 (exceeds budget)
2. UA205 (nonstop): Departs 11:30, arrives 13:45 - $380 (exceeds budget)
3. DL310 (1 stop): Departs 14:00, arrives 18:30 - $280 (within budget)

Since you prefer nonstop flights when possible, let me try to book the cheapest
nonstop option (UA205 at $380) first:

[4/15] Tool: book_flight
  Input: {"token_id": "demo-f72e58e6", "flight_number": "UA205",
          "date": "2026-03-10"}
  Result: BLOCKED — budget_exceeded: capability costs $380.0 but delegation
          chain authority is max $300.0

Agent: As expected, the nonstop flight exceeds my budget. Let me request a
budget increase:

[5/15] Tool: request_budget_increase
  Input: {"current_token_id": "demo-f72e58e6", "requested_budget": 380,
          "reason": "The cheapest nonstop flight UA205 costs $380, but current
          budget is only $300.",
          "target_capability": "book_flight", "flight_number": "UA205",
          "date": "2026-03-10"}

[Simulated human grants $380 budget for book_flight — UA205 on 2026-03-10]
  Result: approved

Agent: The budget increase was approved. I now have a new token demo-c5da6ccd
with $380 budget. Let me book the nonstop flight UA205:

[6/15] Tool: book_flight
  Input: {"token_id": "demo-c5da6ccd", "flight_number": "UA205",
          "date": "2026-03-10"}
  Result: SUCCESS

Agent: The flight has been successfully booked. Let me verify the audit trail:

[7/15] Tool: query_audit
  Input: {"token_id": "demo-c5da6ccd"}
  Result: 2 audit entries

Agent: Booking confirmed.

Flight: UA205 (nonstop), SEA → SFO, March 10 2026, 11:30→13:45
Cost: $380 | Booking ID: BK-0018
Process: checked permissions → searched flights → preferred nonstop →
hit $300 budget → escalated to $380 → booked → verified audit trail

============================================================
AGENT COMPLETE (7 tool calls)
============================================================
```

**What to notice:** The agent was never told the steps. It discovered its authority from `check_permissions`, learned flight prices from `search_flights`, hit the budget wall from ANIP's structured failure (not an HTTP 403), escalated through the protocol's `request_budget_increase` with the exact failed flight/date, and verified its work through the audit trail. Every decision came from ANIP metadata.
