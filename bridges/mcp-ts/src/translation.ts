/**
 * ANIP → MCP translation layer.
 *
 * Converts ANIP capability declarations into MCP tool schemas,
 * enriching descriptions with ANIP metadata that MCP cannot
 * natively represent.
 */

import type { ANIPCapability } from "./discovery.js";

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
  capability: ANIPCapability
): MCPInputSchema {
  const properties: Record<string, Record<string, unknown>> = {};
  const required: string[] = [];

  for (const input of capability.inputs) {
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

export function enrichDescription(capability: ANIPCapability): string {
  const parts: string[] = [capability.description];

  // Side-effect warning
  if (capability.sideEffect === "irreversible") {
    parts.push("WARNING: IRREVERSIBLE action — cannot be undone.");
    if (capability.rollbackWindow === "none") {
      parts.push("No rollback window.");
    }
  } else if (capability.sideEffect === "write") {
    const rollback = capability.rollbackWindow;
    if (rollback && rollback !== "none" && rollback !== "not_applicable") {
      parts.push(`Reversible within ${rollback}.`);
    }
  } else if (capability.sideEffect === "read") {
    parts.push("Read-only, no side effects.");
  }

  // Financial cost
  if (capability.financial && capability.cost) {
    const financial = capability.cost.financial as Record<string, unknown> | undefined;
    const certainty = capability.cost.certainty as string | undefined;

    if (certainty === "fixed" && financial) {
      const amount = financial.amount as number;
      const currency = (financial.currency as string) ?? "USD";
      if (amount > 0) {
        parts.push(`Cost: ${currency} ${amount} (fixed).`);
      }
    } else if (certainty === "estimated" && financial) {
      const rangeMin = financial.range_min as number | undefined;
      const rangeMax = financial.range_max as number | undefined;
      const currency = (financial.currency as string) ?? "USD";
      if (rangeMin !== undefined && rangeMax !== undefined) {
        parts.push(`Estimated cost: ${currency} ${rangeMin}-${rangeMax}.`);
      }
    } else if (certainty === "dynamic" && financial) {
      const upperBound = financial.upper_bound as number | undefined;
      const currency = (financial.currency as string) ?? "USD";
      if (upperBound !== undefined) {
        parts.push(`Dynamic cost, up to ${currency} ${upperBound}.`);
      } else {
        parts.push("Dynamic cost — amount varies.");
      }
    }
  }

  // Prerequisites
  if (capability.requires.length > 0) {
    const prereqs = capability.requires.map((r) => r.capability);
    parts.push(`Requires calling first: ${prereqs.join(", ")}.`);
  }

  // Scope requirements
  if (capability.minimumScope.length > 0) {
    parts.push(`Delegation scope: ${capability.minimumScope.join(", ")}.`);
  }

  return parts.join(" ");
}
