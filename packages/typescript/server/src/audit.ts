/**
 * Audit log manager for ANIP services.
 *
 * Wraps a {@link StorageBackend} with Merkle tree accumulation and
 * hash-chain linking between entries.
 */

import { createHash } from "crypto";
import type { StorageBackend } from "./storage.js";
import { MerkleTree, type Snapshot } from "./merkle.js";

export class AuditLog {
  private _storage: StorageBackend;
  private _signer: ((entry: Record<string, unknown>) => string | Promise<string>) | null;
  private _merkle: MerkleTree;

  constructor(
    storage: StorageBackend,
    signer?: (entry: Record<string, unknown>) => string | Promise<string>,
  ) {
    this._storage = storage;
    this._signer = signer ?? null;
    this._merkle = new MerkleTree();
  }

  /**
   * Log an audit entry: compute hash chain, sign, accumulate into Merkle
   * tree, store.
   *
   * `entryData` should contain: `capability`, `token_id`, `root_principal`,
   * `success`, and optionally: `issuer`, `subject`, `parameters`,
   * `result_summary`, `failure_type`, `cost_actual`, `delegation_chain`.
   *
   * Returns the complete entry dict (with `sequence_number`, `timestamp`,
   * `previous_hash`, `signature`).
   */
  async logEntry(entryData: Record<string, unknown>): Promise<Record<string, unknown>> {
    const last = await this._storage.getLastAuditEntry();
    let sequenceNumber: number;
    let previousHash: string;
    if (last === null) {
      sequenceNumber = 1;
      previousHash = "sha256:0";
    } else {
      sequenceNumber = (last.sequence_number as number) + 1;
      previousHash = AuditLog._computeEntryHash(last);
    }

    const now = new Date().toISOString();

    const entry: Record<string, unknown> = {
      sequence_number: sequenceNumber,
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
      previous_hash: previousHash,
    };

    // Accumulate into Merkle tree
    const canonicalBytes = AuditLog._canonicalBytes(entry);
    this._merkle.addLeaf(Buffer.from(canonicalBytes));

    // Sign if signer is provided
    entry.signature = this._signer ? await this._signer(entry) : null;

    await this._storage.storeAuditEntry(entry);
    return entry;
  }

  /** Query audit entries with optional filters. */
  async query(opts?: {
    capability?: string;
    rootPrincipal?: string;
    since?: string;
    invocationId?: string;
    clientReferenceId?: string;
    eventClass?: string;
    limit?: number;
  }): Promise<Record<string, unknown>[]> {
    return await this._storage.queryAuditEntries(opts);
  }

  /** Return the current Merkle tree snapshot. */
  getMerkleSnapshot(): Snapshot {
    return this._merkle.snapshot();
  }

  private static _computeEntryHash(entry: Record<string, unknown>): string {
    const canonical = AuditLog._canonicalBytes(entry);
    const hash = createHash("sha256").update(canonical).digest("hex");
    return `sha256:${hash}`;
  }

  private static _canonicalBytes(entry: Record<string, unknown>): string {
    const filtered: Record<string, unknown> = {};
    for (const key of Object.keys(entry).sort()) {
      if (key !== "signature" && key !== "id") {
        filtered[key] = entry[key];
      }
    }
    return JSON.stringify(filtered);
  }
}
