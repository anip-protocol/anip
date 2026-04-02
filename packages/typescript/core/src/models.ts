/**
 * ANIP protocol models — Zod schemas and inferred TypeScript types.
 *
 * Extracted from the reference implementation in examples/anip-ts/src/types.ts.
 * All schemas are re-exported from the package root via index.ts.
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Side-effect Typing
// ---------------------------------------------------------------------------

export const SideEffectType = z.enum([
  "read",
  "write",
  "irreversible",
  "transactional",
]);
export type SideEffectType = z.infer<typeof SideEffectType>;

export const SideEffect = z.object({
  type: SideEffectType,
  rollback_window: z.string().nullable().default(null),
});
export type SideEffect = z.infer<typeof SideEffect>;

// ---------------------------------------------------------------------------
// Delegation Chain
// ---------------------------------------------------------------------------

export const Purpose = z.object({
  capability: z.string(),
  parameters: z.record(z.any()).default({}),
  task_id: z.string().nullable().default(null),
});
export type Purpose = z.infer<typeof Purpose>;

export const ConcurrentBranches = z.enum(["allowed", "exclusive"]);
export type ConcurrentBranches = z.infer<typeof ConcurrentBranches>;

export const Budget = z.object({
  currency: z.string(),
  max_amount: z.number(),
});
export type Budget = z.infer<typeof Budget>;

export const DelegationConstraints = z.object({
  max_delegation_depth: z.number().int().default(3),
  concurrent_branches: ConcurrentBranches.default("allowed"),
  budget: Budget.nullable().default(null),
});
export type DelegationConstraints = z.infer<typeof DelegationConstraints>;

export const DelegationToken = z.object({
  token_id: z.string(),
  issuer: z.string(),
  subject: z.string(),
  scope: z.array(z.string()),
  purpose: Purpose,
  parent: z.string().nullable().default(null),
  expires: z.string(),
  constraints: DelegationConstraints.default({
    max_delegation_depth: 3,
    concurrent_branches: "allowed",
  }),
  root_principal: z.string().nullable().default(null),
  caller_class: z.string().nullable().default(null),
});
export type DelegationToken = z.infer<typeof DelegationToken>;

// ---------------------------------------------------------------------------
// Capability Declaration
// ---------------------------------------------------------------------------

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

export const FinancialCost = z.object({
  currency: z.string(),
  amount: z.number().nullable().default(null),        // fixed costs
  range_min: z.number().nullable().default(null),      // estimated costs
  range_max: z.number().nullable().default(null),      // estimated costs
  typical: z.number().nullable().default(null),        // estimated costs
  upper_bound: z.number().nullable().default(null),    // dynamic costs
});
export type FinancialCost = z.infer<typeof FinancialCost>;

export const Cost = z.object({
  certainty: CostCertainty.default("fixed"),
  financial: FinancialCost.nullable().default(null),
  determined_by: z.string().nullable().default(null),
  factors: z.array(z.string()).nullable().default(null),
  compute: z.record(z.any()).nullable().default(null),
  rate_limit: z.record(z.any()).nullable().default(null),
});
export type Cost = z.infer<typeof Cost>;

export const CostActual = z.object({
  financial: FinancialCost,
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

export const ResponseMode = z.enum(["unary", "streaming"]);
export type ResponseMode = z.infer<typeof ResponseMode>;

export const BindingRequirement = z.object({
  type: z.string(),        // "quote", "offer", "price_lock"
  field: z.string(),       // which param must carry the reference
  source_capability: z.string().nullable().default(null),  // advisory
  max_age: z.string().nullable().default(null),            // ISO 8601 duration
});
export type BindingRequirement = z.infer<typeof BindingRequirement>;

export const ControlRequirement = z.object({
  type: z.string(),        // "cost_ceiling", "stronger_delegation_required"
  enforcement: z.string().default("reject"),  // v0.14: "reject" only
});
export type ControlRequirement = z.infer<typeof ControlRequirement>;

export const BudgetContext = z.object({
  budget_max: z.number(),
  budget_currency: z.string(),
  cost_check_amount: z.number().nullable().default(null),
  cost_certainty: z.string().nullable().default(null),
  cost_actual: z.number().nullable().default(null),
  within_budget: z.boolean().nullable().default(null),
});
export type BudgetContext = z.infer<typeof BudgetContext>;

export const CapabilityDeclaration = z.object({
  name: z.string(),
  description: z.string(),
  contract_version: z.string().default("1.0"),
  inputs: z.array(CapabilityInput),
  output: CapabilityOutput,
  side_effect: SideEffect,
  minimum_scope: z.array(z.string()),
  cost: Cost.nullable().default(null),
  requires: z.array(CapabilityRequirement).default([]),
  composes_with: z.array(CapabilityComposition).default([]),
  session: SessionInfo.default({ type: "stateless" }),
  observability: ObservabilityContract.nullable().default(null),
  response_modes: z.array(ResponseMode).min(1).default(["unary"]),
  requires_binding: z.array(BindingRequirement).default([]),
  control_requirements: z.array(ControlRequirement).default([]),
  refresh_via: z.array(z.string()).default([]),
  verify_via: z.array(z.string()).default([]),
});
export type CapabilityDeclaration = z.infer<typeof CapabilityDeclaration>;

// ---------------------------------------------------------------------------
// Permission Discovery
// ---------------------------------------------------------------------------

export const AvailableCapability = z.object({
  capability: z.string(),
  scope_match: z.string(),
  constraints: z.record(z.any()).default({}),
});
export type AvailableCapability = z.infer<typeof AvailableCapability>;

export const RestrictedCapability = z.object({
  capability: z.string(),
  reason: z.string(),
  reason_type: z.string(),
  grantable_by: z.string(),
  unmet_token_requirements: z.array(z.string()).default([]),
  resolution_hint: z.string().nullable().default(null),
});
export type RestrictedCapability = z.infer<typeof RestrictedCapability>;

export const DeniedCapability = z.object({
  capability: z.string(),
  reason: z.string(),
  reason_type: z.string(),
});
export type DeniedCapability = z.infer<typeof DeniedCapability>;

export const PermissionResponse = z.object({
  available: z.array(AvailableCapability).default([]),
  restricted: z.array(RestrictedCapability).default([]),
  denied: z.array(DeniedCapability).default([]),
});
export type PermissionResponse = z.infer<typeof PermissionResponse>;

// ---------------------------------------------------------------------------
// Failure Semantics
// ---------------------------------------------------------------------------

export const Resolution = z.object({
  action: z.string(),
  recovery_class: z.string(),
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

// ---------------------------------------------------------------------------
// Trust Posture (v0.3)
// ---------------------------------------------------------------------------

export const AnchoringPolicy = z.object({
  cadence: z.string().nullable().optional(),
  max_lag: z.number().nullable().optional(),
  sink: z.array(z.string()).nullable().optional(),
});
export type AnchoringPolicy = z.infer<typeof AnchoringPolicy>;

export const TrustPolicyTrigger = z.object({
  trigger: z.record(z.unknown()),
  action: z.string(),
});
export type TrustPolicyTrigger = z.infer<typeof TrustPolicyTrigger>;

export const TrustPosture = z.object({
  level: z.enum(["signed", "anchored", "attested"]).default("signed"),
  anchoring: AnchoringPolicy.nullable().optional(),
  policies: z.array(TrustPolicyTrigger).nullable().optional(),
});
export type TrustPosture = z.infer<typeof TrustPosture>;

// ---------------------------------------------------------------------------
// Security Hardening Enums (v0.8)
// ---------------------------------------------------------------------------

export const EventClass = z.enum([
  "high_risk_success",
  "high_risk_denial",
  "low_risk_success",
  "repeated_low_value_denial",
  "malformed_or_spam",
]);
export type EventClass = z.infer<typeof EventClass>;

export const RetentionTier = z.enum([
  "long",
  "medium",
  "short",
  "aggregate_only",
]);
export type RetentionTier = z.infer<typeof RetentionTier>;

export const DisclosureLevel = z.enum(["full", "reduced", "redacted", "policy"]);
export type DisclosureLevel = z.infer<typeof DisclosureLevel>;

// ---------------------------------------------------------------------------
// Discovery Posture (v0.7)
// ---------------------------------------------------------------------------

export const AuditPosture = z.object({
  enabled: z.boolean().default(true),
  signed: z.boolean().default(true),
  queryable: z.boolean().default(true),
  retention: z.string().default("P90D"),
  retention_enforced: z.boolean().default(false),
});
export type AuditPosture = z.infer<typeof AuditPosture>;

export const ClientReferenceIdPosture = z.object({
  supported: z.boolean().default(true),
  max_length: z.number().int().default(256),
  opaque: z.boolean().default(true),
  propagation: z.enum(["bounded", "local_only", "policy"]).default("bounded"),
});
export type ClientReferenceIdPosture = z.infer<typeof ClientReferenceIdPosture>;

export const LineagePosture = z.object({
  invocation_id: z.boolean().default(true),
  client_reference_id: ClientReferenceIdPosture.default({}),
});
export type LineagePosture = z.infer<typeof LineagePosture>;

export const MetadataPolicy = z.object({
  bounded_lineage: z.boolean().default(true),
  freeform_context: z.boolean().default(false),
  downstream_propagation: z.enum(["minimal", "policy", "service_defined"]).default("minimal"),
});
export type MetadataPolicy = z.infer<typeof MetadataPolicy>;

export const FailureDisclosure = z.object({
  detail_level: z.enum(["full", "reduced", "redacted", "policy"]).default("redacted"),
  caller_classes: z.array(z.string()).nullable().default(null),
});
export type FailureDisclosure = z.infer<typeof FailureDisclosure>;

export const AnchoringPosture = z.object({
  enabled: z.boolean().default(false),
  cadence: z.string().nullable().default(null),
  max_lag: z.number().nullable().default(null),
  proofs_available: z.boolean().default(false),
});
export type AnchoringPosture = z.infer<typeof AnchoringPosture>;

export const DiscoveryPosture = z.object({
  audit: AuditPosture.default({}),
  lineage: LineagePosture.default({}),
  metadata_policy: MetadataPolicy.default({}),
  failure_disclosure: FailureDisclosure.default({}),
  anchoring: AnchoringPosture.default({}),
});
export type DiscoveryPosture = z.infer<typeof DiscoveryPosture>;

// ---------------------------------------------------------------------------
// Manifest
// ---------------------------------------------------------------------------

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
  version: z.string().default("0.10.0"),
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
  protocol: z.string().default("anip/0.17"),
  profile: ProfileVersions,
  capabilities: z.record(CapabilityDeclaration),
  manifest_metadata: ManifestMetadata.nullable().default(null),
  service_identity: ServiceIdentity.nullable().default(null),
  trust: TrustPosture.nullable().default(null),
});
export type ANIPManifest = z.infer<typeof ANIPManifest>;

// ---------------------------------------------------------------------------
// Invocation
// ---------------------------------------------------------------------------

export const InvokeRequest = z.object({
  token: z.string(),
  parameters: z.record(z.any()).default({}),
  budget: z.record(z.any()).nullable().default(null),
  client_reference_id: z.string().max(256).nullable().default(null),
  stream: z.boolean().default(false),
});
export type InvokeRequest = z.infer<typeof InvokeRequest>;

export const StreamSummary = z.object({
  response_mode: z.literal("streaming"),
  events_emitted: z.number().int(),
  events_delivered: z.number().int(),
  duration_ms: z.number().int(),
  client_disconnected: z.boolean(),
});
export type StreamSummary = z.infer<typeof StreamSummary>;

export const InvokeResponse = z.object({
  success: z.boolean(),
  invocation_id: z.string().regex(/^inv-[0-9a-f]{12}$/),
  client_reference_id: z.string().max(256).nullable().default(null),
  result: z.record(z.any()).nullable().default(null),
  cost_actual: CostActual.nullable().default(null),
  failure: ANIPFailure.nullable().default(null),
  session: z.record(z.any()).nullable().default(null),
  stream_summary: StreamSummary.nullable().default(null),
  budget_context: BudgetContext.nullable().default(null),
});
export type InvokeResponse = z.infer<typeof InvokeResponse>;

// ---------------------------------------------------------------------------
// Token Request (v0.2 server-side issuance)
// ---------------------------------------------------------------------------

export const TokenRequest = z.object({
  subject: z.string(),
  scope: z.array(z.string()),
  capability: z.string(),
  parent_token: z.string().nullable().optional(),
  purpose_parameters: z.record(z.any()).default({}),
  ttl_hours: z.number().default(2),
  caller_class: z.string().nullable().optional(),
});
export type TokenRequest = z.infer<typeof TokenRequest>;

// ---------------------------------------------------------------------------
// Checkpoint Body
// ---------------------------------------------------------------------------

export const CheckpointBody = z.object({
  version: z.string().default("1.0"),
  service_id: z.string(),
  checkpoint_id: z.string(),
  range: z.object({
    first_sequence: z.number(),
    last_sequence: z.number(),
  }),
  merkle_root: z.string(),
  previous_checkpoint: z.string().nullable().default(null),
  timestamp: z.string(),
  entry_count: z.number(),
});
export type CheckpointBody = z.infer<typeof CheckpointBody>;

// ---------------------------------------------------------------------------
// Checkpoint Detail Response (response wrapper, NOT the signed body)
// ---------------------------------------------------------------------------

export const CheckpointDetailResponse = z.object({
  checkpoint: z.record(z.unknown()),
  inclusion_proof: z.record(z.unknown()).nullable().default(null),
  consistency_proof: z.record(z.unknown()).nullable().default(null),
  proof_unavailable: z.string().nullable().default(null),
  expires_hint: z.string().nullable().default(null),
});
export type CheckpointDetailResponse = z.infer<typeof CheckpointDetailResponse>;
