import { ANIPError } from "@anip-dev/service";
import { generatedCapabilityMetadata, type BackendInvocationPlan, type GeneratedCapabilityRuntimeMetadata } from "../generated/runtime-target.js";

export type GeneratedBackendInvocationContext = {
  rootPrincipal?: string;
};

export interface GeneratedBackendAdapter {
  execute(
    capability: GeneratedCapabilityRuntimeMetadata,
    plan: BackendInvocationPlan,
    adapterInput: Record<string, unknown>,
    context: GeneratedBackendInvocationContext,
  ): Promise<Record<string, unknown>>;
}

function readJsonObject(name: string): Record<string, string> {
  const raw = process.env[name];
  if (!raw) return {};
  const parsed = JSON.parse(raw) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
  return Object.fromEntries(
    Object.entries(parsed as Record<string, unknown>)
      .filter(([, value]) => typeof value === "string")
      .map(([key, value]) => [key, String(value)]),
  );
}

function actorIdFromPrincipal(rootPrincipal?: string): string | null {
  const raw = rootPrincipal || "";
  const match = raw.match(/(?:^|\|)actor_id=([^|]+)/);
  return match?.[1] || null;
}

function downstreamServices(): Record<string, string> {
  return {
    "gtm-pipeline-service": "http://127.0.0.1:4100",
    "gtm-enrichment-service": "http://127.0.0.1:4101",
    "gtm-prioritization-service": "http://127.0.0.1:4102",
    "gtm-outreach-service": "http://127.0.0.1:4103",
    ...readJsonObject("GTM_BACKEND_SERVICES_JSON"),
  };
}

const manifestScopeCache = new Map<string, string[]>();

async function downstreamMinimumScope(serviceUrl: string, capability: GeneratedCapabilityRuntimeMetadata): Promise<string[]> {
  const cacheKey = `${serviceUrl}|${capability.capability_id}`;
  const cached = manifestScopeCache.get(cacheKey);
  if (cached) return cached;
  try {
    const response = await fetch(`${serviceUrl.replace(/\/$/, "")}/anip/manifest`);
    const manifest = await response.json() as { capabilities?: Record<string, { minimum_scope?: unknown }> };
    const scope = manifest.capabilities?.[capability.capability_id]?.minimum_scope;
    if (Array.isArray(scope) && scope.every((item) => typeof item === "string")) {
      manifestScopeCache.set(cacheKey, scope);
      return scope;
    }
  } catch {
    // Fall back to signed package metadata when the downstream manifest is not available.
  }
  manifestScopeCache.set(cacheKey, capability.minimum_scope);
  return capability.minimum_scope;
}

function bearerForContext(context: GeneratedBackendInvocationContext): string {
  const actorId = actorIdFromPrincipal(context.rootPrincipal);
  const tokens = readJsonObject("GTM_ACTOR_TOKENS_JSON");
  const bearer = actorId ? tokens[actorId] : "";
  if (!bearer) {
    throw new ANIPError("access_denied", "No downstream GTM actor token is configured for the current actor.", {
      action: "configure_actor_token",
      actor_id: actorId,
    }, false);
  }
  return bearer;
}

