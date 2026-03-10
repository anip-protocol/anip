# Agent Mode (`--agent`) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real autonomous agent mode where Claude chooses which ANIP tools to call, reasons about costs and side effects, handles budget failures through structured escalation, and arrives at a flight booking through its own decisions.

**Architecture:** At startup, fetch the ANIP manifest and generate Claude tool definitions from live capability declarations. Enter a tool_use loop (max 15 iterations): send goal + tools to Claude, execute the model's chosen tool, feed result back, repeat until done. Runner owns delegation token creation; model owns planning and escalation requests.

**Tech Stack:** Python, httpx, anthropic SDK (required for --agent mode)

---

### Task 1: Tool Generation from ANIP Manifest

**Files:**
- Create: `examples/agent/agent_loop.py`

**Context:** This module generates Claude API tool definitions from a live ANIP manifest. Each capability becomes a tool whose description is built from the ANIP metadata (side effects, costs, prerequisites, scope). Three additional protocol tools are added with static definitions.

**Step 1: Create agent_loop.py with tool generation**

```python
"""Autonomous agent loop — tool generation, Claude API calls, dispatch."""

from __future__ import annotations

import json
from typing import Any

from anip_client import ANIPClient, make_token


def _capability_to_tool(name: str, cap: dict[str, Any]) -> dict[str, Any]:
    """Generate a Claude tool definition from an ANIP capability declaration."""
    parts = []

    # Description from manifest
    if cap.get("description"):
        parts.append(cap["description"] + ".")

    # Side effect — prominently at the front for irreversible actions
    side_effect = cap.get("side_effect", {})
    if isinstance(side_effect, dict):
        se_type = side_effect.get("type", "unknown")
        rollback = side_effect.get("rollback_window", "unknown")
    else:
        se_type = str(side_effect)
        rollback = "unknown"
    if se_type == "irreversible":
        parts.insert(0, f"IRREVERSIBLE — no rollback.")
    else:
        parts.append(f"Side effect: {se_type}.")
    if rollback != "unknown" and rollback != "none":
        parts.append(f"Rollback window: {rollback}.")

    # Cost
    cost = cap.get("cost", {})
    financial = cost.get("financial") if cost else None
    if financial:
        range_min = financial.get("range_min")
        range_max = financial.get("range_max")
        currency = financial.get("currency", "USD")
        if range_min is not None and range_max is not None:
            parts.append(
                f"Estimated cost: {currency} ${range_min}-${range_max}. "
                f"Actual budget authority is determined by the delegation token at invocation time."
            )
    else:
        parts.append("No financial cost.")

    # Prerequisites
    requires = cap.get("requires", [])
    for req in requires:
        req_cap = req.get("capability", "unknown")
        reason = req.get("reason", "")
        parts.append(f"Prerequisite: {req_cap} should be called before this tool. {reason}")

    # Scope
    minimum_scope = cap.get("minimum_scope", [])
    if minimum_scope:
        parts.append(f"Required scope: {', '.join(minimum_scope)}.")

    # Build input schema from capability inputs
    properties: dict[str, Any] = {
        "token_id": {
            "type": "string",
            "description": "The delegation token ID to use for this invocation",
        }
    }
    required = ["token_id"]

    for inp in cap.get("inputs", []):
        prop: dict[str, Any] = {}
        inp_type = inp.get("type", "string")
        # Map ANIP types to JSON Schema types
        type_map = {
            "string": "string",
            "date": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
        }
        prop["type"] = type_map.get(inp_type, "string")
        if inp.get("description"):
            prop["description"] = inp["description"]
        if inp_type == "date":
            prop["description"] = (prop.get("description", "") + " (YYYY-MM-DD format)").strip()
        if inp.get("default") is not None:
            prop["description"] = (
                prop.get("description", "") + f" Default: {inp['default']}"
            ).strip()

        properties[inp["name"]] = prop
        if inp.get("required", False):
            required.append(inp["name"])

    return {
        "name": name,
        "description": " ".join(parts),
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


# Protocol tools — static definitions
PROTOCOL_TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_permissions",
        "description": (
            "Query what capabilities a delegation token grants. "
            "Returns available, restricted, and denied capabilities. "
            "Use this to verify your authority before attempting an action."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "The delegation token ID to check",
                },
            },
            "required": ["token_id"],
        },
    },
    {
        "name": "request_budget_increase",
        "description": (
            "Request additional budget authority from the human principal. "
            "PREREQUISITE: You must have received a budget_exceeded failure from a "
            "capability invocation before calling this. The runner will reject the "
            "request if no prior failure exists. "
            "The human will review and may grant a new purpose-bound token with "
            "higher budget, scoped to the specific booking you specify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "current_token_id": {
                    "type": "string",
                    "description": "The token that was insufficient (must match a registered token)",
                },
                "requested_budget": {
                    "type": "number",
                    "description": "The budget amount needed (in USD)",
                },
                "reason": {
                    "type": "string",
                    "description": "Why the increase is needed — reference the specific failure",
                },
                "target_capability": {
                    "type": "string",
                    "description": "Which capability this budget is for (must match the failed token's capability)",
                },
                "flight_number": {
                    "type": "string",
                    "description": "The specific flight this budget is for (purpose binding)",
                },
                "date": {
                    "type": "string",
                    "description": "The travel date (purpose binding)",
                },
            },
            "required": [
                "current_token_id",
                "requested_budget",
                "reason",
                "target_capability",
                "flight_number",
                "date",
            ],
        },
    },
    {
        "name": "query_audit",
        "description": (
            "Query the audit trail to verify what actions were taken, "
            "by whom, on whose authority, and at what cost. "
            "Use this after completing actions to verify the record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "token_id": {
                    "type": "string",
                    "description": "The delegation token ID for audit access",
                },
                "capability": {
                    "type": "string",
                    "description": "Optional: filter audit entries by capability name",
                },
            },
            "required": ["token_id"],
        },
    },
]


def generate_tools(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate Claude tool definitions from an ANIP manifest."""
    tools = []
    for name, cap in manifest.get("capabilities", {}).items():
        tools.append(_capability_to_tool(name, cap))
    tools.extend(PROTOCOL_TOOLS)
    return tools
```

