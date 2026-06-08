import { runtimeTarget, type GeneratedCapabilityRuntimeMetadata, type GeneratedPolicyBinding } from "../generated/runtime-target.js";

export type PolicyDecision = {
  decision: "allow" | "deny" | "clarify" | "approval_required";
  detail?: string;
  resolution?: Record<string, unknown>;
};

const policyBindings = ((runtimeTarget as unknown as { policy_bindings?: GeneratedPolicyBinding[] }).policy_bindings ?? []);

function principalClaims(rootPrincipal?: string): Record<string, string> {
  const raw = (rootPrincipal ?? "").trim();
  if (!raw) return {};
  const pieces = raw.split("|");
  const claims: Record<string, string> = { principal: pieces[0] ?? "" };
  for (const piece of pieces.slice(1)) {
    const index = piece.indexOf("=");
    if (index < 0) continue;
    claims[piece.slice(0, index).trim()] = piece.slice(index + 1).trim();
  }
  return claims;
}

function matchesPrincipal(binding: GeneratedPolicyBinding, claims: Record<string, string>): boolean {
  const selector = binding.principal_selector ?? {};
  const claim = selector.claim || "actor_id";
  const expected = selector.equals || binding.actor_id || "";
  if (!expected) return true;
  if (!(claim in claims)) return false;
  return claims[claim] === expected;
}

function requiresGovernedStop(capability: GeneratedCapabilityRuntimeMetadata): boolean {
  return Boolean(capability.grant_policy)
    || capability.side_effect_level === "approval_required"
    || capability.execution_posture === "approval_required"
    || capability.operation_type === "approval_gated";
}

function decisionFor(binding: GeneratedPolicyBinding): PolicyDecision {
  const detail = binding.business_rule || binding.enforcement_notes;
  if (binding.decision === "deny" || binding.decision === "clarify" || binding.decision === "approval_required") {
    return { decision: binding.decision, detail };
  }
  return { decision: "allow", detail };
}

export async function evaluatePolicy(context: {
  capability: GeneratedCapabilityRuntimeMetadata;
  params: Record<string, unknown>;
  rootPrincipal?: string;
}): Promise<PolicyDecision> {
  const bindings = policyBindings.filter((binding) => binding.capability_ids?.includes(context.capability.capability_id));
  if (bindings.length === 0) return { decision: "allow" };
  const claims = principalClaims(context.rootPrincipal);
  if (Object.keys(claims).length === 0) return { decision: "allow" };
  const matching = bindings.filter((binding) => matchesPrincipal(binding, claims));
  if (requiresGovernedStop(context.capability)) {
    const denied = matching.find((binding) => binding.decision === "deny");
    if (denied) return decisionFor(denied);
    const approval = matching.find((binding) => binding.decision === "approval_required");
    if (approval) return decisionFor(approval);
    const clarify = matching.find((binding) => binding.decision === "clarify");
    if (clarify) return decisionFor(clarify);
  }
  const allowed = matching.find((binding) => binding.decision !== "deny" && binding.decision !== "clarify" && binding.decision !== "approval_required");
  if (allowed) return decisionFor(allowed);
  return { decision: "allow", detail: "No matching runtime policy binding; continuing." };
}
