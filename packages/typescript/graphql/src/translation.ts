/**
 * ANIP → GraphQL translation layer.
 *
 * Generates SDL schema from ANIP capabilities with custom directives,
 * camelCase field names, and query/mutation separation.
 */

export function toCamelCase(snake: string): string {
  const parts = snake.split("_");
  return parts[0] + parts.slice(1).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join("");
}

export function toSnakeCase(camel: string): string {
  return camel.replace(/([A-Z])/g, "_$1").toLowerCase().replace(/^_/, "");
}

function toPascalCase(snake: string): string {
  return snake.split("_").map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join("");
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

function buildFieldArgs(decl: Record<string, unknown>): string {
  const inputs = (decl.inputs ?? []) as Array<Record<string, unknown>>;
  if (inputs.length === 0) return "";
  const args = inputs.map((inp) => {
    const name = toCamelCase(inp.name as string);
    let gqlType = anipTypeToGraphQL((inp.type as string) ?? "string");
    if (inp.required !== false) gqlType += "!";
    return `${name}: ${gqlType}`;
  });
  return "(" + args.join(", ") + ")";
}

function buildDirectives(decl: Record<string, unknown>): string {
  const parts: string[] = [];
  const se = decl.side_effect as Record<string, unknown> | string;
  const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
  const rollback = typeof se === "string" ? null : (se as any)?.rollback_window;

  let seDir = `@anipSideEffect(type: "${seType}"`;
  if (rollback) seDir += `, rollbackWindow: "${rollback}"`;
  seDir += ")";
  parts.push(seDir);

  const cost = decl.cost as Record<string, unknown> | undefined;
  if (cost) {
    const certainty = (cost.certainty as string) ?? "estimate";
    let costDir = `@anipCost(certainty: "${certainty}"`;
    const financial = cost.financial as Record<string, unknown> | undefined;
    if (financial) {
      if (financial.currency) costDir += `, currency: "${financial.currency}"`;
      if (financial.range_min !== undefined) costDir += `, rangeMin: ${financial.range_min}`;
      if (financial.range_max !== undefined) costDir += `, rangeMax: ${financial.range_max}`;
    }
    costDir += ")";
    parts.push(costDir);
  }

  const requires = (decl.requires ?? []) as Array<Record<string, unknown>>;
  if (requires.length > 0) {
    const capNames = requires.map((r) => `"${r.capability}"`).join(", ");
    parts.push(`@anipRequires(capabilities: [${capNames}])`);
  }

  const scope = (decl.minimum_scope ?? []) as string[];
  if (scope.length > 0) {
    const scopeVals = scope.map((s) => `"${s}"`).join(", ");
    parts.push(`@anipScope(scopes: [${scopeVals}])`);
  }

  return parts.join(" ");
}

/**
 * Generate a complete GraphQL SDL schema from service capabilities.
 */
export function generateSchema(
  capabilities: Record<string, Record<string, unknown>>,
): string {
  const lines: string[] = [];

  // Directives
  lines.push('directive @anipSideEffect(type: String!, rollbackWindow: String) on FIELD_DEFINITION');
  lines.push('directive @anipCost(certainty: String!, currency: String, rangeMin: Float, rangeMax: Float) on FIELD_DEFINITION');
  lines.push('directive @anipRequires(capabilities: [String!]!) on FIELD_DEFINITION');
  lines.push('directive @anipScope(scopes: [String!]!) on FIELD_DEFINITION');
  lines.push('');
  lines.push('scalar JSON');
  lines.push('');

  // Shared types
  lines.push('type CostActual { financial: FinancialCost, varianceFromEstimate: String }');
  lines.push('type FinancialCost { amount: Float, currency: String }');
  lines.push('type ANIPFailure { type: String!, detail: String!, resolution: Resolution, retry: Boolean! }');
  lines.push('type Resolution { action: String!, requires: String, grantableBy: String }');
  lines.push('type RestrictedCapability { capability: String!, reason: String!, reasonType: String!, grantableBy: String!, unmetTokenRequirements: [String!]!, resolutionHint: String }');
  lines.push('type DeniedCapability { capability: String!, reason: String!, reasonType: String! }');
  lines.push('');

  const queries: string[] = [];
  const mutations: string[] = [];

  for (const [name, decl] of Object.entries(capabilities)) {
    const pascal = toPascalCase(name);
    const camel = toCamelCase(name);

    // Result type
    lines.push(`type ${pascal}Result { success: Boolean!, result: JSON, costActual: CostActual, failure: ANIPFailure }`);

    // Field with args and directives
    const args = buildFieldArgs(decl);
    const directives = buildDirectives(decl);
    const fieldLine = `  ${camel}${args}: ${pascal}Result! ${directives}`;

    const se = decl.side_effect as Record<string, unknown> | string;
    const seType = typeof se === "string" ? se : (se as any)?.type ?? "read";
    if (seType === "read") {
      queries.push(fieldLine);
    } else {
      mutations.push(fieldLine);
    }
  }

  lines.push('');
  if (queries.length > 0) {
    lines.push('type Query {');
    lines.push(...queries);
    lines.push('}');
  }
  if (mutations.length > 0) {
    lines.push('type Mutation {');
    lines.push(...mutations);
    lines.push('}');
  }

  return lines.join('\n');
}

/**
 * Map an ANIP invoke response to the GraphQL result shape (camelCase).
 */
export function buildGraphQLResponse(result: Record<string, unknown>): Record<string, unknown> {
  const response: Record<string, unknown> = {
    success: result.success ?? false,
    result: result.result ?? null,
    costActual: null,
    failure: null,
  };

  const costActual = result.cost_actual as Record<string, unknown> | undefined;
  if (costActual) {
    response.costActual = {
      financial: costActual.financial ?? null,
      varianceFromEstimate: costActual.variance_from_estimate ?? null,
    };
  }

  const failure = result.failure as Record<string, unknown> | undefined;
  if (failure) {
    const resolution = failure.resolution as Record<string, unknown> | undefined;
    response.failure = {
      type: failure.type ?? "unknown",
      detail: failure.detail ?? "",
      resolution: resolution ? {
        action: resolution.action ?? "",
        requires: resolution.requires ?? null,
        grantableBy: resolution.grantable_by ?? null,
      } : null,
      retry: failure.retry ?? false,
    };
  }

  return response;
}
