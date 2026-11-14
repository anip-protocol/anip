/**
 * Validation of invocation parameters against a capability's declared inputs.
 *
 * SPEC.md §4.1 "Inputs" and §6.3 "Parameter Validation". The check is the
 * same in every runtime: required inputs first, then the JSON type of each
 * supplied value whose declared type is one of the six primitive type names.
 * It applies no defaults and does not enforce `allowed_values` or the
 * `resolution` block; the one thing it reads from that block is whether
 * `on_missing` is set, because such an input is left to the service (§4.10).
 */
import type { CapabilityDeclaration } from "@anip-dev/core";

/** The declared type names the runtime checks. Any other name is not checked. */
export const PRIMITIVE_INPUT_TYPES = [
  "string",
  "integer",
  "number",
  "boolean",
  "array",
  "object",
] as const;

export type PrimitiveInputType = (typeof PRIMITIVE_INPUT_TYPES)[number];

/** The JSON type of a supplied value, as a failure detail names it. */
export type JsonTypeName = "string" | "number" | "boolean" | "array" | "object";

/** What a declared input has to say for the check. */
export interface DeclaredInput {
  name: string;
  type: string;
  /** Defaults to `true` (SPEC.md §4.1). */
  required?: boolean;
  /** Input resolution metadata (SPEC.md §4.10); only `on_missing` is read. */
  resolution?: { on_missing?: string | null } | null;
}

/** The resolution of every `invalid_parameters` failure. */
export const INVALID_PARAMETERS_RESOLUTION: Readonly<Record<string, string>> = Object.freeze({
  action: "retry_now",
  recovery_class: "retry_now",
  requires: "parameters that match the capability's declared inputs",
});

/** The `invalid_parameters` failure object for a refused invocation. */
export function invalidParametersFailure(detail: string): Record<string, unknown> {
  return {
    type: "invalid_parameters",
    detail,
    resolution: { ...INVALID_PARAMETERS_RESOLUTION },
    retry: false,
  };
}

/** `required` defaults to `true`: only an explicit `false` makes an input optional. */
export function isRequiredInput(input: { required?: unknown }): boolean {
  return input.required !== false;
}

/** True when the input's `resolution` block sets `on_missing` (SPEC.md §4.10). */
export function declaresOnMissing(input: { resolution?: unknown }): boolean {
  const resolution = input.resolution;
  if (typeof resolution !== "object" || resolution === null) return false;
  const onMissing = (resolution as { on_missing?: unknown }).on_missing;
  return onMissing !== null && onMissing !== undefined;
}

/**
 * True when a call that leaves the input out (or sends `null`) is refused with
 * `invalid_parameters`: the input is required and declares no `on_missing`.
 * A required input that sets `resolution.on_missing` is answered by the
 * service through that path (SPEC.md §6.3 item 1, §4.10), so nothing in front
 * of the service may demand it either: not the check below, and not a tool,
 * GraphQL or OpenAPI schema generated from the declaration.
 */
export function mustBeSupplied(input: { required?: unknown; resolution?: unknown }): boolean {
  return isRequiredInput(input) && !declaresOnMissing(input);
}

/** An absent member, `undefined` (which JSON cannot carry) and JSON `null` are all "not supplied". */
function isSupplied(parameters: Record<string, unknown>, name: string): boolean {
  if (!Object.hasOwn(parameters, name)) return false;
  const value = parameters[name];
  return value !== null && value !== undefined;
}

/** The JSON type of an in-memory value that is neither `null` nor `undefined`. */
export function jsonTypeOf(value: unknown): JsonTypeName {
  switch (typeof value) {
    case "string":
      return "string";
    case "number":
    case "bigint":
      return "number";
    case "boolean":
      return "boolean";
    default:
      return Array.isArray(value) ? "array" : "object";
  }
}

function matchesPrimitive(declared: PrimitiveInputType, value: unknown, received: JsonTypeName): boolean {
  switch (declared) {
    case "integer":
      // 5, 5.0 and 1e2 are integers; 1.5, NaN and the infinities are not.
      return typeof value === "bigint" || (typeof value === "number" && Number.isInteger(value));
    default:
      return received === declared;
  }
}

function isPrimitiveType(type: unknown): type is PrimitiveInputType {
  return (PRIMITIVE_INPUT_TYPES as readonly unknown[]).includes(type);
}

/**
 * SPEC.md §6.3: a `parameters` value that is neither an object nor null does
 * not match the request schema. Returns the failure `detail`, or `null` when
 * the value is an object, null or absent.
 */
export function checkParametersShape(capabilityName: string, parameters: unknown): string | null {
  if (parameters === null || parameters === undefined) return null;
  const received = jsonTypeOf(parameters);
  return received === "object"
    ? null
    : `${capabilityName} parameters must be an object, got ${received}`;
}

/**
 * Check `parameters`, exactly as the caller sent them, against the declared
 * inputs. Returns `null` when the call is acceptable, otherwise the `detail`
 * of the `invalid_parameters` failure.
 *
 * Absent or `null` parameters count as `{}`.
 */
export function checkDeclaredInputs(
  capabilityName: string,
  inputs: ReadonlyArray<DeclaredInput> | null | undefined,
  parameters: unknown,
): string | null {
  if (parameters !== null && parameters !== undefined) {
    const received = jsonTypeOf(parameters);
    if (received !== "object") {
      return `${capabilityName} parameters must be an object, got ${received}`;
    }
  }
  const supplied = (parameters ?? {}) as Record<string, unknown>;
  const declared = inputs ?? [];

  const missing = declared
    .filter((input) => mustBeSupplied(input) && !isSupplied(supplied, input.name))
    .map((input) => input.name);
  if (missing.length > 0) {
    return `${capabilityName} is missing required input(s): ${missing.join(", ")}`;
  }

  // SPEC.md §6.3: every key must name a declared input. Sorted as RFC 8785
  // sorts member names (UTF-16 code units, the default string order here).
  const declaredNames = new Set(declared.map((input) => input.name));
  const undeclared = Object.keys(supplied).filter((key) => !declaredNames.has(key)).sort();
  if (undeclared.length > 0) {
    return `${capabilityName} has undeclared parameter(s): ${undeclared.join(", ")}`;
  }

  const wrong: string[] = [];
  for (const input of declared) {
    if (!isSupplied(supplied, input.name)) continue;
    if (!isPrimitiveType(input.type)) continue;
    const value = supplied[input.name];
    const received = jsonTypeOf(value);
    if (!matchesPrimitive(input.type, value, received)) {
      wrong.push(`'${input.name}' must be ${input.type}, got ${received}`);
    }
  }
  if (wrong.length > 0) {
    return `${capabilityName} has invalid input(s): ${wrong.join("; ")}`;
  }
  return null;
}

/**
 * A declaration whose every input states `required` (SPEC.md §4.1:
 * serialisation always writes it). Returns the same object when nothing is
 * missing.
 */
export function withExplicitRequired(declaration: CapabilityDeclaration): CapabilityDeclaration {
  const inputs = (declaration.inputs ?? []) as Array<Record<string, unknown>>;
  if (inputs.every((input) => typeof input.required === "boolean")) return declaration;
  return {
    ...declaration,
    inputs: inputs.map((input) =>
      typeof input.required === "boolean" ? input : { ...input, required: isRequiredInput(input) },
    ),
  } as CapabilityDeclaration;
}
