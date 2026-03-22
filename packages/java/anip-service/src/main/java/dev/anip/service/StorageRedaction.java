package dev.anip.service;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public final class StorageRedaction {
    private static final Set<String> LOW_VALUE_CLASSES = Set.of(
        "low_risk_success", "malformed_or_spam", "repeated_low_value_denial"
    );

    private StorageRedaction() {}

    public static Map<String, Object> redactEntry(Map<String, Object> entry) {
        var result = new HashMap<>(entry);
        String ec = (String) result.get("event_class");
        if (ec != null && LOW_VALUE_CLASSES.contains(ec)) {
            result.put("parameters", null);
            result.put("storage_redacted", true);
        } else {
            result.put("storage_redacted", false);
        }
        return result;
    }

    public static boolean isLowValue(String eventClass) {
        return eventClass != null && LOW_VALUE_CLASSES.contains(eventClass);
    }
}
