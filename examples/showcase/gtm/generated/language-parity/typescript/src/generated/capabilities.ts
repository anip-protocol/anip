import { ANIPError, defineCapability, type CapabilityDef, type InvocationContext } from "@anip-dev/service";
import { backendAdapter } from "../runtime/backend-adapter.js";
import { evaluatePolicy } from "../runtime/policy.js";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type EffectiveBackendInputContract, type GeneratedBackendBinding, type GeneratedCapabilityRuntimeMetadata } from "./runtime-target.js";

const activeSelections = readActiveSelections();

function readActiveSelections(): Record<string, { backend_kind?: string; connection_ref?: string }> {
  const raw = process.env.ANIP_ACTIVE_BACKEND_SELECTIONS_JSON;
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, { backend_kind?: string; connection_ref?: string }>;
  } catch {
    return {};
  }
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function effectiveBackendInputContract(capability: GeneratedCapabilityRuntimeMetadata, selectedBinding: GeneratedBackendBinding | null): EffectiveBackendInputContract {
  const mode = selectedBinding?.backend_input_mode || capability.backend_input_mode || "implicit";
  const derivedRequired = selectedBinding?.derived_required_backend_inputs?.length ? selectedBinding.derived_required_backend_inputs : capability.derived_required_backend_inputs;
  const derivedOptional = selectedBinding?.derived_optional_backend_inputs?.length ? selectedBinding.derived_optional_backend_inputs : capability.derived_optional_backend_inputs;
  const explicitRequired = selectedBinding?.explicit_required_backend_inputs?.length ? selectedBinding.explicit_required_backend_inputs : capability.explicit_required_backend_inputs;
  const explicitOptional = selectedBinding?.explicit_optional_backend_inputs?.length ? selectedBinding.explicit_optional_backend_inputs : capability.explicit_optional_backend_inputs;
  if (mode === "explicit") {
    const required = uniqueStrings(explicitRequired || []);
    const optional = uniqueStrings((explicitOptional || []).filter((item) => !required.includes(item)));
    return { mode: "explicit", required, optional };
  }
  if (mode === "hybrid") {
    const required = uniqueStrings([...(derivedRequired || []), ...(explicitRequired || [])]);
    const optional = uniqueStrings([...(derivedOptional || []), ...(explicitOptional || [])]).filter((item) => !required.includes(item));
    return { mode: "hybrid", required, optional };
  }
  const required = uniqueStrings(derivedRequired || []);
  const optional = uniqueStrings(derivedOptional || []).filter((item) => !required.includes(item));
  return { mode: "implicit", required, optional };
}

function selectBackendBinding(capability: GeneratedCapabilityRuntimeMetadata): GeneratedBackendBinding | null {
  if (capability.backend_bindings.length === 0) return null;
  if (capability.backend_bindings.length === 1) return capability.backend_bindings[0];
  const configured = activeSelections[capability.capability_id];
  if (!configured) return capability.backend_bindings[0];
  const selected = capability.backend_bindings.find(
    (binding) =>
      (!configured.backend_kind || configured.backend_kind === binding.backend_kind)
      && (!configured.connection_ref || configured.connection_ref === binding.connection_ref),
  );
  if (!selected) throw new Error(`Configured backend selection does not match ${capability.capability_id}.`);
  return selected;
}

function buildBackendInvocationPlan(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>): BackendInvocationPlan {
  const selectedBinding = selectBackendBinding(capability);
  const backendInputContract = effectiveBackendInputContract(capability, selectedBinding);
  const semanticKeys = new Set([
    ...capability.required_inputs.map((input) => input.input_name),
    ...capability.optional_inputs.map((input) => input.input_name),
  ]);
  const semanticInput = Object.fromEntries(Object.entries(params).filter(([key]) => semanticKeys.has(key)));
  const adapterKeys = new Set([...semanticKeys, ...backendInputContract.required, ...backendInputContract.optional]);
  const adapterInput = Object.fromEntries(Object.entries(params).filter(([key]) => adapterKeys.has(key)));
  const unresolved = backendInputContract.required.filter((key) => !(key in params));
  return {
    selected_binding: selectedBinding,
    semantic_input: semanticInput,
    adapter_input: adapterInput,
    backend_input_contract: backendInputContract,
    unresolved_required_backend_inputs: unresolved,
  };
}

function assertRequiredSemanticInputs(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  const missing = capability.required_inputs.filter((input) => !input.default_value && (params[input.input_name] === undefined || params[input.input_name] === null || params[input.input_name] === ""));
  if (missing.length === 0) return;
  throw new ANIPError(
    "clarification_required",
    `Required semantic inputs are missing for ${capability.capability_id}.`,
    {
      action: "obtain_binding",
      recovery_class: "refresh_then_retry",
      requires: missing.map((input) => input.input_name).join(","),
    },
    false,
  );
}

function applyInputDefaults(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  const normalized = { ...params };
  for (const input of [...capability.required_inputs, ...capability.optional_inputs]) {
    if (input.resolution?.on_missing === "omit") continue;
    if (input.default_value && (normalized[input.input_name] === undefined || normalized[input.input_name] === null || normalized[input.input_name] === "")) {
      normalized[input.input_name] = input.default_value;
    }
  }
  return normalized;
}

function validateInputBehavior(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  for (const input of [...capability.required_inputs, ...capability.optional_inputs]) {
    const value = params[input.input_name];
    if (value === undefined || value === null || value === "") continue;
    const allowedValues = input.allowed_values || [];
    if (allowedValues.length > 0 && !allowedValues.map(String).includes(String(value))) {
      const shouldDeny = input.resolution?.mode === "closed_values" && input.resolution?.on_unresolved === "deny";
      throw new ANIPError(
        shouldDeny ? "denied" : "clarification_required",
        input.summary || `Input ${input.input_name} must use one of the declared allowed values.`,
        {
          action: shouldDeny ? "contact_service_owner" : "obtain_binding",
          recovery_class: shouldDeny ? "terminal" : "refresh_then_retry",
          requires: input.input_name,
        },
        false,
      );
    }
  }
}

