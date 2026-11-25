package dev.anip.core;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConstantsTest {

    @Test
    void protocolVersion() {
        // Intentionally hardcoded — this is the one place that verifies the constant value.
        // Update this when bumping the protocol version.
        assertEquals("anip/0.24", Constants.PROTOCOL_VERSION);
    }

    /** SPEC.md §6.3 "HTTP Status Codes": every row of the table. */
    private static final java.util.Map<String, Integer> HTTP_STATUS = java.util.Map.ofEntries(
            java.util.Map.entry("authentication_required", 401),
            java.util.Map.entry("invalid_token", 401),
            java.util.Map.entry("token_expired", 401),
            java.util.Map.entry("token_not_registered", 401),
            java.util.Map.entry("scope_insufficient", 403),
            java.util.Map.entry("insufficient_authority", 403),
            java.util.Map.entry("purpose_mismatch", 403),
            java.util.Map.entry("scope_escalation", 403),
            java.util.Map.entry("constraint_escalation", 403),
            java.util.Map.entry("broken_delegation_chain", 403),
            java.util.Map.entry("delegation_depth_exceeded", 403),
            java.util.Map.entry("parent_token_expired", 403),
            java.util.Map.entry("budget_exceeded", 403),
            java.util.Map.entry("budget_currency_mismatch", 403),
            java.util.Map.entry("budget_not_enforceable", 403),
            java.util.Map.entry("binding_missing", 403),
            java.util.Map.entry("binding_stale", 403),
            java.util.Map.entry("control_requirement_unsatisfied", 403),
            java.util.Map.entry("approver_not_authorized", 403),
            java.util.Map.entry("grant_requester_mismatch", 403),
            java.util.Map.entry("unknown_capability", 404),
            java.util.Map.entry("not_found", 404),
            java.util.Map.entry("approval_request_not_found", 404),
            java.util.Map.entry("grant_consumed", 409),
            java.util.Map.entry("grant_expired", 409),
            java.util.Map.entry("approval_request_already_decided", 409),
            java.util.Map.entry("approval_request_expired", 409),
            java.util.Map.entry("concurrent_lock", 409),
            java.util.Map.entry("concurrent_request_rejected", 409),
            java.util.Map.entry("unavailable", 409),
            java.util.Map.entry("internal_error", 500),
            java.util.Map.entry("service_unavailable", 503),
            java.util.Map.entry("invalid_parameters", 400),
            java.util.Map.entry("streaming_not_supported", 400),
            java.util.Map.entry("approval_required", 400),
            java.util.Map.entry("grant_not_found", 400),
            java.util.Map.entry("grant_capability_mismatch", 400),
            java.util.Map.entry("grant_scope_mismatch", 400),
            java.util.Map.entry("grant_param_drift", 400),
            java.util.Map.entry("grant_session_invalid", 400),
            java.util.Map.entry("grant_type_not_allowed_by_policy", 400));

    @Test
    void failureStatusCodeIsTheSpecTable() {
        assertEquals(41, HTTP_STATUS.size());
        HTTP_STATUS.forEach((type, status) ->
                assertEquals(status, Constants.failureStatusCode(type), type));
    }

    @Test
    void failureStatusCodeDefaultsTo400() {
        // A type the table does not list, including one a handler defines.
        assertEquals(400, Constants.failureStatusCode("some_unknown_type"));
        assertEquals(400, Constants.failureStatusCode(Constants.FAILURE_NON_DELEGABLE_ACTION));
        assertEquals(400, Constants.failureStatusCode(Constants.FAILURE_COMPOSITION_CHILD_FAILED));
        assertEquals(400, Constants.failureStatusCode(""));
        assertEquals(400, Constants.failureStatusCode(null));
    }

    @Test
    void failureTypeConstantsNamedInTheTable() {
        assertEquals(401, Constants.failureStatusCode(Constants.FAILURE_TOKEN_NOT_REGISTERED));
        assertEquals(403, Constants.failureStatusCode(Constants.FAILURE_CONSTRAINT_ESCALATION));
        assertEquals(409, Constants.failureStatusCode(Constants.FAILURE_CONCURRENT_REQUEST_REJECTED));
        assertEquals(503, Constants.failureStatusCode(Constants.FAILURE_SERVICE_UNAVAILABLE));
        assertEquals("service_unavailable", Constants.FAILURE_SERVICE_UNAVAILABLE);
    }

    @Test
    void failureTypeConstants() {
        assertEquals("authentication_required", Constants.FAILURE_AUTH_REQUIRED);
        assertEquals("invalid_token", Constants.FAILURE_INVALID_TOKEN);
        assertEquals("token_expired", Constants.FAILURE_TOKEN_EXPIRED);
        assertEquals("scope_insufficient", Constants.FAILURE_SCOPE_INSUFFICIENT);
        assertEquals("unknown_capability", Constants.FAILURE_UNKNOWN_CAPABILITY);
        assertEquals("budget_exceeded", Constants.FAILURE_BUDGET_EXCEEDED);
        assertEquals("purpose_mismatch", Constants.FAILURE_PURPOSE_MISMATCH);
        assertEquals("not_found", Constants.FAILURE_NOT_FOUND);
        assertEquals("unavailable", Constants.FAILURE_UNAVAILABLE);
        assertEquals("concurrent_lock", Constants.FAILURE_CONCURRENT_LOCK);
        assertEquals("internal_error", Constants.FAILURE_INTERNAL_ERROR);
        assertEquals("streaming_not_supported", Constants.FAILURE_STREAMING_NOT_SUPPORTED);
        assertEquals("invalid_parameters", Constants.FAILURE_INVALID_PARAMETERS);
    }

    @Test
    void defaultProfile() {
        assertEquals("1.0", Constants.DEFAULT_PROFILE.get("core"));
        assertEquals("1.0", Constants.DEFAULT_PROFILE.get("cost"));
        assertEquals("1.0", Constants.DEFAULT_PROFILE.get("capability_graph"));
        assertEquals("1.0", Constants.DEFAULT_PROFILE.get("state_session"));
        assertEquals("1.0", Constants.DEFAULT_PROFILE.get("observability"));
    }
}
