package dev.anip.core;

import java.util.List;

/** Constrains what an approver MAY issue for a given approval request. v0.23. See SPEC.md §4.7. */
public class GrantPolicy {
    private final List<String> allowedGrantTypes;
    private final String defaultGrantType;
    private final int expiresInSeconds;
    private final int maxUses;

    public GrantPolicy(List<String> allowedGrantTypes, String defaultGrantType,
                       int expiresInSeconds, int maxUses) {
        if (allowedGrantTypes == null || allowedGrantTypes.isEmpty()) {
            throw new IllegalArgumentException("GrantPolicy.allowedGrantTypes must be non-empty");
        }
        if (defaultGrantType == null || defaultGrantType.isEmpty()) {
            throw new IllegalArgumentException("GrantPolicy.defaultGrantType must be set");
        }
        // SPEC.md §4.7: default_grant_type MUST appear in allowed_grant_types.
        if (!allowedGrantTypes.contains(defaultGrantType)) {
            throw new IllegalArgumentException(
                "GrantPolicy.defaultGrantType='" + defaultGrantType +
                "' must appear in allowedGrantTypes=" + allowedGrantTypes);
        }
        this.allowedGrantTypes = allowedGrantTypes;
        this.defaultGrantType = defaultGrantType;
        this.expiresInSeconds = expiresInSeconds;
        this.maxUses = maxUses;
    }

    public List<String> getAllowedGrantTypes() {
        return allowedGrantTypes;
    }

    public String getDefaultGrantType() {
        return defaultGrantType;
    }

    public int getExpiresInSeconds() {
        return expiresInSeconds;
    }

    public int getMaxUses() {
        return maxUses;
    }
}
