package dev.anip.generated.gtm_pipeline_q2_review;

import java.util.Map;

public final class Policy {

    private Policy() {}

    public static PolicyDecision evaluate(Map<String, Object> capability, Map<String, Object> params, String rootPrincipal) {
        return new PolicyDecision("allow", "GTM native bundle evaluates actor policy inside the backend adapter.");
    }

    public record PolicyDecision(String decision, String detail) {}
}
