# ANIP Demo Agent — Design Document

## Goal

Build a demo agent that proves ANIP helps agents reason before acting — not just that the protocol can be implemented. The demo shows an actual agent consuming the ANIP flight booking service: discovering capabilities, reasoning about cost and side effects, handling budget failures with structured resolution, receiving narrowly scoped human delegation, and verifying the audit trail.

## What This Proves (vs. the existing demo.py)

The reference implementation proves ANIP can be implemented, the protocol surface is coherent, and adapters can be generated. The demo agent proves something different: an actual agent can use ANIP to do something *better* than it could with a normal API surface.

Specifically:
- ANIP helps the agent decide before acting
- Authorization survives into execution
- Failures are recoverable, not opaque
- Auditability is part of the interface, not an afterthought

## Architecture

### Location

`examples/agent/` — separated from the reference server to reinforce that the agent is a consumer, not part of the service.

### Approach: Hybrid — fixed flow with injectable reasoning

The 8-step narrative flow is fixed in both modes. The same ANIP HTTP calls execute in the same order. Only the reasoning text changes between simulated and live modes.

- **Simulated mode (default):** Deterministic, recordable. Canned reasoning text at each step. Zero API key required. This is the artifact people will read, record, and paste into READMEs.
- **Live mode (`--live`):** Real LLM reasoning. At each decision point, ANIP metadata (manifest excerpts, responses, failures) is sent to the model and its reasoning is printed. The flow doesn't change — only the commentary.

ANIP calls are always real in both modes. The demo talks to the actual reference server over HTTP. No mocked ANIP responses.

### File Structure

```
examples/agent/
├── agent_demo.py      # Entry point — runs the 8-step flow
├── reasoning.py       # reason(step, state) — simulated or live
├── anip_client.py     # Thin HTTP client for ANIP endpoints
├── README.md          # What this proves, how to run, sample output
└── requirements.txt   # httpx (+ anthropic for --live)
```

### Components

**`anip_client.py`** — thin HTTP client wrapping ANIP endpoint calls:
- `discover(base_url)` → discovery doc
- `get_manifest(base_url)` → full manifest
- `register_token(base_url, token)` → registration result
- `check_permissions(base_url, token)` → available/restricted/denied
- `get_graph(base_url, capability)` → prerequisites
- `invoke(base_url, capability, token, params)` → invoke response
- `query_audit(base_url, token, **filters)` → audit entries

**`reasoning.py`** — the only seam between simulated and live modes:
- `reason(step: str, state: dict, live: bool = False) -> str`
- Simulated: dictionary of canned reasoning keyed by step name
- Live: builds a prompt from the state (manifest excerpts, responses, failures) and calls the model via `anthropic` SDK
- One provider (Claude API), one model call wrapper, minimal config

**`agent_demo.py`** — the narrative runner:
- Parses `--live` flag and optional `--base-url` (default `http://localhost:8000`)
- Runs steps 1–8 sequentially
- Each step: prints header, calls reasoning, executes ANIP action, prints result
- Plain text output with section headers, no color/emoji dependencies

### Dependencies

- `httpx` — HTTP client (always required)
- `anthropic` — only imported when `--live` is used

### Running

```bash
# Start the reference server first
cd examples/anip && uvicorn anip_server.main:app

# Run the demo (simulated, default)
cd examples/agent && python agent_demo.py

# Run with live LLM reasoning
ANTHROPIC_API_KEY=sk-... python agent_demo.py --live
```

## Narrative Flow

### Step 1: Discovery

Agent fetches `/.well-known/anip` and manifest. Reasoning: "Two capabilities. `search_flights` is read-only, free, no side effects. `book_flight` is irreversible, estimated cost $280–$500, requires `search_flights` first."

### Step 2: Permission Check

Human delegates to agent with `travel.search` + `travel.book:max_$300`. Agent queries `/anip/permissions`. Reasoning: "I can search and book, but only up to $300."

### Step 3: Pre-invocation Reasoning

No HTTP call. Agent reasons from manifest metadata:
- `book_flight` is irreversible, no rollback
- Cost is estimated, resolved by searching first
- `search_flights` is a declared prerequisite
- "I'll search first to get actual prices before committing."

This is the step that proves ANIP helps agents think before acting.

### Step 4: Search and Compare

Agent invokes `search_flights` SEA→SFO 2026-03-10. Gets 3 results:
- AA100: $420, nonstop, 08:00–10:15
- UA205: $380, nonstop, 11:30–13:45
- DL310: $280, 1 stop, 14:00–18:30

Reasoning: "AA100 is the best option — nonstop, earliest arrival. But $420 exceeds my $300 authority. DL310 fits my budget at $280, but has a stop. I'll try the better flight first — if I'm blocked, the failure will tell me how to resolve it."

### Step 5: Book Attempt Blocked

Agent tries to book AA100 ($420). Gets `budget_exceeded`: "costs $420 but authority is max $300, request budget increase from human:samir@example.com." Reasoning: "Blocked as expected. The failure tells me exactly who can grant more authority and how much I need."

### Step 6: Human Grants Fresh Delegation

Human issues a fresh delegation (not a child token — widening budget would violate scope narrowing rules). Purpose-bound to `book_flight`, scoped to `travel.book:max_$450`. Reasoning: "Human granted a fresh delegation with just enough budget for this booking — $450, not unlimited. Purpose-bound to `book_flight` only."

### Step 7: Book Succeeds

Agent books AA100 with the new token. Actual cost $420. Reasoning: "Booking confirmed. Actual cost $420 vs declared estimate $280–$500 — within range. Side effect is irreversible, no undo."

### Step 8: Audit and Contrast

Agent queries `/anip/audit`. Verifies: who acted (agent), on whose authority (human:samir), delegation chain, actual cost $420, cost variance recorded. Brief REST contrast: "Through the REST adapter, this same booking loses delegation-chain fidelity and purpose-bound authority, so the workflow is less expressive than native ANIP."

## Output Format

Plain terminal output. Strong section headers. Short narrated reasoning blocks. No rich, no emoji, no visual gimmicks.

```
============================================================
STEP 1: DISCOVERY
============================================================

Agent reasoning: Two capabilities found. search_flights is read-only
and free. book_flight is irreversible with estimated cost $280-$500.
search_flights is a declared prerequisite for book_flight.

Action: GET /.well-known/anip
Result: Protocol anip/1.0, compliance: anip-complete, 2 capabilities

Action: GET /anip/manifest
Result: Full capability declarations retrieved

============================================================
STEP 2: PERMISSION CHECK
============================================================

...
```

## Design Decisions

- **ANIP calls are always real** — the demo talks to the actual server, not mocks. This proves protocol fidelity.
- **Flow is fixed in both modes** — live mode changes reasoning text, not the sequence of actions. This keeps the demo deterministic and recordable.
- **$300 initial budget** — uses existing flight data without modification. AA100 ($420 nonstop) is the obviously preferred flight that exceeds authority, creating a natural budget block.
- **Fresh delegation, not child token** — Step 6 issues a new root delegation because widening budget from $300 to $450 would violate scope narrowing rules (which we hardened in PRs #9–12).
- **REST contrast is brief and precise** — says "loses delegation-chain fidelity and purpose-bound authority," not overclaiming about specific features unless verified.
- **Python only** — the demo proves protocol value, not language symmetry. Python is the expected language for agent demos. TypeScript port can come later if needed.
