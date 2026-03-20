"""ANIP → MCP translation layer.

Converts ANIP capability declarations into MCP tool schemas,
enriching descriptions with ANIP metadata.
"""
from __future__ import annotations

from typing import Any

_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",
    "airport_code": "string",
}


def capability_to_input_schema(declaration: dict[str, Any]) -> dict:
    """Convert ANIP capability inputs to JSON Schema for MCP tool."""
    properties = {}
    required = []

    for inp in declaration.get("inputs", []):
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        prop: dict = {"type": json_type, "description": inp.get("description", "")}
        if inp.get("type") == "date":
            prop["format"] = "date"
        if "default" in inp and inp["default"] is not None:
            prop["default"] = inp["default"]
        properties[inp["name"]] = prop
        if inp.get("required", True):
            required.append(inp["name"])

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def enrich_description(declaration: dict[str, Any]) -> str:
    """Enrich MCP tool description with ANIP metadata."""
    parts = [declaration.get("description", "")]
    se = declaration.get("side_effect", {})
    se_type = se.get("type") if isinstance(se, dict) else se
    rollback = se.get("rollback_window") if isinstance(se, dict) else None

    if se_type == "irreversible":
        parts.append("WARNING: IRREVERSIBLE action — cannot be undone.")
        if rollback == "none":
            parts.append("No rollback window.")
    elif se_type == "write":
        if rollback and rollback not in ("none", "not_applicable"):
            parts.append(f"Reversible within {rollback}.")
    elif se_type == "read":
        parts.append("Read-only, no side effects.")

    cost = declaration.get("cost")
    if cost:
        financial = cost.get("financial", {})
        certainty = cost.get("certainty")
        if certainty == "fixed" and financial:
            amount = financial.get("amount", 0)
            currency = financial.get("currency", "USD")
            if amount and float(amount) > 0:
                parts.append(f"Cost: {currency} {amount} (fixed).")
        elif certainty == "estimated" and financial:
            rmin = financial.get("range_min")
            rmax = financial.get("range_max")
            currency = financial.get("currency", "USD")
            if rmin is not None and rmax is not None:
                parts.append(f"Estimated cost: {currency} {rmin}-{rmax}.")

    requires = declaration.get("requires", [])
    if requires:
        prereqs = [r.get("capability", r) if isinstance(r, dict) else r for r in requires]
        parts.append(f"Requires calling first: {', '.join(prereqs)}.")

    scope = declaration.get("minimum_scope", [])
    if scope:
        parts.append(f"Delegation scope: {', '.join(scope)}.")

    return " ".join(parts)
