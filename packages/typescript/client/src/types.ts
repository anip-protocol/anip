/**
 * Normalized consumer-facing types for ANIP client interactions.
 *
 * These types present a stable, consumer-friendly shape over the raw
 * ANIP protocol wire format. Framework adapters (React, Vue, Angular)
 * build on these types without duplicating protocol logic.
 */

// ---------------------------------------------------------------------------
// Discovery
// ---------------------------------------------------------------------------

export interface NormalizedDiscovery {
  protocol: string;
  compliance: string;
  trustLevel?: string;
  baseUrl?: string;
  endpoints: Record<string, string>;
  profiles: Record<string, string>;
  capabilityNames: string[];
  capabilities: Record<string, {
    name: string;
    sideEffect: string;
    minimumScope: string[];
    financial: boolean;
    contract?: string;
    raw: Record<string, unknown>;
  }>;
  posture?: Record<string, unknown>;
  raw: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Manifest / Capability
// ---------------------------------------------------------------------------

export interface NormalizedManifest {
  protocol: string;
  signature?: string;
  manifestMetadata?: Record<string, unknown>;
  serviceIdentity?: Record<string, unknown>;
  trust?: Record<string, unknown>;
  capabilities: Record<string, NormalizedCapability>;
  raw: Record<string, unknown>;
}

export interface NormalizedCapability {
  name: string;
  description: string;
  minimumScope: string[];
  sideEffect: { type: string; rollbackWindow?: string };
  responseModes: string[];
  cost?: {
    certainty?: string;
    financial?: {
      currency: string;
      estimatedAmount: number;
      rangeMin?: number;
      rangeMax?: number;
      typical?: number;
    };
    determinedBy?: string;
    compute?: Record<string, unknown>;
  };
  contractVersion?: string;
  inputs?: unknown[];
  output?: Record<string, unknown>;
  observability?: Record<string, unknown>;
  requiresBinding?: unknown[];
  refreshVia?: string[];
  verifyVia?: string[];
  crossService?: Record<string, unknown>;
  controlRequirements?: Array<{ type: string; enforcement: string }>;
  crossServiceContract?: {
    handoff?: Array<{ service: string; capability: string; requiredForTaskCompletion: boolean }>;
    followup?: Array<{ service: string; capability: string }>;
    verification?: Array<{ service: string; capability: string }>;
  };
  graph?: { requires?: Array<{ capability: string; reason: string }>; composesWith?: Array<{ capability: string; optional: boolean }> };
  raw: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

export interface NormalizedPermissions {
  available: Array<{ capability: string; scopeMatch?: string }>;
  restricted: Array<{ capability: string; reasonType: string; reason?: string; resolutionHint?: string; grantableBy?: string }>;
  denied: Array<{ capability: string; reasonType: string; reason?: string }>;
}

// ---------------------------------------------------------------------------
// Token Issuance
// ---------------------------------------------------------------------------

export interface NormalizedTokenResponse {
  issued: boolean;
  tokenId: string;
  token: string;
  expires: string;
  taskId?: string;
  budget?: { currency: string; maxAmount: number };
}

export interface TokenIssueRequest {
  scope: string[];
  subject?: string;
  capability?: string;
  parentToken?: string;
  purposeParameters?: Record<string, unknown>;
  ttlHours?: number;
  callerClass?: string;
  budget?: { currency: string; maxAmount: number };
  concurrentBranches?: string;
}

// ---------------------------------------------------------------------------
// Invocation
// ---------------------------------------------------------------------------

export interface NormalizedInvocationResult {
  success: boolean;
  invocationId: string;
  taskId?: string;
  result?: Record<string, unknown>;
  failure?: NormalizedFailure;
  budgetContext?: { budgetMax: number; budgetCurrency: string; costCheckAmount: number };
  streamSummary?: { responseMode: string; eventsEmitted: number; eventsDelivered: number; durationMs: number; clientDisconnected: boolean };
}

// ---------------------------------------------------------------------------
// Failure
// ---------------------------------------------------------------------------

export interface NormalizedFailure {
  type: string;
  detail: string;
  retryable: boolean;
  permissionRelated: boolean;
  recoveryClass?: string;
  recoveryTarget?: {
    kind: string;
    target?: { service: string; capability: string };
    continuity?: string;
    retryAfterTarget?: boolean;
  };
  resolution?: {
    action: string;
    requires?: string;
    grantableBy?: string;
  };
  displaySummary: string;
}

// ---------------------------------------------------------------------------
// Audit
// ---------------------------------------------------------------------------

export interface NormalizedAuditResult {
  entries: Array<Record<string, unknown>>;
  count: number;
}