async function issueDownstreamToken(serviceUrl: string, capability: GeneratedCapabilityRuntimeMetadata, bearer: string): Promise<string> {
  const scope = await downstreamMinimumScope(serviceUrl, capability);
  const response = await fetch(`${serviceUrl.replace(/\/$/, "")}/anip/tokens`, {
    method: "POST",
    headers: {
      "authorization": `Bearer ${bearer}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      subject: "agent:anip-language-parity-bridge",
      scope,
      capability: capability.capability_id,
      purpose_parameters: { source: "typescript_parity_bridge" },
    }),
  });
  const payload = await response.json() as Record<string, unknown>;
  if (!response.ok || !payload.issued || typeof payload.token !== "string") {
    throw new ANIPError("access_denied", `Downstream token issuance failed for ${capability.capability_id}.`, {
      action: "check_downstream_actor_scope",
      status: response.status,
      detail: payload,
    }, false);
  }
  return payload.token;
}

function throwDownstreamFailure(payload: Record<string, unknown>): never {
  const failure = (payload.failure && typeof payload.failure === "object" ? payload.failure : {}) as Record<string, unknown>;
  throw new ANIPError(
    String(failure.type || "backend_error"),
    String(failure.detail || "Downstream GTM service rejected the invocation."),
    (failure.resolution && typeof failure.resolution === "object" ? failure.resolution : {}) as Record<string, unknown>,
    false,
  );
}

function mapCompositionInput(mapping: unknown, source: Record<string, unknown>): Record<string, unknown> {
  if (!mapping || typeof mapping !== "object" || Array.isArray(mapping)) return source;
  const mapped: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(mapping as Record<string, unknown>)) {
    if (typeof value === "string" && value.startsWith("$.input.")) {
      const sourceKey = value.slice("$.input.".length);
      if (source[sourceKey] !== undefined) mapped[key] = source[sourceKey];
    } else {
      mapped[key] = value;
    }
  }
  return mapped;
}

function finalCompositionStep(capability: GeneratedCapabilityRuntimeMetadata): { capability: GeneratedCapabilityRuntimeMetadata; parameters: Record<string, unknown> } | null {
  if (capability.grant_policy || capability.side_effect_level === "approval_required" || capability.execution_posture === "approval_required") {
    return null;
  }
  const composition = capability.composition;
  if (!composition || typeof composition !== "object" || Array.isArray(composition)) return null;
  const steps = (composition as { steps?: unknown }).steps;
  if (!Array.isArray(steps) || steps.length === 0) return null;
  const finalStep = steps[steps.length - 1];
  if (!finalStep || typeof finalStep !== "object" || Array.isArray(finalStep)) return null;
  const childCapabilityId = String((finalStep as Record<string, unknown>).capability || "");
  const childCapability = generatedCapabilityMetadata.find((item) => item.capability_id === childCapabilityId);
  if (!childCapability) return null;
  return { capability: childCapability, parameters: {} };
}

export function createDefaultBackendAdapter(): GeneratedBackendAdapter {
  return {
    async execute(capability, plan, _adapterInput, context) {
      if (!process.env.GTM_ACTOR_TOKENS_JSON) {
        return {
          execution_status: "backend_execution_stub",
          capability_id: capability.capability_id,
          selected_backend: plan.selected_binding,
          semantic_input: plan.semantic_input,
          backend_input_contract: plan.backend_input_contract,
          note: "Set GTM_ACTOR_TOKENS_JSON to enable the TypeScript GTM parity proxy.",
        };
      }
      const sourceParams = plan.semantic_input;
      let targetCapability = capability;
      let targetParams = sourceParams;
      const finalStep = finalCompositionStep(capability);
      if (finalStep) {
        targetCapability = finalStep.capability;
        const composition = capability.composition as { input_mapping?: Record<string, unknown>; steps?: Array<Record<string, unknown>> };
        const stepId = String(composition.steps?.[composition.steps.length - 1]?.id || "");
        targetParams = mapCompositionInput(composition.input_mapping?.[stepId], sourceParams);
      }

      const serviceUrl = downstreamServices()[targetCapability.service_id];
      if (!serviceUrl) {
        throw new ANIPError("temporarily_unavailable", `No downstream GTM service URL is configured for ${targetCapability.service_id}.`, {
          action: "configure_downstream_service",
          service_id: targetCapability.service_id,
        }, false);
      }

      const bearer = bearerForContext(context);
      const token = await issueDownstreamToken(serviceUrl, targetCapability, bearer);
      const response = await fetch(`${serviceUrl.replace(/\/$/, "")}/anip/invoke/${encodeURIComponent(targetCapability.capability_id)}`, {
        method: "POST",
        headers: {
          "authorization": `Bearer ${token}`,
          "content-type": "application/json",
        },
        body: JSON.stringify({ parameters: targetParams }),
      });
      const payload = await response.json() as Record<string, unknown>;
      if (!response.ok || payload.failure) throwDownstreamFailure(payload);
      const result = payload.result;
      return result && typeof result === "object" && !Array.isArray(result)
        ? result as Record<string, unknown>
        : { result };
    },
  };
}

export const backendAdapter = createDefaultBackendAdapter();
