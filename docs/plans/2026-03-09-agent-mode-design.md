# ANIP Demo Agent — `--agent` Mode Design Document

## Goal

Add a real autonomous agent mode to the demo. The scripted demo proves the protocol semantics. `--agent` mode proves ANIP is actually consumable by an autonomous agent — the model discovers capabilities from live ANIP metadata, reasons about costs and side effects, handles budget failures through structured escalation, and arrives at the same outcome through its own decisions.

## What This Proves (vs. Scripted and Live Modes)

- **Scripted (default):** Proves the workflow and protocol semantics clearly. Deterministic, recordable.
- **Live (`--live`):** Same flow, but model-generated reasoning. Proves the metadata is LLM-consumable.
- **Agent (`--agent`):** Real autonomous loop. The model chooses which tools to call and in what order. Proves ANIP is consumable by an actual agent, not just a narrated walkthrough.

## Architecture

### Approach: ANIP Metadata in Tool Descriptions

At startup, the runner fetches the ANIP manifest and generates Claude tool definitions from the live capability declarations. Side effects, costs, prerequisites, and scope requirements are embedded in the tool descriptions — the model reads these before deciding which tool to call.

This directly proves the thesis: ANIP metadata in the tool interface makes agents reason better. The model doesn't need a separate discovery step because the runner derives the interface from the protocol surface.

### Token & Delegation Handling

The model reasons about authority but does not mint it. The runner owns delegation issuance.

**Pre-loop (runner-controlled):**
- Runner registers the initial tokens (search + book with $300 cap)
- Runner passes a compact token inventory to the model via system prompt:
  - token ID
  - purpose/capability
  - scope
  - budget cap (if present)

**During the loop (model-controlled):**
- Model chooses which tools to call and specifies which token_id to use
- Model can request escalation via `request_budget_increase` but cannot forge tokens
- Runner handles token creation on approval

### The Agentic Loop

```
1. Runner fetches manifest, generates tool definitions
2. Runner registers initial tokens (search + book:$300)
3. Runner sends to Claude:
   - System prompt: goal, ANIP context, token inventory
   - Tools: search_flights, book_flight, check_permissions,
            request_budget_increase, query_audit
4. Loop (max 15 iterations):
   - Model returns tool_use → runner executes → feed result back
   - Model returns text (no tool_use) → done, print final message
5. If loop cap hit → print warning and stop
```

### Tool Definitions

**Generated from ANIP manifest (per capability):**
- `name`: capability name (e.g. `search_flights`, `book_flight`)
- `description`: auto-generated from live ANIP metadata:
  - Capability description (from manifest)
  - Side effect type (irreversible actions stated prominently at the front)
  - Cost range (estimated, with note that actual budget authority comes from the delegation token)
  - Prerequisites (phrased as actionable constraints, e.g. "Prerequisite: search_flights should be called before this tool")
  - Required scope
  - Rollback window
- `input_schema`: derived from the capability's declared parameters, plus a required `token_id` field

**Protocol tools (static descriptions):**
- `check_permissions` — query what a given token grants. Input: `token_id`.
- `request_budget_increase` — structured escalation. Inputs:
  - `current_token_id` — the token that was insufficient
  - `requested_budget` — the amount needed
  - `reason` — why the increase is needed (must reference the specific failure)
  - `target_capability` — which capability this is for (must match the failed token's capability)
  - `flight_number` — specific flight this budget is for (purpose binding)
  - `date` — travel date (purpose binding)
  Runner validates: (1) token exists, (2) target_capability matches, (3) a `budget_exceeded` failure was actually received for that token. Rejects if any check fails.
  Returns on approval: new token ID, granted scope, purpose binding.
- `query_audit` — verify the audit trail. Input: `token_id`, optional `capability` filter.

### Human Delegation Modes

- **Simulated (default):** `request_budget_increase` auto-grants after validation. Runner creates a fresh root token purpose-bound to the specific flight/date (capped at $500).
- **Interactive (`--human-in-the-loop`):** Runner pauses, prints the request details including the specific flight, prompts the user to approve/deny/modify. User can adjust the budget before granting.

### System Prompt

```
You are an AI agent with access to an ANIP flight booking service.

Goal: Book a SEA→SFO flight for March 10.

Your delegation tokens:
  - {token_id}: search_flights (scope: travel.search)
  - {token_id}: book_flight (scope: travel.book, budget: max $300)

Use check_permissions and the tool descriptions to understand your
authority before acting. You must specify which token_id to use when
invoking capabilities. If a capability fails due to budget or scope,
use request_budget_increase to ask the human for additional authority.

Think carefully before acting. Check side effects, costs, and
prerequisites in the tool descriptions.
```

### Output Format

Same plain text style as the scripted demo. Each tool call and result is printed as it happens. The model's reasoning (text blocks between tool calls) is printed inline. The user sees the agent thinking and acting in real time.

### File Structure

```
examples/agent/
├── agent_demo.py      # --agent flag triggers agent_loop()
├── agent_loop.py      # NEW: agentic loop — tool gen, Claude calls, dispatch
├── anip_client.py     # Existing — no changes
├── reasoning.py       # Existing — no changes
├── README.md          # Updated with --agent docs
└── requirements.txt   # Already has anthropic
```

### Components

**`agent_loop.py`** — the new module:
- `generate_tools(manifest)` → list of Claude tool definitions, built from live ANIP metadata
- `build_system_prompt(token_inventory)` → system prompt with goal and token details
- `dispatch_tool(client, tool_name, tool_input, token_inventory, human_in_the_loop)` → execute tool call against ANIPClient, handle `request_budget_increase` specially
- `run_agent_loop(base_url, human_in_the_loop)` → the main loop: setup, Claude API calls, dispatch, print

**`agent_demo.py`** — updated entry point:
- Add `--agent` flag to argparse
- Add `--human-in-the-loop` flag (only valid with `--agent`)
- `--agent` calls `run_agent_loop()` instead of `DemoAgent.run()`

### Loop Cap

15 tool calls maximum. The happy path needs ~11 calls (2 permission checks, search, book-fail, budget request, book-succeed, audit — plus some optional exploration). 15 gives a small buffer without letting the agent spin.

### Dependencies

- `anthropic` — required for `--agent` mode (same as `--live`)
- `httpx` — already required

### Running

```bash
# Start the reference server
cd examples/anip && uvicorn anip_server.main:app

# Run agent mode (simulated human, auto-grants budget requests)
cd examples/agent
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent

# Run with real human-in-the-loop for delegation decisions
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent --human-in-the-loop
```

## Design Decisions

- **Tool descriptions generated from live ANIP metadata** — not hand-authored. The runner fetches the manifest and builds tool descriptions programmatically. This proves the protocol surface is machine-consumable.
- **Model reasons about authority but doesn't mint it** — the runner owns token creation. The model can request escalation via `request_budget_increase` but cannot forge tokens with arbitrary scopes or budgets. This is both more realistic and easier to defend.
- **Same goal as scripted demo** — "book the best nonstop SEA→SFO flight, budget $300." The proof is that the agent arrives at the same outcome autonomously.
- **Pre-loop discovery** — manifest is fetched before the loop starts and embedded in tool descriptions. No loop budget spent on meta-calls. A stricter "discovery mode" could be added later.
- **15-call cap** — tight enough to prevent spinning, loose enough for the happy path plus minor exploration.
- **Separate file (`agent_loop.py`)** — keeps the agentic logic isolated from the scripted demo. No changes to existing files except `agent_demo.py` (new flag) and `README.md`.
