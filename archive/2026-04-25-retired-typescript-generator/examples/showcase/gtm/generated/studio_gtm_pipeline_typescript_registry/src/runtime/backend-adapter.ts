import type { BackendInvocationPlan, GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export interface GeneratedBackendAdapter {
  execute(capability: GeneratedCapabilityRuntimeMetadata, plan: BackendInvocationPlan, params: Record<string, unknown>): Promise<Record<string, unknown>>;
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, _params) {
      if (plan.unresolved_required_backend_inputs.length > 0) {
        return {
          execution_status: "backend_input_incomplete",
          capability_id: capability.capability_id,
          backend_input_contract: plan.backend_input_contract,
          unresolved_required_backend_inputs: plan.unresolved_required_backend_inputs,
          note: "Generated host is runnable, but backend-only inputs still require extension completion.",
        };
      }
      return {
        execution_status: "backend_execution_stub",
        capability_id: capability.capability_id,
        selected_backend: plan.selected_binding,
        semantic_input: plan.semantic_input,
        backend_input_contract: plan.backend_input_contract,
        note: "Replace createDefaultBackendAdapter() with provider-specific backend execution.",
      };
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
