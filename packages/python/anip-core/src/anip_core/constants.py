"""ANIP protocol constants."""

PROTOCOL_VERSION = "anip/0.24"
MANIFEST_VERSION = "0.10.0"
DEFAULT_PROFILE = {
    "core": "1.0",
    "cost": "1.0",
    "capability_graph": "1.0",
    "state_session": "1.0",
    "observability": "1.0",
}
SUPPORTED_ALGORITHMS = ["ES256"]
LEAF_HASH_PREFIX = b"\x00"
NODE_HASH_PREFIX = b"\x01"

# --- Recovery Posture (v0.16) ---

RECOVERY_CLASS_MAP: dict[str, str] = {
    # --- Canonical actions (v0.16 spec) ---
    "retry_now": "retry_now",
    "wait_and_retry": "wait_then_retry",
    "obtain_binding": "refresh_then_retry",
    "refresh_binding": "refresh_then_retry",
    "obtain_quote_first": "refresh_then_retry",
    "revalidate_state": "revalidate_then_retry",
    "request_broader_scope": "redelegation_then_retry",
    "request_budget_increase": "redelegation_then_retry",
    "request_budget_bound_delegation": "redelegation_then_retry",
    "request_matching_currency_delegation": "redelegation_then_retry",
    "request_new_delegation": "redelegation_then_retry",
    "request_capability_binding": "redelegation_then_retry",
    "request_deeper_delegation": "redelegation_then_retry",
    "escalate_to_root_principal": "terminal",
    "provide_credentials": "retry_now",
    "request_approval": "wait_then_retry",
    "check_manifest": "revalidate_then_retry",
    "contact_service_owner": "terminal",
}


def recovery_class_for_action(action: str) -> str:
    """Return the recovery class for a canonical action.

    Raises KeyError for non-canonical (unmapped) actions.
    """
    return RECOVERY_CLASS_MAP[action]


# --- HTTP status per failure type (v0.24) ---

# SPEC.md §6.3 "HTTP Status Codes": every HTTP binding (the protocol endpoints
# and the REST adapter) answers a failure with the status of its type. A type
# that is not listed here, including one a capability handler defines, is 400.
FAILURE_STATUS_CODES: dict[str, int] = {
    # 400 — the caller has to change the request
    "invalid_parameters": 400,
    "streaming_not_supported": 400,
    "approval_required": 400,
    "grant_not_found": 400,
    "grant_capability_mismatch": 400,
    "grant_scope_mismatch": 400,
    "grant_param_drift": 400,
    "grant_session_invalid": 400,
    "grant_type_not_allowed_by_policy": 400,
    # 401 — no usable credential
    "authentication_required": 401,
    "invalid_token": 401,
    "token_expired": 401,
    "token_not_registered": 401,
    # 403 — the delegated authority does not cover the request
    "scope_insufficient": 403,
    "insufficient_authority": 403,
    "purpose_mismatch": 403,
    "scope_escalation": 403,
    "constraint_escalation": 403,
    "broken_delegation_chain": 403,
    "delegation_depth_exceeded": 403,
    "parent_token_expired": 403,
    "budget_exceeded": 403,
    "budget_currency_mismatch": 403,
    "budget_not_enforceable": 403,
    "binding_missing": 403,
    "binding_stale": 403,
    "control_requirement_unsatisfied": 403,
    "approver_not_authorized": 403,
    "grant_requester_mismatch": 403,
    # 404 — the capability, resource or approval request does not exist
    "unknown_capability": 404,
    "not_found": 404,
    "approval_request_not_found": 404,
    # 409 — conflict with the state of a grant, an approval request or a lock
    "grant_consumed": 409,
    "grant_expired": 409,
    "approval_request_already_decided": 409,
    "approval_request_expired": 409,
    "concurrent_lock": 409,
    "concurrent_request_rejected": 409,
    "unavailable": 409,
    # 500, 503 — the service failed
    "internal_error": 500,
    "service_unavailable": 503,
}

DEFAULT_FAILURE_STATUS_CODE = 400


def failure_status_code(failure_type: str | None) -> int:
    """Return the HTTP status for an ANIP failure type (SPEC.md §6.3)."""
    if not isinstance(failure_type, str):
        return DEFAULT_FAILURE_STATUS_CODE
    return FAILURE_STATUS_CODES.get(failure_type, DEFAULT_FAILURE_STATUS_CODE)
