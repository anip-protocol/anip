"""ANIP → GraphQL translation layer.

Generates SDL schema from ANIP capabilities with custom directives,
camelCase field names, and query/mutation separation.
"""
from __future__ import annotations

from typing import Any

from anip_core.models import CapabilityDeclaration


def to_camel_case(snake: str) -> str:
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def to_snake_case(camel: str) -> str:
    import re
    return re.sub(r"([A-Z])", r"_\1", camel).lower().lstrip("_")


def _to_pascal_case(snake: str) -> str:
    return "".join(p.capitalize() for p in snake.split("_"))


_GQL_TYPE_MAP = {
    "string": "String",
    "integer": "Int",
    "number": "Float",
    "boolean": "Boolean",
    "object": "JSON",
    "array": "JSON",
}


def generate_schema(capabilities: dict[str, CapabilityDeclaration]) -> str:
    """Generate a complete GraphQL SDL schema from ANIP capabilities."""
    lines = [
        'directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION',
        'directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION',
        'directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION',
        'directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION',
        '',
        'scalar JSON',
        '',
        'type CostActual { financial: FinancialCost, varianceFromEstimate: String }',
        'type FinancialCost { amount: Float, currency: String }',
        'type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }',
        'type Resolution { action: String!, requires: String, grantableBy: String }',
        '',
    ]

    queries = []
    mutations = []

    for name, decl in capabilities.items():
        pascal = _to_pascal_case(name)
        camel = to_camel_case(name)

        lines.append(f"type {pascal}Result {{ success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }}")

        args = _build_field_args(decl)
        directives = _build_directives(decl)
        field_line = f"  {camel}{args}: {pascal}Result! {directives}"

        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        if se_type == "read":
            queries.append(field_line)
        else:
            mutations.append(field_line)

    lines.append("")
    if queries:
        lines.append("type Query {")
        lines.extend(queries)
        lines.append("}")
    if mutations:
        lines.append("type Mutation {")
        lines.extend(mutations)
        lines.append("}")

    return "\n".join(lines)


def _build_field_args(decl: CapabilityDeclaration) -> str:
    if not decl.inputs:
        return ""
    args = []
    for inp in decl.inputs:
        gql_type = _GQL_TYPE_MAP.get(inp.type, "String")
        if inp.required:
            gql_type += "!"
        args.append(f"{to_camel_case(inp.name)}: {gql_type}")
    return "(" + ", ".join(args) + ")"


def _build_directives(decl: CapabilityDeclaration) -> str:
    parts = []
    se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
    rollback = decl.side_effect.rollback_window

    se_dir = f'@anipSideEffect(type: "{se_type}"'
    if rollback:
        se_dir += f', rollbackWindow: "{rollback}"'
    se_dir += ")"
    parts.append(se_dir)

    if decl.cost:
        certainty = decl.cost.certainty.value if hasattr(decl.cost.certainty, "value") else str(decl.cost.certainty)
        cost_dir = f'@anipCost(certainty: "{certainty}"'
        if decl.cost.financial:
            financial = decl.cost.financial
            if hasattr(financial, "currency") and financial.currency:
                cost_dir += f', currency: "{financial.currency}"'
        cost_dir += ")"
        parts.append(cost_dir)

    if decl.requires:
        cap_names = ", ".join(f'"{r.capability}"' for r in decl.requires)
        parts.append(f"@anipRequires(capabilities: [{cap_names}])")

    if decl.minimum_scope:
        scope_vals = ", ".join(f'"{s}"' for s in decl.minimum_scope)
        parts.append(f"@anipScope(scopes: [{scope_vals}])")

    return " ".join(parts)


def build_graphql_response(result: dict[str, Any]) -> dict[str, Any]:
    """Map ANIP invoke response to GraphQL result shape (camelCase)."""
    response: dict[str, Any] = {
        "success": result.get("success", False),
        "result": result.get("result"),
        "costActual": None,
        "failure": None,
    }

    cost_actual = result.get("cost_actual")
    if cost_actual:
        response["costActual"] = {
            "financial": cost_actual.get("financial"),
            "varianceFromEstimate": cost_actual.get("variance_from_estimate"),
        }

    failure = result.get("failure")
    if failure:
        resolution = failure.get("resolution")
        response["failure"] = {
            "type": failure.get("type", "unknown"),
            "detail": failure.get("detail", ""),
            "resolution": {
                "action": resolution.get("action", ""),
                "requires": resolution.get("requires"),
                "grantableBy": resolution.get("grantable_by"),
            } if resolution else None,
            "retry": failure.get("retry", False),
        }

    return response
