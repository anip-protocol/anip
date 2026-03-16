/**
 * Core types for the ANIP service runtime.
 */
import type { CapabilityDeclaration, DelegationToken } from "@anip/core";

export interface InvocationContext {
  token: DelegationToken;
  rootPrincipal: string;
  subject: string;
  scopes: string[];
  delegationChain: string[];
  invocationId: string;
  clientReferenceId: string | null;
  /** Set actual cost for variance tracking. */
  setCostActual(cost: Record<string, unknown>): void;
  /** Emit a progress event. No-op in unary mode. */
  emitProgress(payload: Record<string, unknown>): Promise<void>;
}

export type Handler = (
  ctx: InvocationContext,
  params: Record<string, unknown>,
) => Record<string, unknown> | Promise<Record<string, unknown>>;

export interface CapabilityDef {
  declaration: CapabilityDeclaration;
  handler: Handler;
  exclusiveLock?: boolean;
}

export class ANIPError extends Error {
  readonly errorType: string;
  readonly detail: string;

  constructor(errorType: string, detail: string) {
    super(`${errorType}: ${detail}`);
    this.errorType = errorType;
    this.detail = detail;
    this.name = "ANIPError";
  }
}
