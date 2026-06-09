export type ActorPolicy = {
  actor_id: string;
  role: string;
  pipeline_scope: string;
  financial_access: "full" | "masked" | string;
  enrichment_access: "full" | "bounded" | string;
  outreach_access: "full" | "bounded" | string;
  can_prepare_followup: boolean;
  can_approve_followup: boolean;
  can_use_lookalikes: boolean;
  can_route_leads: boolean;
  can_approve_routing: boolean;
  can_use_objection_variants: boolean;
};

export class ActorScopeRestriction extends Error {
  constructor(public readonly requestedScope: string, public readonly requiredScope: string) {
    super(`This actor is restricted to ${requiredScope}.`);
    this.name = "ActorScopeRestriction";
  }
}

export function claimsFromPrincipal(rootPrincipal?: string): Record<string, string> {
  const raw = (rootPrincipal || "").trim();
  if (!raw) return {};
  const pieces = raw.split("|");
  const claims: Record<string, string> = { principal: pieces[0] || "" };
  for (const piece of pieces.slice(1)) {
    const index = piece.indexOf("=");
    if (index < 0) continue;
    claims[piece.slice(0, index).trim()] = piece.slice(index + 1).trim();
  }
  return claims;
}

function boolClaim(value: string | undefined): boolean {
  return String(value || "").toLowerCase() === "true";
}

export function actorPolicyFromPrincipal(rootPrincipal?: string): ActorPolicy {
  const claims = claimsFromPrincipal(rootPrincipal);
  return {
    actor_id: claims.actor_id || "unknown",
    role: claims.role || "unknown",
    pipeline_scope: claims.pipeline_scope || "company",
    financial_access: claims.financial_access || "masked",
    enrichment_access: claims.enrichment_access || "bounded",
    outreach_access: claims.outreach_access || "bounded",
    can_prepare_followup: boolClaim(claims.can_prepare_followup),
    can_approve_followup: boolClaim(claims.can_approve_followup),
    can_use_lookalikes: boolClaim(claims.can_use_lookalikes),
    can_route_leads: boolClaim(claims.can_route_leads),
    can_approve_routing: boolClaim(claims.can_approve_routing),
    can_use_objection_variants: boolClaim(claims.can_use_objection_variants),
  };
}

export function resolveOwnerScope(explicitScope: unknown, actor: ActorPolicy): string {
  const requested = String(explicitScope || "").trim();
  const actorScope = actor.pipeline_scope || "company";
  if (requested.endsWith("-value")) return actorScope || "company";
  if (!requested || requested === "all") return actorScope || "company";
  if (actorScope === "company" || requested === actorScope) return requested;
  throw new ActorScopeRestriction(requested, actorScope);
}
