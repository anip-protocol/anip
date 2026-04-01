export const PROTOCOL_VERSION = "anip/0.16";
export const MANIFEST_VERSION = "0.10.0";
export const DEFAULT_PROFILE = {
  core: "1.0",
  cost: "1.0",
  capability_graph: "1.0",
  state_session: "1.0",
  observability: "1.0",
};
export const FAILURE_NON_DELEGABLE_ACTION = "non_delegable_action";
export const SUPPORTED_ALGORITHMS = ["ES256"] as const;
export const LEAF_HASH_PREFIX = 0x00;
export const NODE_HASH_PREFIX = 0x01;

// --- Recovery Posture (v0.16) ---

/** Canonical action → recovery class mapping. */
export const RECOVERY_CLASS_MAP: Record<string, string> = {
  // Canonical actions (v0.16 spec)
  retry_now: "retry_now",
  wait_and_retry: "wait_then_retry",
  obtain_binding: "refresh_then_retry",
  refresh_binding: "refresh_then_retry",
  obtain_quote_first: "refresh_then_retry",
  revalidate_state: "revalidate_then_retry",
  request_broader_scope: "redelegation_then_retry",
  request_budget_increase: "redelegation_then_retry",
  request_budget_bound_delegation: "redelegation_then_retry",
  request_matching_currency_delegation: "redelegation_then_retry",
  request_new_delegation: "redelegation_then_retry",
  request_capability_binding: "redelegation_then_retry",
  request_deeper_delegation: "redelegation_then_retry",
  escalate_to_root_principal: "terminal",
  provide_credentials: "retry_now",
  check_manifest: "revalidate_then_retry",
  contact_service_owner: "terminal",
  // Delegation-layer actions
  narrow_scope: "terminal",
  preserve_budget_constraint: "terminal",
  narrow_budget: "terminal",
  match_parent_currency: "terminal",
  register_missing_ancestor: "redelegation_then_retry",
  reduce_delegation_depth: "terminal",
  refresh_delegation_chain: "redelegation_then_retry",
  register_parent_token_first: "redelegation_then_retry",
  narrow_constraints: "terminal",
  preserve_constraint: "terminal",
  register_token: "redelegation_then_retry",
  // Service-layer actions
  use_token_task_id: "revalidate_then_retry",
  provide_priced_binding: "refresh_then_retry",
  list_checkpoints: "revalidate_then_retry",
};

/**
 * Return the recovery class for a canonical action.
 *
 * Throws an error for non-canonical (unmapped) actions — no silent fallback.
 */
export function recoveryClassForAction(action: string): string {
  const cls = RECOVERY_CLASS_MAP[action];
  if (cls === undefined) {
    throw new Error(`No recovery class mapped for action: "${action}"`);
  }
  return cls;
}
