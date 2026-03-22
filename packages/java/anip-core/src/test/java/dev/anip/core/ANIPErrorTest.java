package dev.anip.core;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class ANIPErrorTest {

    @Test
    void implementsRuntimeException() {
        ANIPError error = new ANIPError(Constants.FAILURE_INVALID_TOKEN, "token is invalid");
        assertInstanceOf(RuntimeException.class, error);
    }

    @Test
    void errorMessageFormat() {
        ANIPError error = new ANIPError(Constants.FAILURE_INVALID_TOKEN, "token is invalid");
        assertEquals("invalid_token: token is invalid", error.getMessage());
    }

    @Test
    void errorTypeAndDetail() {
        ANIPError error = new ANIPError(Constants.FAILURE_SCOPE_INSUFFICIENT, "missing scope");
        assertEquals(Constants.FAILURE_SCOPE_INSUFFICIENT, error.getErrorType());
        assertEquals("missing scope", error.getDetail());
    }

    @Test
    void builderWithResolution() {
        ANIPError error = new ANIPError(Constants.FAILURE_SCOPE_INSUFFICIENT, "missing scope")
                .withResolution("request_scope_grant")
                .withRetry();

        assertEquals(Constants.FAILURE_SCOPE_INSUFFICIENT, error.getErrorType());
        assertNotNull(error.getResolution());
        assertEquals("request_scope_grant", error.getResolution().getAction());
        assertTrue(error.isRetry());
    }

    @Test
    void builderWithFullResolution() {
        Resolution resolution = new Resolution(
                "request_scope_grant",
                "delegation.scope += travel.book",
                "human:samir@example.com",
                null
        );

        ANIPError error = new ANIPError(Constants.FAILURE_SCOPE_INSUFFICIENT, "missing travel.book")
                .withResolution(resolution)
                .withRetry();

        assertNotNull(error.getResolution());
        assertEquals("request_scope_grant", error.getResolution().getAction());
        assertEquals("delegation.scope += travel.book", error.getResolution().getRequires());
        assertEquals("human:samir@example.com", error.getResolution().getGrantableBy());
        assertTrue(error.isRetry());
    }

    @Test
    void canBeCaughtAsException() {
        try {
            throw new ANIPError(Constants.FAILURE_AUTH_REQUIRED, "not authenticated");
        } catch (Exception e) {
            assertInstanceOf(ANIPError.class, e);
            assertEquals("authentication_required: not authenticated", e.getMessage());
        }
    }

    @Test
    void defaultRetryIsFalse() {
        ANIPError error = new ANIPError(Constants.FAILURE_INTERNAL_ERROR, "something failed");
        assertFalse(error.isRetry());
    }

    @Test
    void defaultResolutionIsNull() {
        ANIPError error = new ANIPError(Constants.FAILURE_NOT_FOUND, "not found");
        assertNull(error.getResolution());
    }
}
