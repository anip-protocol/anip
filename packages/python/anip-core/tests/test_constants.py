from anip_core import RECOVERY_CLASS_MAP, recovery_class_for_action


def test_request_approval_recovery_class():
    assert RECOVERY_CLASS_MAP["request_approval"] == "wait_then_retry"
    assert recovery_class_for_action("request_approval") == "wait_then_retry"


# SPEC.md §6.3 "HTTP Status Codes": one status per failure type.
HTTP_STATUS_TABLE = {
    400: [
        "invalid_parameters", "streaming_not_supported", "approval_required",
        "grant_not_found", "grant_capability_mismatch", "grant_scope_mismatch",
        "grant_param_drift", "grant_session_invalid", "grant_type_not_allowed_by_policy",
    ],
    401: ["authentication_required", "invalid_token", "token_expired", "token_not_registered"],
    403: [
        "scope_insufficient", "insufficient_authority", "purpose_mismatch", "scope_escalation",
        "constraint_escalation", "broken_delegation_chain", "delegation_depth_exceeded",
        "parent_token_expired", "budget_exceeded", "budget_currency_mismatch",
        "budget_not_enforceable", "binding_missing", "binding_stale",
        "control_requirement_unsatisfied", "approver_not_authorized",
        "grant_requester_mismatch",
    ],
    404: ["unknown_capability", "not_found", "approval_request_not_found"],
    409: [
        "grant_consumed", "grant_expired", "approval_request_already_decided",
        "approval_request_expired", "concurrent_lock", "concurrent_request_rejected",
        "unavailable",
    ],
    500: ["internal_error"],
    503: ["service_unavailable"],
}


def test_failure_status_code_matches_every_row_of_the_table():
    from anip_core import failure_status_code

    rows = [(t, status) for status, types in HTTP_STATUS_TABLE.items() for t in types]
    assert len(rows) == len({t for t, _ in rows}) == 41
    for failure_type, status in rows:
        assert failure_status_code(failure_type) == status, failure_type


def test_failure_status_codes_is_exactly_the_table():
    from anip_core import FAILURE_STATUS_CODES

    assert FAILURE_STATUS_CODES == {
        failure_type: status
        for status, types in HTTP_STATUS_TABLE.items() for failure_type in types
    }


def test_failure_status_code_defaults_to_400():
    from anip_core import failure_status_code

    for failure_type in (
        "capability_unavailable", "clarification_required", "denied", "restricted",
        "composition_empty_result_denied", "something_a_handler_made_up", "", None,
        "Internal_Error", "INTERNAL_ERROR",
    ):
        assert failure_status_code(failure_type) == 400, failure_type
