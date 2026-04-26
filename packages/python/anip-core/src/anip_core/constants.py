"""ANIP protocol constants."""

PROTOCOL_VERSION = "anip/0.23"
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
    "check_manifest": "revalidate_then_retry",
    "contact_service_owner": "terminal",
}


def recovery_class_for_action(action: str) -> str:
    """Return the recovery class for a canonical action.

    Raises KeyError for non-canonical (unmapped) actions.
    """
    return RECOVERY_CLASS_MAP[action]
