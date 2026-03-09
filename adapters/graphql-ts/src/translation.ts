/**
 * ANIP-to-GraphQL schema translation.
 *
 * Generates a GraphQL SDL schema from discovered ANIP capabilities,
 * mapping read capabilities to Query fields and everything else to
 * Mutation fields with custom @anip* directives.
 */

import type { ANIPCapability, ANIPService } from "./discovery.js";

export function toCamelCase(snake: string): string {
  const parts = snake.split("_");
  return (
    parts[0] +
    parts
      .slice(1)
      .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
      .join("")
  );
}

export function toSnakeCase(camel: string): string {
  return camel.replace(/([A-Z])/g, "_$1").toLowerCase().replace(/^_/, "");
}

function toPascalCase(snake: string): string {
  return snake
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join("");
}

function anipTypeToGraphQL(anipType: string): string {
  const typeMap: Record<string, string> = {
    string: "String",
    integer: "Int",
    number: "Float",
    boolean: "Boolean",
    object: "JSON",
    array: "JSON",
  };
  return typeMap[anipType] ?? "String";
}

function buildDirectives(cap: ANIPCapability): string {
  const parts: string[] = [];

  // @anipSideEffect
  let se = `@anipSideEffect(type: "${cap.sideEffect}"`;
  if (cap.rollbackWindow) {
    se += `, rollbackWindow: "${cap.rollbackWindow}"`;
  }
  se += ")";
  parts.push(se);

  // @anipCost
  if (cap.cost) {
    const certainty =
      (cap.cost.certainty as string) ?? "estimate";
    let costDir = `@anipCost(certainty: "${certainty}"`;
    const financial = cap.cost.financial as
      | Record<string, unknown>
      | undefined;
    if (financial) {
      const currency = financial.currency as string | undefined;
      if (currency) {
        costDir += `, currency: "${currency}"`;
      }
      const range = financial.range as number[] | undefined;
      if (range) {
        costDir += `, rangeMin: ${range[0]}, rangeMax: ${range[1]}`;
      }
    }
    costDir += ")";
    parts.push(costDir);
  }

  // @anipRequires
  if (cap.requires && cap.requires.length > 0) {
    const capNames = cap.requires
      .map((req) => req.capability)
      .filter(Boolean)
      .map((n) => `"${n}"`);
    if (capNames.length > 0) {
      parts.push(`@anipRequires(capabilities: [${capNames.join(", ")}])`);
    }
  }

  // @anipScope
  if (cap.minimumScope && cap.minimumScope.length > 0) {
    const scopeVals = cap.minimumScope.map((s) => `"${s}"`).join(", ");
    parts.push(`@anipScope(scopes: [${scopeVals}])`);
  }

  return parts.join(" ");
}

function buildFieldArgs(cap: ANIPCapability): string {
  if (!cap.inputs || cap.inputs.length === 0) {
    return "";
  }

  const args: string[] = [];
  for (const inp of cap.inputs) {
    const name = toCamelCase(inp.name);
    let gqlType = anipTypeToGraphQL(inp.type ?? "string");
    if (inp.required) {
      gqlType += "!";
    }
    args.push(`${name}: ${gqlType}`);
  }

  return "(" + args.join(", ") + ")";
}

export function generateSchema(service: ANIPService): string {
  const lines: string[] = [];

  // Directive definitions
  lines.push(
    "directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION"
  );
  lines.push(
    "directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION"
  );
  lines.push(
    "directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION"
  );
  lines.push(
    "directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION"
  );
  lines.push("");

  // Scalar and shared types
  lines.push("scalar JSON");
  lines.push("");
  lines.push("type CostActual {");
  lines.push("  financial: FinancialCost");
  lines.push("  varianceFromEstimate: String");
  lines.push("}");
  lines.push("");
  lines.push("type FinancialCost {");
  lines.push("  amount: Float");
  lines.push("  currency: String");
  lines.push("}");
  lines.push("");
  lines.push("type ANIPFailure {");
  lines.push("  type: String!");
  lines.push("  detail: String!");
  lines.push("  resolution: Resolution");
  lines.push("  retry: Boolean!");
  lines.push("}");
  lines.push("");
  lines.push("type Resolution {");
  lines.push("  action: String!");
  lines.push("  requires: String");
  lines.push("  grantableBy: String");
  lines.push("}");
  lines.push("");

  // Per-capability result types
  const queries: string[] = [];
  const mutations: string[] = [];

  for (const [name, cap] of service.capabilities) {
    const pascal = toPascalCase(name);
    const camel = toCamelCase(name);

    // Result type
    lines.push(`type ${pascal}Result {`);
    lines.push("  success: Boolean!");
    lines.push("  result: JSON");
    lines.push("  costActual: CostActual");
    lines.push("  failure: ANIPFailure");
    lines.push("}");
    lines.push("");

    // Field with args and directives
    const args = buildFieldArgs(cap);
    const directives = buildDirectives(cap);
    const fieldLine = `  ${camel}${args}: ${pascal}Result! ${directives}`;

    if (cap.sideEffect === "read") {
      queries.push(fieldLine);
    } else {
      mutations.push(fieldLine);
    }
  }

  // Query type
  if (queries.length > 0) {
    lines.push("type Query {");
    for (const q of queries) {
      lines.push(q);
    }
    lines.push("}");
    lines.push("");
  } else {
    lines.push("type Query {");
    lines.push("  _empty: String");
    lines.push("}");
    lines.push("");
  }

  // Mutation type
  if (mutations.length > 0) {
    lines.push("type Mutation {");
    for (const m of mutations) {
      lines.push(m);
    }
    lines.push("}");
    lines.push("");
  }

  return lines.join("\n");
}
