package dev.anip.servicetest;

import dev.anip.service.FailureRedaction;
import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class FailureRedactionTest {
    private Map<String, Object> sampleFailure() {
        var res = new HashMap<String, Object>();
        res.put("action", "request_scope");
        res.put("requires", List.of("travel.book"));
        res.put("grantable_by", "human:samir@example.com");
        var failure = new HashMap<String, Object>();
        failure.put("type", "scope_insufficient");
        failure.put("detail", "Need travel.book scope");
        failure.put("retry", false);
        failure.put("resolution", res);
        return failure;
    }

    @Test void fullPreservesEverything() {
        var result = FailureRedaction.redact(sampleFailure(), "full");
        assertEquals("Need travel.book scope", result.get("detail"));
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertEquals("human:samir@example.com", res.get("grantable_by"));
    }

    @Test void reducedNullsGrantableBy() {
        var result = FailureRedaction.redact(sampleFailure(), "reduced");
        assertEquals("Need travel.book scope", result.get("detail"));
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertNull(res.get("grantable_by"));
        assertEquals("request_scope", res.get("action"));
    }

    @Test void redactedUsesGenericMessage() {
        var result = FailureRedaction.redact(sampleFailure(), "redacted");
        assertEquals("Insufficient scope for this capability", result.get("detail"));
        assertEquals("scope_insufficient", result.get("type"));
        assertEquals(false, result.get("retry"));
        @SuppressWarnings("unchecked")
        var res = (Map<String, Object>) result.get("resolution");
        assertEquals("request_scope", res.get("action"));
        assertNull(res.get("requires"));
        assertNull(res.get("grantable_by"));
    }

    @Test void reducedTruncatesLongDetail() {
        var failure = new HashMap<String, Object>();
        failure.put("type", "internal_error");
        failure.put("detail", "x".repeat(300));
        failure.put("retry", false);
        var result = FailureRedaction.redact(failure, "reduced");
        assertTrue(((String) result.get("detail")).length() <= 200);
    }

    @Test void typeAndRetryNeverRedacted() {
        var failure = new HashMap<String, Object>();
        failure.put("type", "token_expired");
        failure.put("detail", "Token XYZ expired");
        failure.put("retry", true);
        for (String level : new String[]{"full", "reduced", "redacted"}) {
            var result = FailureRedaction.redact(failure, level);
            assertEquals("token_expired", result.get("type"), level);
            assertEquals(true, result.get("retry"), level);
        }
    }
}
