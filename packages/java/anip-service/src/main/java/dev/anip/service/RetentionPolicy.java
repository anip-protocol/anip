package dev.anip.service;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class RetentionPolicy {
    private static final Map<String, String> DEFAULT_CLASS_TO_TIER = Map.of(
        "high_risk_success", "long",
        "high_risk_denial", "medium",
        "low_risk_success", "short",
        "repeated_low_value_denial", "aggregate_only",
        "malformed_or_spam", "short"
    );
    private static final Map<String, String> DEFAULT_TIER_TO_DURATION = Map.of(
        "long", "P365D", "medium", "P90D", "short", "P7D", "aggregate_only", "P1D"
    );
    private static final Pattern DURATION_RE = Pattern.compile("^P(\\d+)D$");

    private final Map<String, String> classToTier;
    private final Map<String, String> tierToDuration;

    public RetentionPolicy(Map<String, String> classOverrides, Map<String, String> tierOverrides) {
        this.classToTier = new HashMap<>(DEFAULT_CLASS_TO_TIER);
        if (classOverrides != null) this.classToTier.putAll(classOverrides);
        this.tierToDuration = new HashMap<>(DEFAULT_TIER_TO_DURATION);
        if (tierOverrides != null) this.tierToDuration.putAll(tierOverrides);
    }

    public String resolveTier(String eventClass) {
        return classToTier.getOrDefault(eventClass, "short");
    }

    public String computeExpiresAt(String tier, Instant now) {
        String duration = tierToDuration.get(tier);
        if (duration == null) return null;
        Matcher m = DURATION_RE.matcher(duration);
        if (!m.matches()) return null;
        int days = Integer.parseInt(m.group(1));
        return now.plus(days, ChronoUnit.DAYS).toString();
    }

    public String getDefaultRetention() {
        return tierToDuration.get("medium");
    }
}