**Step 2: Verify tool generation manually**

```bash
cd examples/anip && uvicorn anip_server.main:app &
sleep 2
cd examples/agent && python3 -c "
from anip_client import ANIPClient
from agent_loop import generate_tools
import json
c = ANIPClient()
m = c.get_manifest()
tools = generate_tools(m)
for t in tools:
    print(f'{t[\"name\"]}: {t[\"description\"][:80]}...')
print(f'\nTotal tools: {len(tools)}')
print(json.dumps(tools[1], indent=2))  # book_flight
"
```

Expected: 5 tools (search_flights, book_flight, check_permissions, request_budget_increase, query_audit). book_flight description starts with "IRREVERSIBLE".

**Step 3: Commit**

```bash
git add examples/agent/agent_loop.py
git commit -m "feat(agent-mode): add tool generation from ANIP manifest"
```

---

### Task 2: System Prompt and Token Inventory

**Files:**
- Modify: `examples/agent/agent_loop.py`

**Context:** Build the system prompt with the goal, ANIP context, and a compact token inventory showing each token's ID, capability, scope, and budget cap.

**Step 1: Add system prompt builder**

Add after `generate_tools`:

```python
def build_system_prompt(token_inventory: list[dict[str, Any]]) -> str:
    """Build the system prompt with goal and token inventory."""
    token_lines = []
    for t in token_inventory:
        line = f"  - {t['token_id']}: {t['capability']} (scope: {t['scope']}"
        if t.get("budget"):
            line += f", budget: max ${t['budget']}"
        line += ")"
        token_lines.append(line)

    return (
        "You are an AI agent with access to an ANIP flight booking service.\n\n"
        "Goal: Book a SEA→SFO flight for March 10.\n\n"
        "Your delegation tokens:\n"
        + "\n".join(token_lines)
        + "\n\n"
        "Use check_permissions and the tool descriptions to understand your authority "
        "before acting. You must specify which token_id to use when invoking capabilities.\n"
        "If a capability fails due to budget or scope, use request_budget_increase "
        "to ask the human for additional authority.\n\n"
        "Think carefully before acting. Check side effects, costs, and "
        "prerequisites in the tool descriptions.\n"
        "When you are done, respond with a final text summary of what you accomplished."
    )
```

