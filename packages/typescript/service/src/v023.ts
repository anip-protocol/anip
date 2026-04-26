/**
 * v0.23 - Capability composition and approval grants runtime.
 *
 * TypeScript translation of `anip_service.v023` (Python). The wire-format
 * primitives - canonical JSON, SHA-256 digests, detached JWS over canonical
 * payload - match the Python module byte-for-byte so that a Python service
 * can verify a grant signed by a TS service and vice versa.
 *
 * See SPEC.md sections 4.6, 4.7, 4.8, 4.9.
 */
import { createHash, randomUUID } from "node:crypto";

import type {
  CapabilityDeclaration,
  Composition,
  CompositionStep,
} from "@anip-dev/core";
import { KeyManager, signJWSDetached, verifyJWSDetached } from "@anip-dev/crypto";
import type { StorageBackend } from "@anip-dev/server";

import { ANIPError } from "./types.js";

// ---------------------------------------------------------------------------
// Canonical JSON / digest helpers
// ---------------------------------------------------------------------------

/** Canonical JSON: sorted keys (recursive), no whitespace, UTF-8.
 *  Matches Python's `json.dumps(value, sort_keys=True, separators=(",", ":"))`. */
export function canonicalJson(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map((v) => canonicalJson(v)).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(obj[k])}`);
  return `{${parts.join(",")}}`;
}

/** SHA-256 of canonical JSON, returned as `sha256:<hex>`. */
export function sha256Digest(value: unknown): string {
  const payload = canonicalJson(value);
  return "sha256:" + createHash("sha256").update(payload, "utf8").digest("hex");
}

export function newApprovalRequestId(): string {
  return `apr_${randomUUID().replace(/-/g, "").slice(0, 12)}`;
}

export function newGrantId(): string {
  return `grant_${randomUUID().replace(/-/g, "").slice(0, 12)}`;
}

export function utcNowIso(): string {
  return new Date().toISOString();
}

export function utcInIso(seconds: number): string {
  return new Date(Date.now() + seconds * 1000).toISOString();
}

// ---------------------------------------------------------------------------
// Composition validation (registration time)
// ---------------------------------------------------------------------------

export class CompositionValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CompositionValidationError";
  }
}

const JSONPATH_INPUT_RE = /^\$\.input(?:\.[A-Za-z_][A-Za-z0-9_]*)+$/;
const JSONPATH_STEP_RE =
  /^\$\.steps\.(?<step>[A-Za-z_][A-Za-z0-9_-]*)\.output(?:\.[A-Za-z_][A-Za-z0-9_]*)+$/;

function parseStepRef(path: string): string | null {
  if (JSONPATH_INPUT_RE.test(path)) return null;
  const m = JSONPATH_STEP_RE.exec(path);
  if (m === null) {
    throw new CompositionValidationError(
      `composition_invalid_step: malformed JSONPath '${path}' (must be $.input.* or $.steps.<id>.output.*)`,
    );
  }
  return m.groups!.step;
}

export function validateComposition(
  parentName: string,
  decl: CapabilityDeclaration,
  opts: { otherCapabilities: Record<string, CapabilityDeclaration> },
): void {
  if (decl.kind !== "composed") return;
  const comp = decl.composition;
  if (comp === null || comp === undefined) {
    throw new CompositionValidationError(
      `composition_invalid_step: capability '${parentName}' declares kind='composed' but composition is missing`,
    );
  }

  if (comp.authority_boundary !== "same_service") {
    throw new CompositionValidationError(
      `composition_unsupported_authority_boundary: '${comp.authority_boundary}' is reserved in v0.23`,
    );
  }

  if (!comp.steps || comp.steps.length === 0) {
    throw new CompositionValidationError("composition_invalid_step: composition has no steps");
  }

  const stepIds = comp.steps.map((s) => s.id);
  if (new Set(stepIds).size !== stepIds.length) {
    throw new CompositionValidationError(
      `composition_invalid_step: duplicate step ids in [${stepIds.join(", ")}]`,
    );
  }

  const sources = comp.steps.filter((s) => s.empty_result_source);
  if (sources.length > 1) {
    throw new CompositionValidationError(
      "composition_invalid_step: at most one step may have empty_result_source=true",
    );
  }
  const sourceStep: CompositionStep | null = sources[0] ?? null;

  const stepIndex = new Map<string, number>();
  comp.steps.forEach((s, i) => stepIndex.set(s.id, i));

  for (const step of comp.steps) {
    if (step.capability === parentName) {
      throw new CompositionValidationError(
        `composition_invalid_step: step '${step.id}' self-references parent capability`,
      );
    }
    const target = opts.otherCapabilities[step.capability];
    if (target === undefined) {
      throw new CompositionValidationError(
        `composition_unknown_capability: step '${step.id}' references unknown capability '${step.capability}'`,
      );
    }
    if (target.kind !== "atomic") {
      throw new CompositionValidationError(
        `composition_invalid_step: step '${step.id}' references '${step.capability}' which is kind='${target.kind}'; composed capabilities may only call kind='atomic' steps in v0.23`,
      );
    }
  }

  for (const [stepKey, mapping] of Object.entries(comp.input_mapping)) {
    if (!stepIndex.has(stepKey)) {
      throw new CompositionValidationError(
        `composition_invalid_step: input_mapping key '${stepKey}' is not a declared step id`,
      );
    }
    const stepPos = stepIndex.get(stepKey)!;
    for (const [param, jp] of Object.entries(mapping)) {
      const ref = parseStepRef(jp);
      if (ref === null) continue;
      if (!stepIndex.has(ref)) {
        throw new CompositionValidationError(
          `composition_invalid_step: input_mapping['${stepKey}'].${param} references unknown step '${ref}'`,
        );
      }
      if (stepIndex.get(ref)! >= stepPos) {
        throw new CompositionValidationError(
          `composition_invalid_step: input_mapping['${stepKey}'].${param} forward-references '${ref}' (forward-only references required)`,
        );
      }
    }
  }

  for (const [field, jp] of Object.entries(comp.output_mapping)) {
    const ref = parseStepRef(jp);
    if (ref === null) continue;
    if (!stepIndex.has(ref)) {
      throw new CompositionValidationError(
        `composition_invalid_step: output_mapping['${field}'] references unknown step '${ref}'`,
      );
    }
  }

  if (sourceStep !== null && comp.empty_result_policy === null) {
    throw new CompositionValidationError(
      "composition_invalid_step: step has empty_result_source=true but composition has no empty_result_policy",
    );
  }

  if (comp.empty_result_policy === "return_success_no_results") {
    if (comp.empty_result_output === null || comp.empty_result_output === undefined) {
      throw new CompositionValidationError(
        "composition_invalid_step: empty_result_policy='return_success_no_results' requires empty_result_output",
      );
    }
    if (sourceStep === null) {
      throw new CompositionValidationError(
        "composition_invalid_step: empty_result_output requires a step with empty_result_source=true",
      );
    }
    for (const [field, value] of Object.entries(comp.empty_result_output)) {
      if (typeof value === "string" && value.startsWith("$")) {
        const ref = parseStepRef(value);
        if (ref !== null && ref !== sourceStep.id) {
          throw new CompositionValidationError(
            `composition_invalid_step: empty_result_output['${field}'] references step '${ref}' but only the empty_result_source step '${sourceStep.id}' (or $.input.*) is allowed`,
          );
        }
      }
    }
  } else if (
    (comp.empty_result_policy === "clarify" || comp.empty_result_policy === "deny") &&
    comp.empty_result_output !== null &&
    comp.empty_result_output !== undefined
  ) {
    throw new CompositionValidationError(
      `composition_invalid_step: empty_result_output is forbidden when empty_result_policy='${comp.empty_result_policy}'`,
    );
  }
}

// ---------------------------------------------------------------------------
// Composition execution (runtime)
// ---------------------------------------------------------------------------

function resolveJsonPath(
  path: string,
  ctx: { parentInput: Record<string, unknown>; stepOutputs: Record<string, Record<string, unknown>> },
): unknown {
  if (JSONPATH_INPUT_RE.test(path)) {
    const keys = path.split(".").slice(2);
    let cur: unknown = ctx.parentInput;
    for (const k of keys) {
      if (cur === null || cur === undefined || typeof cur !== "object" || !(k in (cur as object))) {
        throw new Error(`missing key '${k}' resolving '${path}'`);
      }
      cur = (cur as Record<string, unknown>)[k];
    }
    return cur;
  }
  const m = JSONPATH_STEP_RE.exec(path);
  if (m === null) {
    throw new Error(`malformed JSONPath at runtime: '${path}'`);
  }
  const step = m.groups!.step;
  const keys = path.split(".").slice(4);
  let cur: unknown = ctx.stepOutputs[step];
  if (cur === undefined) {
    throw new Error(`step '${step}' has no recorded output`);
  }
  for (const k of keys) {
    if (cur === null || cur === undefined || typeof cur !== "object" || !(k in (cur as object))) {
      throw new Error(`missing key '${k}' resolving '${path}'`);
    }
    cur = (cur as Record<string, unknown>)[k];
  }
  return cur;
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "string") return value.length === 0;
  if (typeof value === "object") return Object.keys(value as object).length === 0;
  return false;
}

function isEmptyForStep(
  step: CompositionStep,
  output: Record<string, unknown>,
  _comp: Composition,
): boolean {
  if (!output || Object.keys(output).length === 0) return true;
  if (step.empty_result_path !== null && step.empty_result_path !== undefined) {
    try {
      const keys = step.empty_result_path
        .split(".")
        .filter((k) => k !== "$" && k !== "");
      let cur: unknown = output;
      for (const k of keys) {
        if (cur === null || cur === undefined || typeof cur !== "object") return true;
        cur = (cur as Record<string, unknown>)[k];
      }
      return isEmpty(cur);
    } catch {
      return true;
    }
  }
  for (const v of Object.values(output)) {
    if (Array.isArray(v)) return v.length === 0;
  }
  return Object.values(output).every((v) => isEmpty(v));
}

function failureOutcome(failureType: string, policy: Composition["failure_policy"]): string {
  if (failureType === "approval_required") return policy.child_approval_required;
  if (
    failureType === "scope_insufficient" ||
    failureType === "denied" ||
    failureType === "non_delegable_action"
  ) {
    return policy.child_denial;
  }
  if (
    failureType === "binding_missing" ||
    failureType === "binding_stale" ||
    failureType === "control_requirement_unsatisfied" ||
    failureType === "purpose_mismatch" ||
    failureType === "invalid_parameters"
  ) {
    return policy.child_clarification;
  }
  return policy.child_error;
}

function resolveEmptyRef(
  path: string,
  parentInput: Record<string, unknown>,
  sourceOutput: Record<string, unknown>,
): unknown {
  if (JSONPATH_INPUT_RE.test(path)) {
    const keys = path.split(".").slice(2);
    let cur: unknown = parentInput;
    for (const k of keys) {
      if (cur === null || cur === undefined || typeof cur !== "object") {
        throw new Error(`missing key '${k}' resolving '${path}'`);
      }
      cur = (cur as Record<string, unknown>)[k];
    }
    return cur;
  }
  const m = JSONPATH_STEP_RE.exec(path);
  if (m === null) throw new Error(`malformed JSONPath: '${path}'`);
  const keys = path.split(".").slice(4);
  let cur: unknown = sourceOutput;
  for (const k of keys) {
    if (cur === null || cur === undefined || typeof cur !== "object") {
      throw new Error(`missing key '${k}' resolving '${path}'`);
    }
    cur = (cur as Record<string, unknown>)[k];
  }
  return cur;
}

function buildEmptyResultResponse(
  comp: Composition,
  parentInput: Record<string, unknown>,
  sourceOutput: Record<string, unknown>,
): Record<string, unknown> {
  if (comp.empty_result_policy === "clarify") {
    throw new ANIPError(
      "composition_empty_result_clarification_required",
      "selection step returned no results; clarification required",
    );
  }
  if (comp.empty_result_policy === "deny") {
    throw new ANIPError(
      "composition_empty_result_denied",
      "selection step returned no results; policy denies an empty answer",
    );
  }
  const out: Record<string, unknown> = {};
  const empty = comp.empty_result_output ?? {};
  for (const [field, value] of Object.entries(empty)) {
    if (typeof value === "string" && value.startsWith("$")) {
      try {
        out[field] = resolveEmptyRef(value, parentInput, sourceOutput);
      } catch {
        out[field] = null;
      }
    } else {
      out[field] = value;
    }
  }
  return out;
}

function buildOutput(
  mapping: Record<string, string>,
  ctx: { parentInput: Record<string, unknown>; stepOutputs: Record<string, Record<string, unknown>> },
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [field, jp] of Object.entries(mapping)) {
    try {
      out[field] = resolveJsonPath(jp, ctx);
    } catch {
      out[field] = null;
    }
  }
  return out;
}

export type InvokeStepFn = (
  capability: string,
  params: Record<string, unknown>,
) => Promise<Record<string, unknown>>;

export async function executeComposition(
  parentName: string,
  decl: CapabilityDeclaration,
  parentInput: Record<string, unknown>,
  opts: { invokeStep: InvokeStepFn },
): Promise<Record<string, unknown>> {
  const comp = decl.composition;
  if (comp === null || comp === undefined) {
    throw new Error(`capability '${parentName}' has no composition`);
  }
  const sourceStep = comp.steps.find((s) => s.empty_result_source) ?? null;
  const stepOutputs: Record<string, Record<string, unknown>> = {};

  for (const step of comp.steps) {
    const mapping = comp.input_mapping[step.id] ?? {};
    const stepInput: Record<string, unknown> = {};
    for (const [param, jp] of Object.entries(mapping)) {
      try {
        stepInput[param] = resolveJsonPath(jp, { parentInput, stepOutputs });
      } catch {
        stepInput[param] = null;
      }
    }

    const result = await opts.invokeStep(step.capability, stepInput);
    if (!result.success) {
      const failure = (result.failure as Record<string, unknown> | undefined) ?? {};
      const failureType = (failure.type as string | undefined) ?? "unknown";
      const outcome = failureOutcome(failureType, comp.failure_policy);
      if (outcome === "fail_parent") {
        throw new ANIPError(
          "composition_child_failed",
          `child step '${step.id}' (${step.capability}) failed with ${failureType}: ${
            (failure.detail as string | undefined) ?? ""
          }`,
          { action: "contact_service_owner", recovery_class: "terminal" },
        );
      }
      const approvalRequired = failure.approval_required as Record<string, unknown> | null | undefined;
      throw new ANIPError(
        failureType,
        (failure.detail as string | undefined) ?? "child step failed",
        failure.resolution as Record<string, unknown> | undefined,
        false,
        approvalRequired ?? null,
      );
    }

    const stepResult = (result.result as Record<string, unknown> | undefined) ?? {};
    stepOutputs[step.id] = stepResult;

    if (step === sourceStep && isEmptyForStep(step, stepResult, comp)) {
      return buildEmptyResultResponse(comp, parentInput, stepResult);
    }
  }

  return buildOutput(comp.output_mapping, { parentInput, stepOutputs });
}

// ---------------------------------------------------------------------------
// Approval grants - signing + validation
// ---------------------------------------------------------------------------

export async function signGrant(
  grant: Record<string, unknown>,
  opts: { keyManager: KeyManager },
): Promise<string> {
  const payload: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(grant)) {
    if (k !== "signature" && k !== "use_count") payload[k] = v;
  }
  const canon = new TextEncoder().encode(canonicalJson(payload));
  return signJWSDetached(opts.keyManager, canon);
}

export async function verifyGrantSignature(
  grant: Record<string, unknown>,
  opts: { keyManager: KeyManager },
): Promise<boolean> {
  const payload: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(grant)) {
    if (k !== "signature" && k !== "use_count") payload[k] = v;
  }
  const canon = new TextEncoder().encode(canonicalJson(payload));
  try {
    await verifyJWSDetached(opts.keyManager, grant.signature as string, canon);
    return true;
  } catch {
    return false;
  }
}

export function grantScopeSubsetOfToken(grantScope: string[], tokenScope: string[]): boolean {
  return grantScope.every((s) => tokenScope.includes(s));
}

// ---------------------------------------------------------------------------
// v0.23 failure types
// ---------------------------------------------------------------------------

export const FAILURE_GRANT_NOT_FOUND = "grant_not_found";
export const FAILURE_GRANT_EXPIRED = "grant_expired";
export const FAILURE_GRANT_CONSUMED = "grant_consumed";
export const FAILURE_GRANT_CAPABILITY_MISMATCH = "grant_capability_mismatch";
export const FAILURE_GRANT_SCOPE_MISMATCH = "grant_scope_mismatch";
export const FAILURE_GRANT_PARAM_DRIFT = "grant_param_drift";
export const FAILURE_GRANT_SESSION_INVALID = "grant_session_invalid";

export const FAILURE_APPROVAL_REQUEST_NOT_FOUND = "approval_request_not_found";
export const FAILURE_APPROVAL_REQUEST_ALREADY_DECIDED = "approval_request_already_decided";
export const FAILURE_APPROVAL_REQUEST_EXPIRED = "approval_request_expired";
export const FAILURE_APPROVER_NOT_AUTHORIZED = "approver_not_authorized";
export const FAILURE_GRANT_TYPE_NOT_ALLOWED_BY_POLICY = "grant_type_not_allowed_by_policy";

export const FAILURE_COMPOSITION_INVALID_STEP = "composition_invalid_step";
export const FAILURE_COMPOSITION_UNKNOWN_CAPABILITY = "composition_unknown_capability";
export const FAILURE_COMPOSITION_UNSUPPORTED_AUTHORITY_BOUNDARY =
  "composition_unsupported_authority_boundary";
export const FAILURE_COMPOSITION_EMPTY_RESULT_CLARIFICATION_REQUIRED =
  "composition_empty_result_clarification_required";
export const FAILURE_COMPOSITION_EMPTY_RESULT_DENIED = "composition_empty_result_denied";

// ---------------------------------------------------------------------------
// ApprovalRequest materialization + grant validation
// ---------------------------------------------------------------------------

export async function materializeApprovalRequest(opts: {
  storage: StorageBackend;
  capabilityDecl: CapabilityDeclaration;
  parentInvocationId: string | null;
  requester: Record<string, unknown>;
  parameters: Record<string, unknown>;
  preview: Record<string, unknown>;
  serviceDefaultGrantPolicy?: Record<string, unknown> | null;
}): Promise<Record<string, unknown>> {
  let gp: Record<string, unknown>;
  if (opts.capabilityDecl.grant_policy !== null && opts.capabilityDecl.grant_policy !== undefined) {
    gp = { ...(opts.capabilityDecl.grant_policy as Record<string, unknown>) };
  } else if (opts.serviceDefaultGrantPolicy) {
    gp = { ...opts.serviceDefaultGrantPolicy };
  } else {
    throw new Error(
      `capability '${opts.capabilityDecl.name}' raised approval_required but has no grant_policy declared and no service-level default exists`,
    );
  }

  const requestId = newApprovalRequestId();
  const request: Record<string, unknown> = {
    approval_request_id: requestId,
    capability: opts.capabilityDecl.name,
    scope: [...opts.capabilityDecl.minimum_scope],
    requester: opts.requester,
    parent_invocation_id: opts.parentInvocationId,
    preview: opts.preview,
    preview_digest: sha256Digest(opts.preview),
    requested_parameters: opts.parameters,
    requested_parameters_digest: sha256Digest(opts.parameters),
    grant_policy: gp,
    status: "pending",
    approver: null,
    decided_at: null,
    created_at: utcNowIso(),
    expires_at: utcInIso(gp.expires_in_seconds as number),
  };
  await opts.storage.storeApprovalRequest(request);

  return {
    approval_request_id: requestId,
    preview_digest: request.preview_digest,
    requested_parameters_digest: request.requested_parameters_digest,
    grant_policy: gp,
  };
}

export async function validateContinuationGrant(opts: {
  storage: StorageBackend;
  grantId: string;
  capability: string;
  parameters: Record<string, unknown>;
  tokenScope: string[];
  tokenSessionId: string | null;
  keyManager: KeyManager;
  nowIso: string;
}): Promise<[Record<string, unknown> | null, string | null]> {
  const grant = await opts.storage.getGrant(opts.grantId);
  if (grant === null) return [null, FAILURE_GRANT_NOT_FOUND];
  const sigOk = await verifyGrantSignature(grant, { keyManager: opts.keyManager });
  if (!sigOk) return [null, FAILURE_GRANT_NOT_FOUND];
  if ((grant.expires_at as string) <= opts.nowIso) return [null, FAILURE_GRANT_EXPIRED];
  if (grant.capability !== opts.capability) return [null, FAILURE_GRANT_CAPABILITY_MISMATCH];
  if (!grantScopeSubsetOfToken(grant.scope as string[], opts.tokenScope)) {
    return [null, FAILURE_GRANT_SCOPE_MISMATCH];
  }
  const submittedDigest = sha256Digest(opts.parameters);
  if (submittedDigest !== grant.approved_parameters_digest) {
    return [null, FAILURE_GRANT_PARAM_DRIFT];
  }
  if (grant.grant_type === "session_bound") {
    if (opts.tokenSessionId !== (grant.session_id ?? null)) {
      return [null, FAILURE_GRANT_SESSION_INVALID];
    }
  }
  return [grant, null];
}