function sideEffectType(sideEffectLevel: string): "read" | "write" | "irreversible" | "transactional" {
  if (sideEffectLevel.includes("irreversible")) return "irreversible";
  if (sideEffectLevel.includes("transaction")) return "transactional";
  if (sideEffectLevel.includes("write")) return "write";
  return "read";
}

function inputResolution(value: Record<string, unknown> | undefined) {
  if (!value) return null;
  return {
    mode: value.mode as any,
    resolver_ref: typeof value.resolver_ref === "string" ? value.resolver_ref : null,
    on_missing: (value.on_missing ?? null) as any,
    on_ambiguous: (value.on_ambiguous ?? null) as any,
    on_unresolved: (value.on_unresolved ?? null) as any,
  };
}

async function handleGeneratedCapability(ctx: { rootPrincipal?: string }, capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  params = applyInputDefaults(capability, params);
  assertRequiredSemanticInputs(capability, params);
  validateInputBehavior(capability, params);
  const policy = await evaluatePolicy({ capability, params, rootPrincipal: ctx.rootPrincipal });
  if (policy.decision === "deny") {
    throw new ANIPError("denied", policy.detail || `Request denied for ${capability.capability_id}.`, policy.resolution || { action: "contact_service_owner", recovery_class: "terminal" }, false);
  }
  if (policy.decision === "clarify") {
    throw new ANIPError("clarification_required", policy.detail || `Clarification required for ${capability.capability_id}.`, policy.resolution || { action: "obtain_binding", recovery_class: "refresh_then_retry" }, false);
  }
  const plan = buildBackendInvocationPlan(capability, params);
  if (policy.decision === "approval_required") {
    let preview: Record<string, unknown> = {};
    try {
      const candidatePreview = await backendAdapter.execute(capability, plan, plan.adapter_input, {
        rootPrincipal: ctx.rootPrincipal,
      });
      preview = candidatePreview && typeof candidatePreview === "object" && !Array.isArray(candidatePreview) ? candidatePreview : {};
    } catch (err: unknown) {
      const anipError = err instanceof ANIPError ? err : null;
      if (!anipError || anipError.errorType !== "approval_required") throw err;
      const resolutionPreview = anipError.resolution?.preview;
      const suppliedPreview = anipError.approvalRequired?.preview;
      preview = suppliedPreview && typeof suppliedPreview === "object" && !Array.isArray(suppliedPreview)
        ? suppliedPreview as Record<string, unknown>
        : resolutionPreview && typeof resolutionPreview === "object" && !Array.isArray(resolutionPreview)
          ? resolutionPreview as Record<string, unknown>
          : {};
    }
    throw new ANIPError("approval_required", policy.detail || `Approval required for ${capability.capability_id}.`, {
      action: "request_approval",
      capability_id: capability.capability_id,
      semantic_input: plan.semantic_input,
      backend_input_contract: plan.backend_input_contract,
      approval_rule_refs: capability.governance.approval_rule_refs,
      preview,
    }, false, { preview });
  }
  return backendAdapter.execute(capability, plan, plan.adapter_input, {
    rootPrincipal: ctx.rootPrincipal,
  });
}

export const generatedCapabilities: CapabilityDef[] = generatedCapabilityMetadata.map((capability) => defineCapability({
  declaration: {
    name: capability.capability_id,
    description: capability.summary,
    contract_version: "1.0",
    inputs: [
      ...capability.required_inputs.map((input) => ({
        name: input.input_name,
        type: input.input_type || "string",
        required: true,
        default: input.default_value || null,
        allowed_values: input.allowed_values || [],
        semantic_type: input.semantic_type || null,
        entity_reference: Boolean(input.entity_reference),
        catalog_ref: input.catalog_ref || null,
        input_meanings: input.input_meanings || null,
        resolution: inputResolution(input.resolution),
        description: input.summary || input.input_name,
      })),
      ...capability.optional_inputs.map((input) => ({
        name: input.input_name,
        type: input.input_type || "string",
        required: false,
        default: input.default_value || null,
        allowed_values: input.allowed_values || [],
        semantic_type: input.semantic_type || null,
        entity_reference: Boolean(input.entity_reference),
        catalog_ref: input.catalog_ref || null,
        input_meanings: input.input_meanings || null,
        resolution: inputResolution(input.resolution),
        description: input.summary || input.input_name,
      })),
    ],
    output: {
      type: capability.output_shape || "governed_result",
      fields: ["execution_status", "capability_id", "semantic_input"],
    },
    side_effect: { type: sideEffectType(capability.side_effect_level), rollback_window: null },
    minimum_scope: capability.minimum_scope,
    cost: null,
    requires: [],
    composes_with: [],
    session: { type: "stateless" },
    observability: null,
    response_modes: ["unary"],
    requires_binding: [],
    control_requirements: [],
    refresh_via: [],
    verify_via: [],
    cross_service: null,
    kind: capability.kind || "atomic",
    composition: (capability.composition ?? null) as CapabilityDef["declaration"]["composition"],
    grant_policy: (capability.grant_policy ?? null) as CapabilityDef["declaration"]["grant_policy"],
  },
  handler: async (ctx: InvocationContext, params: Record<string, unknown>) => handleGeneratedCapability(ctx, capability, params),
}));

export { generatedCapabilityMetadata };