**Step 2: Verify**

```bash
cd examples/agent && python3 -c "
from agent_loop import build_system_prompt
prompt = build_system_prompt([
    {'token_id': 'tok-1', 'capability': 'search_flights', 'scope': 'travel.search'},
    {'token_id': 'tok-2', 'capability': 'book_flight', 'scope': 'travel.book', 'budget': 300},
])
print(prompt)
"
```

Expected: System prompt with two token entries, budget shown for book token.

**Step 3: Commit**

```bash
git add examples/agent/agent_loop.py
git commit -m "feat(agent-mode): add system prompt builder with token inventory"
```

---

### Task 3: Tool Dispatcher

**Files:**
- Modify: `examples/agent/agent_loop.py`

**Context:** The dispatcher maps tool names to `ANIPClient` method calls. Capability tools look up the token from inventory and invoke via the client. `request_budget_increase` either auto-grants or prompts the human — but **only if the agent has actually received a `budget_exceeded` failure** (tracked via a `budget_failures` set passed through the dispatch chain). The dispatcher returns the result as a string for Claude.

**Step 1: Add the dispatcher**

Add after `build_system_prompt`:

```python
def dispatch_tool(
    client: ANIPClient,
    tool_name: str,
    tool_input: dict[str, Any],
    token_inventory: list[dict[str, Any]],
    capabilities: list[str],
    budget_failures: set[str],
    human_in_the_loop: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """Execute a tool call and return (result_string, updated_token_inventory).

    Returns the result as a JSON string for Claude, plus the potentially
    updated token inventory (if a new token was granted).
    """
    if tool_name == "check_permissions":
        token = _find_token(tool_input["token_id"], token_inventory)
        if token is None:
            return json.dumps({"error": f"token {tool_input['token_id']} not found"}), token_inventory
        result = client.check_permissions(token["raw_token"])
        return json.dumps(result, default=str), token_inventory

    if tool_name == "request_budget_increase":
        return _handle_budget_request(
            client, tool_input, token_inventory, budget_failures, human_in_the_loop
        )

    if tool_name == "query_audit":
        token = _find_token(tool_input["token_id"], token_inventory)
        if token is None:
            return json.dumps({"error": f"token {tool_input['token_id']} not found"}), token_inventory
        result = client.query_audit(
            token["raw_token"],
            capability=tool_input.get("capability"),
        )
        return json.dumps(result, default=str), token_inventory

    # Capability invocation
    if tool_name in capabilities:
        token_id = tool_input.pop("token_id", None)
        if token_id is None:
            return json.dumps({"error": "token_id is required"}), token_inventory
        token = _find_token(token_id, token_inventory)
        if token is None:
            return json.dumps({"error": f"token {token_id} not found"}), token_inventory
        result = client.invoke(tool_name, token["raw_token"], tool_input)
        # Track budget_exceeded failures so escalation can validate against them
        if "failure" in result and result["failure"].get("type") == "budget_exceeded":
            budget_failures.add(token_id)
        return json.dumps(result, default=str), token_inventory

    return json.dumps({"error": f"unknown tool: {tool_name}"}), token_inventory


def _find_token(
    token_id: str, inventory: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Find a token in the inventory by ID."""
    for t in inventory:
        if t["token_id"] == token_id:
            return t
    return None


def _handle_budget_request(
    client: ANIPClient,
    tool_input: dict[str, Any],
    token_inventory: list[dict[str, Any]],
    budget_failures: set[str],
    human_in_the_loop: bool,
) -> tuple[str, list[dict[str, Any]]]:
    """Handle a budget increase request — simulated or interactive.

    Validates that:
    1. current_token_id exists in inventory
    2. target_capability matches that token's capability
    3. The agent actually received a budget_exceeded failure for that token
    """
    current_token_id = tool_input["current_token_id"]
    requested_budget = tool_input["requested_budget"]
    target_capability = tool_input["target_capability"]
    flight_number = tool_input["flight_number"]
    date = tool_input["date"]
    reason = tool_input.get("reason", "")

    # Validate: token must exist
    token = _find_token(current_token_id, token_inventory)
    if token is None:
        return json.dumps({
            "error": f"token {current_token_id} not found",
        }), token_inventory

    # Validate: target_capability must match the token's capability
    if token.get("capability") != target_capability:
        return json.dumps({
            "error": f"token {current_token_id} is for {token.get('capability')}, "
                     f"not {target_capability}",
        }), token_inventory

    # Validate: must have a prior budget_exceeded failure for this token
    if current_token_id not in budget_failures:
        return json.dumps({
            "error": "No budget_exceeded failure recorded for this token. "
                     "You must attempt the capability first and receive a "
                     "budget_exceeded failure before requesting escalation.",
        }), token_inventory

    # Cap at reasonable maximum
    max_allowed = 500
    granted_budget = min(requested_budget, max_allowed)

    if human_in_the_loop:
        print(f"\n{'=' * 60}")
        print("HUMAN DELEGATION REQUEST")
        print(f"{'=' * 60}")
        print(f"Agent requests budget increase:")
        print(f"  Capability: {target_capability}")
        print(f"  For: {flight_number} on {date}")
        print(f"  Requested budget: ${requested_budget}")
        print(f"  Reason: {reason}")
        response = input(f"\nGrant budget? (enter amount, or 'deny'): ").strip()
        if response.lower() == "deny":
            return json.dumps({
                "status": "denied",
                "detail": "Human denied the budget increase request",
            }), token_inventory
        try:
            granted_budget = float(response)
        except ValueError:
            granted_budget = min(requested_budget, max_allowed)
    else:
        print(f"\n[Simulated human grants ${granted_budget} budget for {target_capability} — {flight_number} on {date}]")

    # Create and register a fresh root token — purpose-bound to the specific booking
    scope_str = f"travel.book:max_${int(granted_budget)}"
    new_token = make_token(
        issuer="human:samir@example.com",
        subject="agent:demo-agent",
        scope=[scope_str],
        capability=target_capability,
    )
    # Bind purpose to the specific flight and date
    new_token["purpose"]["parameters"] = {
        "flight_number": flight_number,
        "date": date,
    }
    client.register_token(new_token)

    # Add to inventory
    new_entry = {
        "token_id": new_token["token_id"],
        "capability": target_capability,
        "scope": scope_str,
        "budget": granted_budget,
        "purpose_bound_to": f"{flight_number} on {date}",
        "raw_token": new_token,
    }
    token_inventory = token_inventory + [new_entry]

    return json.dumps({
        "status": "approved",
        "new_token_id": new_token["token_id"],
        "granted_scope": scope_str,
        "granted_budget": granted_budget,
        "purpose": target_capability,
        "purpose_bound_to": f"{flight_number} on {date}",
    }), token_inventory
```

