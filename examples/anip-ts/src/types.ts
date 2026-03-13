/**
 * ANIP primitive types — the core data structures of the protocol.
 *
 * TypeScript types AND Zod schemas for runtime validation.
 * Matches the Python Pydantic models exactly.
 */

import { z } from "zod";

// --- Side-effect Typing ---

export const SideEffectType = z.enum([
  "read",
  "write",
  "irreversible",
  "transactional",
]);
export type SideEffectType = z.infer<typeof SideEffectType>;

export const SideEffect = z.object({
  type: SideEffectType,
  rollback_window: z.string().nullable().default(null), // ISO 8601 duration or "none" or "not_applicable"
});
export type SideEffect = z.infer<typeof SideEffect>;

// --- Delegation Chain ---

export const Purpose = z.object({
  capability: z.string(),
  parameters: z.record(z.any()).default({}),
  task_id: z.string(),
});
export type Purpose = z.infer<typeof Purpose>;

export const ConcurrentBranches = z.enum(["allowed", "exclusive"]);
export type ConcurrentBranches = z.infer<typeof ConcurrentBranches>;

export const DelegationConstraints = z.object({
  max_delegation_depth: z.number().int().default(3),
  concurrent_branches: ConcurrentBranches.default("allowed"),
});
export type DelegationConstraints = z.infer<typeof DelegationConstraints>;

export const DelegationToken = z.object({
  token_id: z.string(),
  issuer: z.string(),
  subject: z.string(),
  scope: z.array(z.string()),
  purpose: Purpose,
  parent: z.string().nullable().default(null), // null for root tokens (issued by humans)
  expires: z.string(), // ISO 8601 datetime
  constraints: DelegationConstraints.default({
    max_delegation_depth: 3,
    concurrent_branches: "allowed",
  }),
  root_principal: z.string().nullable().default(null), // Human at root of delegation chain
});
export type DelegationToken = z.infer<typeof DelegationToken>;

// --- Capability Declaration ---

export const CapabilityInput = z.object({
  name: z.string(),
  type: z.string(),
  required: z.boolean().default(true),
  default: z.any().nullable().default(null),
  description: z.string().default(""),
});
export type CapabilityInput = z.infer<typeof CapabilityInput>;

export const CapabilityOutput = z.object({
  type: z.string(),
  fields: z.array(z.string()),
});
export type CapabilityOutput = z.infer<typeof CapabilityOutput>;

export const CostCertainty = z.enum(["fixed", "estimated", "dynamic"]);
export type CostCertainty = z.infer<typeof CostCertainty>;

export const Cost = z.object({
  certainty: CostCertainty.default("fixed"),
  financial: z.record(z.any()).nullable().default(null),
  determined_by: z.string().nullable().default(null), // capability that resolves actual cost (for estimated)
  factors: z.array(z.string()).nullable().default(null), // what drives cost variation (for dynamic)
  compute: z.record(z.any()).nullable().default(null),
  rate_limit: z.record(z.any()).nullable().default(null),
});
export type Cost = z.infer<typeof Cost>;

export const CostActual = z.object({
  financial: z.record(z.any()),
  variance_from_estimate: z.string().nullable().default(null),
});
export type CostActual = z.infer<typeof CostActual>;

export const CapabilityRequirement = z.object({
  capability: z.string(),
  reason: z.string(),
});
export type CapabilityRequirement = z.infer<typeof CapabilityRequirement>;

export const CapabilityComposition = z.object({
  capability: z.string(),
  optional: z.boolean().default(true),
});
export type CapabilityComposition = z.infer<typeof CapabilityComposition>;

export const SessionType = z.enum(["stateless", "continuation", "workflow"]);
export type SessionType = z.infer<typeof SessionType>;

export const SessionInfo = z.object({
  type: SessionType.default("stateless"),
});
export type SessionInfo = z.infer<typeof SessionInfo>;

export const ObservabilityContract = z.object({
  logged: z.boolean().default(true),
  retention: z.string().default("P90D"),
  fields_logged: z.array(z.string()).default([]),
  audit_accessible_by: z.array(z.string()).default([]),
});
export type ObservabilityContract = z.infer<typeof ObservabilityContract>;

export const CapabilityDeclaration = z.object({
  name: z.string(),
  description: z.string(),
  contract_version: z.string().default("1.0"),
  inputs: z.array(CapabilityInput),
  output: CapabilityOutput,
  side_effect: SideEffect,
  minimum_scope: z.array(z.string()), // delegation scopes needed to invoke this (AND semantics)
  cost: Cost.nullable().default(null),
  requires: z.array(CapabilityRequirement).default([]),
  composes_with: z.array(CapabilityComposition).default([]),
  session: SessionInfo.default({ type: "stateless" }),
  observability: ObservabilityContract.nullable().default(null),
});
export type CapabilityDeclaration = z.infer<typeof CapabilityDeclaration>;

// --- Permission Discovery ---

