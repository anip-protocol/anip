"""ANIP → MCP translation layer.

Converts ANIP capability declarations into MCP tool schemas,
enriching descriptions with ANIP metadata that MCP cannot
natively represent.
"""

from __future__ import annotations

from .discovery import ANIPCapability

# Map ANIP input types to JSON Schema types
_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "date": "string",  # JSON Schema has no date type; use string with format
    "airport_code": "string",
}


def capability_to_input_schema(capability: ANIPCapability) -> dict:
    """Convert ANIP capability inputs to JSON Schema for MCP tool."""
    properties = {}
    required = []

    for inp in capability.inputs:
        json_type = _TYPE_MAP.get(inp.get("type", "string"), "string")
        prop: dict = {"type": json_type, "description": inp.get("description", "")}

        # Add format hint for date types
        if inp.get("type") == "date":
            prop["format"] = "date"

        # Add default if specified
        if "default" in inp and inp["default"] is not None:
            prop["default"] = inp["default"]

        properties[inp["name"]] = prop

        if inp.get("required", True):
            required.append(inp["name"])

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required

    return schema


def enrich_description(capability: ANIPCapability) -> str:
    """Enrich MCP tool description with ANIP metadata.

    Since MCP has no structured fields for side-effects, costs,
    or prerequisites, we encode these signals into the description
    string. This is lossy but gives MCP-native agents safety hints
    they would otherwise lack entirely.
    """
    parts = [capability.description]

    # Side-effect warning
    if capability.side_effect == "irreversible":
        parts.append(
            "WARNING: IRREVERSIBLE action — cannot be undone."
        )
        if capability.rollback_window == "none":
            parts.append("No rollback window.")
    elif capability.side_effect == "write":
        rollback = capability.rollback_window
        if rollback and rollback not in ("none", "not_applicable"):
            parts.append(f"Reversible within {rollback}.")
    elif capability.side_effect == "read":
        parts.append("Read-only, no side effects.")

    # Financial cost
    if capability.financial and capability.cost:
        financial = capability.cost.get("financial", {})
        certainty = capability.cost.get("certainty", "unknown")

        if certainty == "fixed":
            amount = financial.get("amount", "unknown")
            currency = financial.get("currency", "USD")
            if amount and float(amount) > 0:
                parts.append(f"Cost: {currency} {amount} (fixed).")
        elif certainty == "estimated":
            range_min = financial.get("range_min")
            range_max = financial.get("range_max")
            currency = financial.get("currency", "USD")
            if range_min is not None and range_max is not None:
                parts.append(
                    f"Estimated cost: {currency} {range_min}-{range_max}."
                )
        elif certainty == "dynamic":
            upper = financial.get("upper_bound")
            currency = financial.get("currency", "USD")
            if upper is not None:
                parts.append(f"Dynamic cost, up to {currency} {upper}.")
            else:
                parts.append("Dynamic cost — amount varies.")

    # Prerequisites
    if capability.requires:
        prereq_names = [r.get("capability", r) for r in capability.requires]
        parts.append(f"Requires calling first: {', '.join(prereq_names)}.")

    # Scope requirements
    if capability.minimum_scope:
        parts.append(
            f"Delegation scope: {', '.join(capability.minimum_scope)}."
        )

    return " ".join(parts)