**Step 2: Commit**

```bash
git add examples/agent/agent_loop.py
git commit -m "feat(agent-mode): add tool dispatcher with budget escalation"
```

---

### Task 4: The Agentic Loop

**Files:**
- Modify: `examples/agent/agent_loop.py`

**Context:** The main loop: setup (fetch manifest, generate tools, register tokens), then iterate — send messages to Claude, dispatch tool calls, feed results back. Print each action and result for the user to follow along.

**Step 1: Add the main loop**

Add at the end of `agent_loop.py`:

```python
MAX_TOOL_CALLS = 15


def run_agent_loop(
    base_url: str = "http://127.0.0.1:8000",
    human_in_the_loop: bool = False,
) -> None:
    """Run the autonomous agent loop."""
    import anthropic

    client = ANIPClient(base_url)
    claude = anthropic.Anthropic()

    # --- Setup: fetch manifest and generate tools ---
    print("ANIP Agent Mode")
    print(f"Server: {base_url}")
    print(f"Human delegation: {'interactive' if human_in_the_loop else 'simulated'}")

    print(f"\n{'=' * 60}")
    print("SETUP: Fetching ANIP manifest and registering tokens")
    print(f"{'=' * 60}")

    manifest = client.get_manifest()
    capability_names = list(manifest.get("capabilities", {}).keys())
    tools = generate_tools(manifest)
    print(f"Generated {len(tools)} tools from manifest: {', '.join(t['name'] for t in tools)}")

    # Register initial tokens
    search_token = make_token(
        issuer="human:samir@example.com",
        subject="agent:demo-agent",
        scope=["travel.search"],
        capability="search_flights",
    )
    client.register_token(search_token)

    book_token = make_token(
        issuer="human:samir@example.com",
        subject="agent:demo-agent",
        scope=["travel.book:max_$300"],
        capability="book_flight",
    )
    client.register_token(book_token)

    token_inventory: list[dict[str, Any]] = [
        {
            "token_id": search_token["token_id"],
            "capability": "search_flights",
            "scope": "travel.search",
            "raw_token": search_token,
        },
        {
            "token_id": book_token["token_id"],
            "capability": "book_flight",
            "scope": "travel.book:max_$300",
            "budget": 300,
            "raw_token": book_token,
        },
    ]

    print(f"Registered tokens:")
    for t in token_inventory:
        budget_str = f", budget: max ${t['budget']}" if t.get('budget') else ""
        print(f"  {t['token_id']}: {t['capability']} ({t['scope']}{budget_str})")

    system_prompt = build_system_prompt(token_inventory)

    # --- Agent loop ---
    print(f"\n{'=' * 60}")
    print("AGENT LOOP")
    print(f"{'=' * 60}")

    messages: list[dict[str, Any]] = []
    tool_call_count = 0
    budget_failures: set[str] = set()  # tracks tokens that received budget_exceeded

    while tool_call_count < MAX_TOOL_CALLS:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # Process response content blocks
        assistant_content = response.content
        tool_uses = []

        for block in assistant_content:
            if block.type == "text" and block.text.strip():
                print(f"\nAgent: {block.text}")
            elif block.type == "tool_use":
                tool_uses.append(block)

        # If no tool calls, the agent is done
        if not tool_uses:
            break

        # Append assistant message
        messages.append({"role": "assistant", "content": assistant_content})

        # Execute each tool call
        tool_results = []
        for tool_use in tool_uses:
            tool_call_count += 1
            print(f"\n[{tool_call_count}/{MAX_TOOL_CALLS}] Tool: {tool_use.name}")
            print(f"  Input: {json.dumps(tool_use.input, default=str)}")

            result_str, token_inventory = dispatch_tool(
                client,
                tool_use.name,
                dict(tool_use.input),  # copy to avoid mutation
                token_inventory,
                capability_names,
                budget_failures,
                human_in_the_loop,
            )

            # Print a compact result summary
            try:
                result_data = json.loads(result_str)
                if isinstance(result_data, dict):
                    if result_data.get("success") is False:
                        failure = result_data.get("failure", {})
                        print(f"  Result: BLOCKED — {failure.get('type', 'unknown')}: {failure.get('detail', '')}")
                    elif result_data.get("success") is True:
                        print(f"  Result: SUCCESS")
                    elif result_data.get("status"):
                        print(f"  Result: {result_data['status']}")
                    else:
                        # Permission check or audit — show compact summary
                        if "available" in result_data:
                            avail = [c["capability"] for c in result_data.get("available", [])]
                            print(f"  Result: available={avail}")
                        elif "entries" in result_data:
                            print(f"  Result: {len(result_data['entries'])} audit entries")
                        else:
                            print(f"  Result: {result_str[:200]}")
                else:
                    print(f"  Result: {result_str[:200]}")
            except (json.JSONDecodeError, TypeError):
                print(f"  Result: {result_str[:200]}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result_str,
            })

        messages.append({"role": "user", "content": tool_results})

    if tool_call_count >= MAX_TOOL_CALLS:
        print(f"\n[Loop cap reached: {MAX_TOOL_CALLS} tool calls]")

    print(f"\n{'=' * 60}")
    print(f"AGENT COMPLETE ({tool_call_count} tool calls)")
    print(f"{'=' * 60}")
```

