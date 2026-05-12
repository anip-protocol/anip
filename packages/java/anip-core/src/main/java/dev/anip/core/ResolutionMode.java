package dev.anip.core;

public enum ResolutionMode {
    CLOSED_VALUES("closed_values"),
    BACKEND_RESOLVED("backend_resolved"),
    APP_SELECTED("app_selected"),
    ACTOR_POLICY("actor_policy"),
    ACTOR_POLICY_OR_EXPLICIT("actor_policy_or_explicit"),
    EXPLICIT_ONLY("explicit_only"),
    CLARIFY("clarify");

    private final String wire;

    ResolutionMode(String wire) {
        this.wire = wire;
    }

    public String wire() {
        return wire;
    }

    public static ResolutionMode fromWire(String wire) {
        for (ResolutionMode m : values()) {
            if (m.wire.equals(wire)) return m;
        }
        throw new IllegalArgumentException("invalid resolution.mode: " + wire);
    }
}
