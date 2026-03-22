package dev.anip.service;

import java.util.List;
import java.util.Map;

public final class DisclosureControl {
    private DisclosureControl() {}

    public static String resolve(String level, Map<String, Object> tokenClaims, Map<String, String> policy) {
        if (!"policy".equals(level)) return level;
        String callerClass = resolveCallerClass(tokenClaims);
        if (policy == null) return "redacted";
        String mapped = policy.get(callerClass);
        if (mapped != null) return mapped;
        String def = policy.get("default");
        if (def != null) return def;
        return "redacted";
    }

    private static String resolveCallerClass(Map<String, Object> claims) {
        if (claims == null) return "default";
        Object cc = claims.get("anip:caller_class");
        if (cc instanceof String s && !s.isEmpty()) return s;
        Object scopeObj = claims.get("scope");
        if (scopeObj instanceof List<?> scopes) {
            for (Object s : scopes) {
                if ("audit:full".equals(s)) return "audit_full";
            }
        }
        return "default";
    }
}
