package dev.anip.service;

import java.util.HashMap;
import java.util.Map;

public final class FailureRedaction {
    private static final Map<String, String> GENERIC_MESSAGES = Map.ofEntries(
        Map.entry("scope_insufficient", "Insufficient scope for this capability"),
        Map.entry("invalid_token", "Authentication failed"),
        Map.entry("token_expired", "Token has expired"),
        Map.entry("purpose_mismatch", "Token purpose does not match this capability"),
        Map.entry("insufficient_authority", "Insufficient authority for this action"),
        Map.entry("unknown_capability", "Capability not found"),
        Map.entry("not_found", "Resource not found"),
        Map.entry("unavailable", "Service temporarily unavailable"),
        Map.entry("concurrent_lock", "Operation conflict"),
        Map.entry("internal_error", "Internal error"),
        Map.entry("streaming_not_supported", "Streaming not supported for this capability"),
        Map.entry("scope_escalation", "Scope escalation not permitted")
    );

    private FailureRedaction() {}

    @SuppressWarnings("unchecked")
    public static Map<String, Object> redact(Map<String, Object> failure, String level) {
        if ("full".equals(level)) {
            return new HashMap<>(failure);
        }
        var result = new HashMap<>(failure);
        if ("reduced".equals(level)) {
            String detail = (String) result.get("detail");
            if (detail != null && detail.length() > 200) {
                result.put("detail", detail.substring(0, 200));
            }
            if (result.get("resolution") instanceof Map) {
                var res = new HashMap<>((Map<String, Object>) result.get("resolution"));
                res.put("grantable_by", null);
                result.put("resolution", res);
            }
            return result;
        }
        // "redacted" mode
        String failType = (String) result.get("type");
        result.put("detail", GENERIC_MESSAGES.getOrDefault(failType, "Request failed"));
        if (result.get("resolution") instanceof Map) {
            var res = (Map<String, Object>) result.get("resolution");
            var redactedRes = new HashMap<String, Object>();
            redactedRes.put("action", res.get("action"));
            redactedRes.put("requires", null);
            redactedRes.put("grantable_by", null);
            redactedRes.put("estimated_availability", null);
            result.put("resolution", redactedRes);
        }
        return result;
    }
}
