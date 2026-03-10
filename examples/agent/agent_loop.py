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
            "The human will review and may grant a new token with higher budget. "
            "The token records the specific flight/date for audit context."
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


def dispatch_tool(
    client: ANIPClient,
    tool_name: str,
    tool_input: dict[str, Any],
    token_inventory: list[dict[str, Any]],
    capabilities: list[str],
    budget_failures: dict[str, dict[str, Any]],
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
        # tool_input has token_id popped, so it contains only the invocation params
        result = client.invoke(tool_name, token["raw_token"], tool_input)
        # Track budget_exceeded failures with full context so escalation can validate
        if "failure" in result and result["failure"].get("type") == "budget_exceeded":
            budget_failures[token_id] = {
                "capability": tool_name,
                "parameters": dict(tool_input),  # the params that were rejected
            }
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
    budget_failures: dict[str, dict[str, Any]],
    human_in_the_loop: bool,
) -> tuple[str, list[dict[str, Any]]]:
    """Handle a budget increase request — simulated or interactive.

    Validates that:
    1. current_token_id exists in inventory
    2. target_capability matches that token's capability
    3. The agent actually received a budget_exceeded failure for that token
    4. The requested flight_number and date match the parameters from the
       failed invocation (escalation must be for the same booking attempt)
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
    failed_context = budget_failures.get(current_token_id)
    if failed_context is None:
        return json.dumps({
            "error": "No budget_exceeded failure recorded for this token. "
                     "You must attempt the capability first and receive a "
                     "budget_exceeded failure before requesting escalation.",
        }), token_inventory

    # Validate: escalation must match the failed invocation parameters
    failed_params = failed_context.get("parameters", {})
    if failed_params.get("flight_number") != flight_number:
        return json.dumps({
            "error": f"flight_number '{flight_number}' does not match the failed "
                     f"request ('{failed_params.get('flight_number')}'). "
                     "Escalation must be for the same booking attempt.",
        }), token_inventory
    if failed_params.get("date") != date:
        return json.dumps({
            "error": f"date '{date}' does not match the failed request "
                     f"('{failed_params.get('date')}'). "
                     "Escalation must be for the same booking attempt.",
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

    # Create and register a fresh root token with purpose binding.
    # Note: purpose.parameters records the intended booking for audit context,
    # but the current server does not enforce parameter-level binding at
    # invocation time (it only checks capability match). Server-side
    # enforcement of purpose.parameters is a future enhancement.
    scope_str = f"travel.book:max_${int(granted_budget)}"
    new_token = make_token(
        issuer="human:samir@example.com",
        subject="agent:demo-agent",
        scope=[scope_str],
        capability=target_capability,
    )
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
    budget_failures: dict[str, dict[str, Any]] = {}  # token_id -> failed request context

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
