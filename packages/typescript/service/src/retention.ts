/**
 * Retention policy for v0.8 security hardening.
 *
 * Two-layer policy model:
 *   1. EventClass -> RetentionTier
 *   2. RetentionTier -> Duration
 */

export const DEFAULT_CLASS_TO_TIER: Record<string, string> = {
  high_risk_success: "long",
  high_risk_denial: "medium",
  low_risk_success: "short",
  repeated_low_value_denial: "short",
  malformed_or_spam: "short",
};

export const DEFAULT_TIER_TO_DURATION: Record<string, string | null> = {
  long: "P365D",
  medium: "P90D",
  short: "P7D",
  aggregate_only: "P7D", // v0.8 placeholder
};

const DURATION_RE = /^P(\d+)D$/;

function parseIsoDurationDays(duration: string): number {
  const m = DURATION_RE.exec(duration);
  if (!m) {
    throw new Error(`Unsupported ISO 8601 duration: ${JSON.stringify(duration)}`);
  }
  return parseInt(m[1], 10);
}

export interface RetentionPolicyOpts {
  classToTier?: Record<string, string>;
  tierToDuration?: Record<string, string | null>;
}

export class RetentionPolicy {
  private readonly classToTier: Record<string, string>;
  private readonly tierToDuration: Record<string, string | null>;

  constructor(opts?: RetentionPolicyOpts) {
    this.classToTier = { ...DEFAULT_CLASS_TO_TIER, ...(opts?.classToTier ?? {}) };
    this.tierToDuration = { ...DEFAULT_TIER_TO_DURATION, ...(opts?.tierToDuration ?? {}) };
  }

  resolveTier(eventClass: string): string {
    return this.classToTier[eventClass] ?? "short";
  }

  computeExpiresAt(tier: string, now?: Date): string | null {
    const ts = now ?? new Date();
    const duration = this.tierToDuration[tier];
    if (duration == null) {
      return null;
    }
    const days = parseIsoDurationDays(duration);
    const expires = new Date(ts.getTime() + days * 86_400_000);
    return expires.toISOString();
  }
}
