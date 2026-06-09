import { ANIPError, defineCapability, type CapabilityDef } from "@anip-dev/service";
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
  const unresolved = backendInputContract.required.filter((key) => !(key in params));
  return {
    selected_binding: selectedBinding,
    semantic_input: semanticInput,
    backend_input_contract: backendInputContract,
    unresolved_required_backend_inputs: unresolved,
  };
}

function assertRequiredSemanticInputs(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  const missing = capability.required_inputs.filter((input) => params[input.input_name] === undefined || params[input.input_name] === null || params[input.input_name] === "");
  if (missing.length === 0) return;
  throw new ANIPError(
    "clarification_required",
    `Required semantic inputs are missing for ${capability.capability_id}.`,
    {
      action: "clarify",
      missing_inputs: missing.map((input) => input.input_name),
      required_by: capability.capability_id,
    },
    false,
  );
}

function sideEffectType(sideEffectLevel: string): "read" | "write" | "irreversible" | "transactional" {
  if (sideEffectLevel.includes("irreversible")) return "irreversible";
  if (sideEffectLevel.includes("transaction")) return "transactional";
  if (sideEffectLevel.includes("write")) return "write";
  return "read";
}

async function handleGeneratedCapability(capability: GeneratedCapabilityRuntimeMetadata, params: Record<string, unknown>) {
  assertRequiredSemanticInputs(capability, params);
  const policy = await evaluatePolicy({ capability, params });
  if (policy.decision === "deny") {
    throw new ANIPError("access_denied", policy.detail || `Request denied for ${capability.capability_id}.`, policy.resolution, false);
  }
  if (policy.decision === "clarify") {
    throw new ANIPError("clarification_required", policy.detail || `Clarification required for ${capability.capability_id}.`, policy.resolution, false);
  }
  const plan = buildBackendInvocationPlan(capability, params);
  if (policy.decision === "approval_required" || capability.execution_posture === "approval_gated") {
    return {
      execution_status: "approval_required",
      capability_id: capability.capability_id,
      title: capability.title,
      summary: capability.summary,
      semantic_input: plan.semantic_input,
      backend_input_contract: plan.backend_input_contract,
      approval_rule_refs: capability.governance.approval_rule_refs,
      note: "Generated host requires approval before backend execution.",
    };
  }
  if (capability.execution_posture === "prepare_only") {
    return {
      execution_status: "prepared",
      capability_id: capability.capability_id,
      semantic_input: plan.semantic_input,
      backend_input_contract: plan.backend_input_contract,
      note: "Generated host prepared a governed preview and did not execute the backend.",
    };
  }
  return backendAdapter.execute(capability, plan, params);
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
        default: null,
        description: input.summary || input.input_name,
      })),
      ...capability.optional_inputs.map((input) => ({
        name: input.input_name,
        type: input.input_type || "string",
        required: false,
        default: null,
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
  },
  handler: async (_ctx, params) => handleGeneratedCapability(capability, params),
}));

export { generatedCapabilityMetadata };
