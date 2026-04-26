/**
 * Audit log manager for ANIP services.
 *
 * Sequence numbers, hash chaining, and Merkle accumulation are now
 * handled by the storage layer ({@link StorageBackend.appendAuditEntry}).
 */

import type { StorageBackend } from "./storage.js";

export class AuditLog {
  private _storage: StorageBackend;
  private _signer: ((entry: Record<string, unknown>) => string | Promise<string>) | null;

  constructor(
    storage: StorageBackend,
    signer?: (entry: Record<string, unknown>) => string | Promise<string>,
  ) {
    this._storage = storage;
    this._signer = signer ?? null;
  }

  /**
   * Log an audit entry via the storage backend.
   *
   * `entryData` should contain: `capability`, `token_id`, `root_principal`,
   * `success`, and optionally: `issuer`, `subject`, `parameters`,
   * `result_summary`, `failure_type`, `cost_actual`, `delegation_chain`.
   *
   * Returns the complete entry dict (with `sequence_number`, `timestamp`,
   * `previous_hash`, `signature`).
   */
  async logEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
    const now = new Date().toISOString();

    const entryForStorage: Record<string, unknown> = {
      timestamp: now,
      capability: entryData.capability,
      token_id: entryData.token_id ?? null,
      issuer: entryData.issuer ?? null,
      subject: entryData.subject ?? null,
      root_principal: entryData.root_principal ?? null,
      parameters: entryData.parameters ?? null,
      success: entryData.success,
      result_summary: entryData.result_summary ?? null,
      failure_type: entryData.failure_type ?? null,
      cost_actual: entryData.cost_actual ?? null,
      delegation_chain: entryData.delegation_chain ?? null,
      invocation_id: entryData.invocation_id ?? null,
      client_reference_id: entryData.client_reference_id ?? null,
      task_id: entryData.task_id ?? null,
      parent_invocation_id: entryData.parent_invocation_id ?? null,
      upstream_service: entryData.upstream_service ?? null,
      stream_summary: entryData.streamSummary ?? entryData.stream_summary ?? null,
      event_class: entryData.event_class ?? null,
      retention_tier: entryData.retention_tier ?? null,
      expires_at: entryData.expires_at ?? null,
      storage_redacted: entryData.storage_redacted ?? false,
      entry_type: entryData.entry_type ?? null,
      grouping_key: entryData.grouping_key ?? null,
      aggregation_window: entryData.aggregation_window ?? null,
      aggregation_count: entryData.aggregation_count ?? null,
      first_seen: entryData.first_seen ?? null,
      last_seen: entryData.last_seen ?? null,
      representative_detail: entryData.representative_detail ?? null,
      // v0.23 — approval flow linkage. See SPEC.md §4.7–§4.9.
      approval_request_id: entryData.approval_request_id ?? null,
      approval_grant_id: entryData.approval_grant_id ?? null,
    };

    const entry = await this._storage.appendAuditEntry(entryForStorage);

    entry.signature = this._signer ? await this._signer(entry) : null;
    if (entry.signature) {
      await this._storage.updateAuditSignature(entry.sequence_number as number, entry.signature as string);
    }

    return entry;
  }

  /** Query audit entries with optional filters. */
  async query(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    taskId?: string;
    parentInvocationId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    return await this._storage.queryAuditEntries(opts);
  }
}
