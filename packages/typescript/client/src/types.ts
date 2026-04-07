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
  endpoints: Record<string, string>;
  profiles: Record<string, string>;
  capabilities: string[];
}

// ---------------------------------------------------------------------------
// Manifest / Capability
// ---------------------------------------------------------------------------

export interface NormalizedManifest {
  protocol: string;
  capabilities: Record<string, NormalizedCapability>;
}

export interface NormalizedCapability {
  name: string;
  description: string;
  minimumScope: string[];
  sideEffect: { type: string; rollbackWindow?: string };
  responseModes: string[];
  cost?: { financial?: { currency: string; estimatedAmount: number } };
  controlRequirements?: Array<{ type: string; enforcement: string }>;
  crossServiceContract?: {
    handoff?: Array<{ service: string; capability: string; requiredForTaskCompletion: boolean }>;
    followup?: Array<{ service: string; capability: string }>;
    verification?: Array<{ service: string; capability: string }>;
  };
  graph?: { requires?: Array<{ capability: string; reason: string }>; composesWith?: Array<{ capability: string; optional: boolean }> };
}

// ---------------------------------------------------------------------------
// Permissions
// ---------------------------------------------------------------------------

export interface NormalizedPermissions {
  available: string[];
  restricted: Array<{ capability: string; reasonType: string; resolutionHint?: string }>;
  denied: Array<{ capability: string; reasonType: string }>;
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