**Step 2: Commit**

```bash
git add examples/agent/agent_loop.py
git commit -m "feat(agent-mode): add main agentic loop with Claude API"
```

---

### Task 5: Wire Up CLI Flags

**Files:**
- Modify: `examples/agent/agent_demo.py`

**Context:** Add `--agent` and `--human-in-the-loop` flags to argparse. When `--agent` is passed, call `run_agent_loop()` instead of `DemoAgent.run()`.

**Step 1: Update agent_demo.py**

In the `main()` function, add the new flags and dispatch:

Replace the existing `main()` function (starting from `def main()`) with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP Demo Agent")
    parser.add_argument("--live", action="store_true", help="Use live LLM reasoning (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--agent", action="store_true", help="Run as autonomous agent (requires ANTHROPIC_API_KEY)")
    parser.add_argument("--human-in-the-loop", action="store_true", help="Interactive human delegation (with --agent)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="ANIP service URL")
    args = parser.parse_args()

    if args.agent:
        from agent_loop import run_agent_loop
        try:
            run_agent_loop(
                base_url=args.base_url,
                human_in_the_loop=args.human_in_the_loop,
            )
        except httpx.ConnectError:
            print(f"\nError: Cannot connect to ANIP server at {args.base_url}")
            print("Start the server first: cd examples/anip && uvicorn anip_server.main:app")
            sys.exit(1)
        except httpx.HTTPStatusError as e:
            print(f"\nError: Server returned {e.response.status_code} for {e.request.url}")
            print("Check that the ANIP reference server is running correctly.")
            sys.exit(1)
        return

    agent = DemoAgent(base_url=args.base_url, live=args.live)
    try:
        agent.run()
    except httpx.ConnectError:
        print(f"\nError: Cannot connect to ANIP server at {args.base_url}")
        print("Start the server first: cd examples/anip && uvicorn anip_server.main:app")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nError: Server returned {e.response.status_code} for {e.request.url}")
        print("Check that the ANIP reference server is running correctly.")
        sys.exit(1)
```

**Step 2: Test agent mode starts**

```bash
cd examples/anip && rm -f anip.db* && uvicorn anip_server.main:app &
sleep 2
cd examples/agent && ANTHROPIC_API_KEY=... python3 agent_demo.py --agent
```

Expected: Agent mode runs, generates tools, registers tokens, enters loop, model makes tool calls autonomously.

**Step 3: Commit**

```bash
git add examples/agent/agent_demo.py
git commit -m "feat(agent-mode): wire up --agent and --human-in-the-loop CLI flags"
```

---

### Task 6: Update README

**Files:**
- Modify: `examples/agent/README.md`

**Context:** Add documentation for the new `--agent` mode.

**Step 1: Add agent mode section to README**

After the existing "## Modes" section, add:

```markdown

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
```

Also update the "## Running" section to include:

```markdown

# Agent mode — real autonomous agent
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent

# Agent mode with interactive human delegation
ANTHROPIC_API_KEY=sk-... python agent_demo.py --agent --human-in-the-loop
```

**Step 2: Commit**

```bash
git add examples/agent/README.md
git commit -m "docs(agent-mode): add --agent mode documentation to README"
```

---

### Task 7: End-to-End Verification

**Context:** Run agent mode end-to-end against a fresh server and verify the agent completes the booking autonomously.

**Step 1: Start fresh server**

```bash
cd examples/anip
rm -f anip.db anip.db-shm anip.db-wal
uvicorn anip_server.main:app &
sleep 2
```

**Step 2: Run agent mode**

```bash
cd examples/agent
ANTHROPIC_API_KEY=... python3 agent_demo.py --agent
```

Expected output should show:
- Setup: 5 tools generated, 2 tokens registered
- Agent calls search_flights with search token
- Agent evaluates results, picks AA100 ($420)
- Agent attempts book_flight, gets budget_exceeded
- Agent calls request_budget_increase
- Agent retries book_flight with new token, succeeds
- Agent calls query_audit to verify
- Agent prints final summary
- "AGENT COMPLETE" with tool call count

**Step 3: Fix any issues found during verification**

**Step 4: Kill the server**

```bash
kill %1
```
