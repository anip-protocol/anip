/**
 * ANIP → MCP translation layer.
 *
 * Converts ANIP capability declarations into MCP tool schemas,
 * enriching descriptions with ANIP metadata that MCP cannot
 * natively represent.
 */
import type { CapabilityDeclaration } from "@anip/core";

const TYPE_MAP: Record<string, string> = {
  string: "string",
  integer: "integer",
  number: "number",
  boolean: "boolean",
  date: "string",
  airport_code: "string",
};

export interface MCPInputSchema {
  type: "object";
  properties: Record<string, Record<string, unknown>>;
  required?: string[];
  [key: string]: unknown;
}

export function capabilityToInputSchema(
  declaration: CapabilityDeclaration,
): MCPInputSchema {
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  for (const input of declaration.inputs) {
    const jsonType = TYPE_MAP[input.type] ?? "string";
    const prop: Record<string, unknown> = {
      type: jsonType,
      description: input.description ?? "",
    };
    if (input.type === "date") {
      prop.format = "date";
    }
    if (input.default !== undefined && input.default !== null) {
      prop.default = input.default;
    }
    properties[input.name] = prop;
    if (input.required !== false) {
      required.push(input.name);
    }
  }

  const schema: MCPInputSchema = { type: "object", properties };
  if (required.length > 0) {
    schema.required = required;
  }
  return schema;
}

export function enrichDescription(declaration: CapabilityDeclaration): string {
  const parts: string[] = [declaration.description];
  const se = declaration.side_effect;
  const seType = typeof se === "string" ? se : se.type;
  const rollback = typeof se === "string" ? null : se.rollback_window;

  if (seType === "irreversible") {
    parts.push("WARNING: IRREVERSIBLE action — cannot be undone.");
    if (rollback === "none") {
      parts.push("No rollback window.");
    }
  } else if (seType === "write") {
    if (rollback && rollback !== "none" && rollback !== "not_applicable") {
      parts.push(`Reversible within ${rollback}.`);
    }
  } else if (seType === "read") {
    parts.push("Read-only, no side effects.");
  }

  const cost = declaration.cost as Record<string, unknown> | undefined;
  if (cost) {
    const financial = cost.financial as Record<string, unknown> | undefined;
    const certainty = cost.certainty as string | undefined;
    if (certainty === "fixed" && financial) {
      const amount = financial.amount as number;
      const currency = (financial.currency as string) ?? "USD";
      if (amount > 0) parts.push(`Cost: ${currency} ${amount} (fixed).`);
    } else if (certainty === "estimated" && financial) {
      const rangeMin = financial.range_min as number | undefined;
      const rangeMax = financial.range_max as number | undefined;
      const currency = (financial.currency as string) ?? "USD";
      if (rangeMin !== undefined && rangeMax !== undefined) {
        parts.push(`Estimated cost: ${currency} ${rangeMin}-${rangeMax}.`);
      }
    }
  }

  const requires = declaration.requires ?? [];
  if (requires.length > 0) {
    const prereqs = requires.map((r: any) => r.capability);
    parts.push(`Requires calling first: ${prereqs.join(", ")}.`);
  }

  const scope = declaration.minimum_scope ?? [];
  if (scope.length > 0) {
    parts.push(`Delegation scope: ${scope.join(", ")}.`);
  }

  return parts.join(" ");
}
