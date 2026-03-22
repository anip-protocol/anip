package dev.anip.servicetest;

import dev.anip.service.EventClassification;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class EventClassificationTest {
    @Test void highRiskSuccess() {
        for (String se : new String[]{"write", "irreversible", "transactional"}) {
            assertEquals("high_risk_success", EventClassification.classify(se, true, ""));
        }
    }
    @Test void lowRiskSuccess() {
        assertEquals("low_risk_success", EventClassification.classify("read", true, ""));
    }
    @Test void malformedNoSideEffect() {
        assertEquals("malformed_or_spam", EventClassification.classify("", false, "unknown_capability"));
        assertEquals("malformed_or_spam", EventClassification.classify(null, false, "unknown_capability"));
    }
    @Test void malformedFailureTypes() {
        for (String ft : new String[]{"unknown_capability", "streaming_not_supported", "internal_error"}) {
            assertEquals("malformed_or_spam", EventClassification.classify("read", false, ft));
        }
    }
    @Test void highRiskDenial() {
        for (String ft : new String[]{"scope_insufficient", "invalid_token", "token_expired", "purpose_mismatch"}) {
            assertEquals("high_risk_denial", EventClassification.classify("write", false, ft));
        }
    }
}
