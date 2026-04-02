package dev.anip.core;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ConstantsTest {

    @Test
    void protocolVersion() {
        // Intentionally hardcoded — this is the one place that verifies the constant value.
        // Update this when bumping the protocol version.
        assertEquals("anip/0.19", Constants.PROTOCOL_VERSION);
    }

    @Test
    void failureStatusCodeMapping() {
        // 401 - authentication failures
        assertEquals(401, Constants.failureStatusCode(Constants.FAILURE_AUTH_REQUIRED));
        assertEquals(401, Constants.failureStatusCode(Constants.FAILURE_INVALID_TOKEN));
        assertEquals(401, Constants.failureStatusCode(Constants.FAILURE_TOKEN_EXPIRED));

        // 403 - authorization failures
        assertEquals(403, Constants.failureStatusCode(Constants.FAILURE_SCOPE_INSUFFICIENT));
        assertEquals(403, Constants.failureStatusCode(Constants.FAILURE_BUDGET_EXCEEDED));
        assertEquals(403, Constants.failureStatusCode(Constants.FAILURE_PURPOSE_MISMATCH));

        // 404 - not found
        assertEquals(404, Constants.failureStatusCode(Constants.FAILURE_UNKNOWN_CAPABILITY));
        assertEquals(404, Constants.failureStatusCode(Constants.FAILURE_NOT_FOUND));

        // 409 - conflict
        assertEquals(409, Constants.failureStatusCode(Constants.FAILURE_UNAVAILABLE));
        assertEquals(409, Constants.failureStatusCode(Constants.FAILURE_CONCURRENT_LOCK));

        // 500 - internal error
        assertEquals(500, Constants.failureStatusCode(Constants.FAILURE_INTERNAL_ERROR));

        // 400 - invalid parameters
        assertEquals(400, Constants.failureStatusCode(Constants.FAILURE_INVALID_PARAMETERS));

        // 400 - unknown type defaults to 400
        assertEquals(400, Constants.failureStatusCode("some_unknown_type"));
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
