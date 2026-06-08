import type { GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type PolicyDecision = {
  decision: "allow" | "deny" | "clarify" | "approval_required";
  detail?: string;
  resolution?: Record<string, unknown>;
};

export async function evaluatePolicy(_context: {
  capability: GeneratedCapabilityRuntimeMetadata;
  params: Record<string, unknown>;
}): Promise<PolicyDecision> {
  return { decision: "allow" };
}
