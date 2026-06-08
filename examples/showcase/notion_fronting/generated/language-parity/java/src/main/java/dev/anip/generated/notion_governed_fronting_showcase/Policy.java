package dev.anip.generated.notion_governed_fronting_showcase;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Policy {

    private Policy() {}

    public static PolicyDecision evaluate(Map<String, Object> capability, Map<String, Object> params, String rootPrincipal) {
        String capabilityId = stringValue(capability, "capability_id");
        List<Map<String, Object>> bindings = bindingsFor(capabilityId);
        if (bindings.isEmpty()) return new PolicyDecision("allow", null);
        Map<String, String> claims = principalClaims(rootPrincipal);
        if (claims.isEmpty()) return new PolicyDecision("allow", null);
        List<Map<String, Object>> matching = new ArrayList<>();
        for (Map<String, Object> binding : bindings) {
            if (!matchesPrincipal(binding, claims)) continue;
            matching.add(binding);
        }
        if (requiresGovernedStop(capability)) {
            for (Map<String, Object> binding : matching) {
                if ("deny".equals(stringValue(binding, "decision"))) return decisionFor(binding);
            }
            for (Map<String, Object> binding : matching) {
                if ("approval_required".equals(stringValue(binding, "decision"))) return decisionFor(binding);
            }
            for (Map<String, Object> binding : matching) {
                if ("clarify".equals(stringValue(binding, "decision"))) return decisionFor(binding);
            }
        }
        for (Map<String, Object> binding : matching) {
            String decision = stringValue(binding, "decision");
            if (!"deny".equals(decision) && !"clarify".equals(decision) && !"approval_required".equals(decision)) return decisionFor(binding);
        }
        return new PolicyDecision("allow", "No matching runtime policy binding; continuing.");
    }

    private static boolean requiresGovernedStop(Map<String, Object> capability) {
        return !objectMap(capability.get("grant_policy")).isEmpty()
            || "approval_required".equals(stringValue(capability, "side_effect_level"))
            || "approval_required".equals(stringValue(capability, "execution_posture"))
            || "approval_gated".equals(stringValue(capability, "operation_type"));
    }

    private static PolicyDecision decisionFor(Map<String, Object> binding) {
        String decision = firstNonEmpty(stringValue(binding, "decision"), "allow");
        String detail = firstNonEmpty(stringValue(binding, "business_rule"), stringValue(binding, "enforcement_notes"));
        if ("deny".equals(decision) || "clarify".equals(decision) || "approval_required".equals(decision)) {
            return new PolicyDecision(decision, detail);
        }
        return new PolicyDecision("allow", detail);
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> bindingsFor(String capabilityId) {
        Object raw = GeneratedRuntimeTarget.runtimeTarget().get("policy_bindings");
        if (!(raw instanceof List<?> list)) return List.of();
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> map)) continue;
            Map<String, Object> binding = (Map<String, Object>) map;
            if (stringList(binding.get("capability_ids")).contains(capabilityId)) result.add(binding);
        }
        return result;
    }

    private static Map<String, String> principalClaims(String rootPrincipal) {
        String raw = rootPrincipal == null ? "" : rootPrincipal.trim();
        if (raw.isEmpty()) return Map.of();
        String[] pieces = raw.split("\\|");
        Map<String, String> claims = new LinkedHashMap<>();
        claims.put("principal", pieces.length > 0 ? pieces[0] : "");
        for (int index = 1; index < pieces.length; index++) {
            String piece = pieces[index];
            int separator = piece.indexOf('=');
            if (separator < 0) continue;
            claims.put(piece.substring(0, separator).trim(), piece.substring(separator + 1).trim());
        }
        return claims;
    }

    private static boolean matchesPrincipal(Map<String, Object> binding, Map<String, String> claims) {
        Map<String, Object> selector = objectMap(binding.get("principal_selector"));
        String claim = firstNonEmpty(stringValue(selector, "claim"), "actor_id");
        String expected = firstNonEmpty(stringValue(selector, "equals"), stringValue(binding, "actor_id"));
        if (expected.isBlank()) return true;
        if (!claims.containsKey(claim)) return false;
        return expected.equals(claims.get(claim));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> objectMap(Object value) {
        if (value instanceof Map<?, ?> map) return (Map<String, Object>) map;
        return Map.of();
    }

    private static List<String> stringList(Object value) {
        if (!(value instanceof List<?> list)) return List.of();
        return list.stream().filter(item -> item != null).map(String::valueOf).toList();
    }

    private static String stringValue(Map<String, Object> object, String key) {
        Object value = object == null ? null : object.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private static String firstNonEmpty(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value;
        }
        return "";
    }

    public record PolicyDecision(String decision, String detail) {}
}
