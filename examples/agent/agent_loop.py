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
