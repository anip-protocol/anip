import { createHash, randomBytes } from "node:crypto";
import type { ActorPolicy } from "./actor.js";

export type ApprovalRecord = {
  approval_request_id: string;
  capability: string;
  required_role: string;
  status: "pending" | "approved";
  requested_by: Record<string, unknown>;
  approved_by?: Record<string, unknown>;
  preview: Record<string, unknown>;
  created_at: string;
  approved_at?: string;
};

const records = new Map<string, ApprovalRecord>();

function actorSummary(actor: ActorPolicy): Record<string, unknown> {
  return {
    actor_id: actor.actor_id,
    role: actor.role,
  };
}

export function createApprovalRequest(params: {
  capability: string;
  requester: ActorPolicy;
  required_role?: string;
  preview: Record<string, unknown>;
}): ApprovalRecord {
  const approval_request_id = `apr_${randomBytes(6).toString("hex")}`;
  const record: ApprovalRecord = {
    approval_request_id,
    capability: params.capability,
    required_role: params.required_role || "sales_leader",
    status: "pending",
    requested_by: actorSummary(params.requester),
    preview: params.preview,
    created_at: new Date().toISOString(),
  };
  records.set(approval_request_id, record);
  return record;
}

export function listApprovals(status?: string): ApprovalRecord[] {
  return [...records.values()].filter((record) => !status || record.status === status);
}

export function approveRequest(approvalRequestId: string, approver: ActorPolicy): ApprovalRecord | null {
  const record = records.get(approvalRequestId);
  if (!record) return null;
  record.status = "approved";
  record.approved_by = actorSummary(approver);
  record.approved_at = new Date().toISOString();
  return record;
}

export function approvalFailure(record: ApprovalRecord, detail: string): Record<string, unknown> {
  const digest = createHash("sha256").update(JSON.stringify(record.preview)).digest("hex");
  return {
    type: "approval_required",
    detail,
    resolution: {
      action: "request_approval",
      requires: "approval before downstream mutation",
      preview: record.preview,
      approval_request_id: record.approval_request_id,
      approval_role_required: record.required_role,
    },
    approval_required: {
      approval_request_id: record.approval_request_id,
      preview_digest: `sha256:${digest}`,
      requested_parameters_digest: `sha256:${digest}`,
      grant_policy: {
        allowed_grant_types: ["one_time", "session_bound"],
        default_grant_type: "one_time",
        expires_in_seconds: 900,
        max_uses: 1,
      },
    },
  };
}

