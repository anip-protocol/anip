"""ANIP-to-GraphQL schema translation.

Generates a GraphQL SDL schema from discovered ANIP capabilities,
mapping read capabilities to Query fields and everything else to
Mutation fields with custom @anip* directives.
"""

from __future__ import annotations

from .discovery import ANIPCapability, ANIPService


def _to_camel_case(snake: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_pascal_case(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(p.capitalize() for p in snake.split("_"))


def _anip_type_to_graphql(anip_type: str) -> str:
    """Map ANIP input types to GraphQL scalar types."""
    type_map = {
        "string": "String",
        "integer": "Int",
        "number": "Float",
        "boolean": "Boolean",
        "object": "JSON",
        "array": "JSON",
    }
    return type_map.get(anip_type, "String")


def _build_directives(cap: ANIPCapability) -> str:
    """Build directive annotations for a capability field."""
    parts: list[str] = []

    # @anipSideEffect
    se = f'@anipSideEffect(type: "{cap.side_effect}"'
    if cap.rollback_window:
        se += f', rollbackWindow: "{cap.rollback_window}"'
    se += ")"
    parts.append(se)

    # @anipCost
    if cap.cost:
        certainty = cap.cost.get("certainty", "estimate")
        cost_dir = f'@anipCost(certainty: "{certainty}"'
        financial = cap.cost.get("financial")
        if financial:
            currency = financial.get("currency")
            if currency:
                cost_dir += f', currency: "{currency}"'
            range_val = financial.get("range")
            if range_val:
                cost_dir += f", rangeMin: {range_val[0]}, rangeMax: {range_val[1]}"
        cost_dir += ")"
        parts.append(cost_dir)

    # @anipRequires
    if cap.requires:
        cap_names = []
        for req in cap.requires:
            cap_name = req.get("capability", "")
            if cap_name:
                cap_names.append(f'"{cap_name}"')
        if cap_names:
            parts.append(f"@anipRequires(capabilities: [{', '.join(cap_names)}])")

    # @anipScope
    if cap.minimum_scope:
        scope_vals = ", ".join(f'"{s}"' for s in cap.minimum_scope)
        parts.append(f"@anipScope(scopes: [{scope_vals}])")

    return " ".join(parts)


def _build_field_args(cap: ANIPCapability) -> str:
    """Build GraphQL field arguments from capability inputs."""
    if not cap.inputs:
        return ""

    args: list[str] = []
    for inp in cap.inputs:
        name = _to_camel_case(inp["name"])
        gql_type = _anip_type_to_graphql(inp.get("type", "string"))
        required = inp.get("required", False)
        if required:
            gql_type += "!"
        args.append(f"{name}: {gql_type}")

    return "(" + ", ".join(args) + ")"


def generate_schema(service: ANIPService) -> str:
    """Generate a complete GraphQL SDL schema from an ANIP service.

    Maps read capabilities to Query fields and write/irreversible/transactional
    capabilities to Mutation fields. Includes custom @anip* directives and
    shared ANIP types.
    """
    lines: list[str] = []

    # Directive definitions
    lines.append('directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION')
    lines.append('directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION')
    lines.append('directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION')
    lines.append('directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION')
    lines.append("")

    # Scalar and shared types
    lines.append("scalar JSON")
    lines.append("")
    lines.append("type CostActual {")
    lines.append("  financial: FinancialCost")
    lines.append("  varianceFromEstimate: String")
    lines.append("}")
    lines.append("")
    lines.append("type FinancialCost {")
    lines.append("  amount: Float")
    lines.append("  currency: String")
    lines.append("}")
    lines.append("")
    lines.append("type ANIPFailure {")
    lines.append("  type: String!")
    lines.append("  detail: String!")
    lines.append("  resolution: Resolution")
    lines.append("  retry: Boolean!")
    lines.append("}")
    lines.append("")
    lines.append("type Resolution {")
    lines.append("  action: String!")
    lines.append("  requires: String")
    lines.append("  grantableBy: String")
    lines.append("}")
    lines.append("")

    # Per-capability result types
    queries: list[str] = []
    mutations: list[str] = []

    for name, cap in service.capabilities.items():
        pascal = _to_pascal_case(name)
        camel = _to_camel_case(name)

        # Result type
        lines.append(f"type {pascal}Result {{")
        lines.append("  success: Boolean!")
        lines.append("  result: JSON")
        lines.append("  costActual: CostActual")
        lines.append("  failure: ANIPFailure")
        lines.append("}")
        lines.append("")

        # Field with args and directives
        args = _build_field_args(cap)
        directives = _build_directives(cap)
        field_line = f"  {camel}{args}: {pascal}Result! {directives}"

        if cap.side_effect == "read":
            queries.append(field_line)
        else:
            mutations.append(field_line)

    # Query type
    if queries:
        lines.append("type Query {")
        for q in queries:
            lines.append(q)
        lines.append("}")
        lines.append("")
    else:
        # GraphQL requires a Query type
        lines.append("type Query {")
        lines.append("  _empty: String")
        lines.append("}")
        lines.append("")

    # Mutation type
    if mutations:
        lines.append("type Mutation {")
        for m in mutations:
            lines.append(m)
        lines.append("}")
        lines.append("")

    return "\n".join(lines)
