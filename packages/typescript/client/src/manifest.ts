/**
 * Manifest normalization — maps raw ANIP manifest payloads into a
 * consumer-friendly shape with capability lookup.
 */

import type { NormalizedManifest, NormalizedCapability } from "./types.js";

/**
 * Normalize a single raw capability declaration from the manifest.
 */
export function normalizeCapability(name: string, raw: any): NormalizedCapability {
  const sideEffect: NormalizedCapability["sideEffect"] = {
    type: raw.side_effect?.type ?? "read",
    rollbackWindow: raw.side_effect?.rollback_window ?? undefined,
  };

  let cost: NormalizedCapability["cost"] | undefined;
  if (raw.cost?.financial) {
    const fin = raw.cost.financial;
    // Derive a single estimated amount from whichever cost field is present.
    const estimatedAmount: number =
      fin.amount ?? fin.typical ?? fin.range_max ?? fin.upper_bound ?? 0;
    cost = {
      financial: {
        currency: fin.currency ?? "USD",
        estimatedAmount,
      },
    };
  }

  let controlRequirements: NormalizedCapability["controlRequirements"] | undefined;
  if (Array.isArray(raw.control_requirements) && raw.control_requirements.length > 0) {
    controlRequirements = raw.control_requirements.map((cr: any) => ({
      type: cr.type,
      enforcement: cr.enforcement ?? "reject",
    }));
  }

  let crossServiceContract: NormalizedCapability["crossServiceContract"] | undefined;
  if (raw.cross_service_contract) {
    const csc = raw.cross_service_contract;
    crossServiceContract = {};
    if (Array.isArray(csc.handoff) && csc.handoff.length > 0) {
      crossServiceContract.handoff = csc.handoff.map((h: any) => ({
        service: h.target?.service ?? "",
        capability: h.target?.capability ?? "",
        requiredForTaskCompletion: h.required_for_task_completion ?? false,
      }));
    }
    if (Array.isArray(csc.followup) && csc.followup.length > 0) {
      crossServiceContract.followup = csc.followup.map((f: any) => ({
        service: f.target?.service ?? "",
        capability: f.target?.capability ?? "",
      }));
    }
    if (Array.isArray(csc.verification) && csc.verification.length > 0) {
      crossServiceContract.verification = csc.verification.map((v: any) => ({
        service: v.target?.service ?? "",
        capability: v.target?.capability ?? "",
      }));
    }
  }

  let graph: NormalizedCapability["graph"] | undefined;
  if (
    (Array.isArray(raw.requires) && raw.requires.length > 0) ||
    (Array.isArray(raw.composes_with) && raw.composes_with.length > 0)
  ) {
    graph = {};
    if (Array.isArray(raw.requires) && raw.requires.length > 0) {
      graph.requires = raw.requires.map((r: any) => ({
        capability: r.capability,
        reason: r.reason ?? "",
      }));
    }
    if (Array.isArray(raw.composes_with) && raw.composes_with.length > 0) {
      graph.composesWith = raw.composes_with.map((c: any) => ({
        capability: c.capability,
        optional: c.optional ?? true,
      }));
    }
  }

  return {
    name,
    description: raw.description ?? "",
    minimumScope: Array.isArray(raw.minimum_scope) ? raw.minimum_scope : [],
    sideEffect,
    responseModes: Array.isArray(raw.response_modes) ? raw.response_modes : ["unary"],
    cost,
    controlRequirements,
    crossServiceContract,
    graph,
  };
}

/**
 * Normalize a raw ANIP manifest payload.
 *
 * Expected wire format matches the ANIPManifest schema: protocol, profile,
 * capabilities record, etc.
 */
export function normalizeManifest(raw: any): NormalizedManifest {
  if (!raw || typeof raw !== "object") {
    return { protocol: "unknown", capabilities: {} };
  }

  const capabilities: Record<string, NormalizedCapability> = {};
  if (raw.capabilities && typeof raw.capabilities === "object") {
    for (const [name, decl] of Object.entries(raw.capabilities)) {
      capabilities[name] = normalizeCapability(name, decl);
    }
  }

  return {
    protocol: raw.protocol ?? "unknown",
    capabilities,
  };
}