export const AvailableCapability = z.object({
  capability: z.string(),
  scope_match: z.string(),
  constraints: z.record(z.any()).default({}),
});
export type AvailableCapability = z.infer<typeof AvailableCapability>;

export const RestrictedCapability = z.object({
  capability: z.string(),
  reason: z.string(),
  grantable_by: z.string(),
});
export type RestrictedCapability = z.infer<typeof RestrictedCapability>;

export const DeniedCapability = z.object({
  capability: z.string(),
  reason: z.string(),
});
export type DeniedCapability = z.infer<typeof DeniedCapability>;

export const PermissionResponse = z.object({
  available: z.array(AvailableCapability).default([]),
  restricted: z.array(RestrictedCapability).default([]),
  denied: z.array(DeniedCapability).default([]),
});
export type PermissionResponse = z.infer<typeof PermissionResponse>;

// --- Failure Semantics ---

export const Resolution = z.object({
  action: z.string(),
  requires: z.string().nullable().default(null),
  grantable_by: z.string().nullable().default(null),
  estimated_availability: z.string().nullable().default(null),
});
export type Resolution = z.infer<typeof Resolution>;

export const ANIPFailure = z.object({
  type: z.string(),
  detail: z.string(),
  resolution: Resolution,
  retry: z.boolean().default(true),
});
export type ANIPFailure = z.infer<typeof ANIPFailure>;

// --- Trust Posture (v0.3) ---

export const AnchoringPolicy = z.object({
  cadence: z.string().nullable().optional(),
  max_lag: z.string().nullable().optional(),
  sink: z.string().nullable().optional(),
  sink_name: z.string().nullable().optional(),
});
export type AnchoringPolicy = z.infer<typeof AnchoringPolicy>;

export const TrustPolicyTrigger = z.object({
  trigger: z.record(z.unknown()),
  action: z.string(),
});
export type TrustPolicyTrigger = z.infer<typeof TrustPolicyTrigger>;

export const TrustPosture = z.object({
  level: z.enum(["signed", "anchored", "attested"]),
  anchoring: AnchoringPolicy.nullable().optional(),
  policies: z.array(TrustPolicyTrigger).nullable().optional(),
});
export type TrustPosture = z.infer<typeof TrustPosture>;

// --- Manifest ---

export const ProfileVersions = z.object({
  core: z.string().default("1.0"),
  cost: z.string().nullable().default(null),
  capability_graph: z.string().nullable().default(null),
  state_session: z.string().nullable().default(null),
  observability: z.string().nullable().default(null),
});
export type ProfileVersions = z.infer<typeof ProfileVersions>;

// --- Manifest Metadata (v0.2) ---

export const ManifestMetadata = z.object({
  version: z.string().default("0.2.0"),
  sha256: z.string(),
  issued_at: z.string(),
  expires_at: z.string(),
});
export type ManifestMetadata = z.infer<typeof ManifestMetadata>;

// --- Service Identity (v0.2) ---

export const ServiceIdentity = z.object({
  id: z.string().default("anip-flight-service"),
  jwks_uri: z.string().default("/.well-known/jwks.json"),
  issuer_mode: z.string().default("first-party"),
});
export type ServiceIdentity = z.infer<typeof ServiceIdentity>;

export const ANIPManifest = z.object({
  protocol: z.string().default("anip/0.3"),
  profile: ProfileVersions,
  capabilities: z.record(CapabilityDeclaration),
  manifest_metadata: ManifestMetadata.nullable().default(null),
  service_identity: ServiceIdentity.nullable().default(null),
  trust: TrustPosture.nullable().default(null),
});
export type ANIPManifest = z.infer<typeof ANIPManifest>;

// --- Invocation ---

export const InvokeRequest = z.object({
  delegation_token: DelegationToken,
  parameters: z.record(z.any()).default({}),
  budget: z.record(z.any()).nullable().default(null),
});
export type InvokeRequest = z.infer<typeof InvokeRequest>;

export const InvokeResponse = z.object({
  success: z.boolean(),
  result: z.record(z.any()).nullable().default(null),
  cost_actual: CostActual.nullable().default(null),
  failure: ANIPFailure.nullable().default(null),
  session: z.record(z.any()).nullable().default(null),
});
export type InvokeResponse = z.infer<typeof InvokeResponse>;

// --- Token Request (v0.2 server-side issuance) ---

export const TokenRequest = z.object({
  subject: z.string(),
  scope: z.array(z.string()),
  capability: z.string(),
  parent_token: z.string().nullable().optional(),
  purpose_parameters: z.record(z.any()).default({}),
  ttl_hours: z.number().default(2),
});
export type TokenRequest = z.infer<typeof TokenRequest>;

// --- Invoke Request V2 (JWT-based) ---

export const InvokeRequestV2 = z.object({
  token: z.string(),
  parameters: z.record(z.any()).default({}),
  budget: z.record(z.any()).nullable().default(null),
});
export type InvokeRequestV2 = z.infer<typeof InvokeRequestV2>;
