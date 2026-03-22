package dev.anip.service;

import java.util.Set;

public final class EventClassification {
    private static final Set<String> HIGH_RISK_SIDE_EFFECTS = Set.of("write", "irreversible", "transactional");
    private static final Set<String> MALFORMED_FAILURE_TYPES = Set.of("unknown_capability", "streaming_not_supported", "internal_error");

    private EventClassification() {}

    public static String classify(String sideEffectType, boolean success, String failureType) {
        if (sideEffectType == null || sideEffectType.isEmpty()) {
            return "malformed_or_spam";
        }
        if (success) {
            return HIGH_RISK_SIDE_EFFECTS.contains(sideEffectType) ? "high_risk_success" : "low_risk_success";
        }
        if (failureType != null && MALFORMED_FAILURE_TYPES.contains(failureType)) {
            return "malformed_or_spam";
        }
        return "high_risk_denial";
    }
}
