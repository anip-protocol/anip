package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum ResolutionBehavior {
    CLARIFY("clarify"),
    USE_DEFAULT("use_default"),
    USE_ACTOR_SCOPE("use_actor_scope"),
    APP_SELECT_OR_CLARIFY("app_select_or_clarify"),
    DENY("deny"),
    DENY_OR_CLARIFY("deny_or_clarify"),
    OMIT("omit");

    private final String wire;
    ResolutionBehavior(String wire) { this.wire = wire; }

    @JsonValue
    public String wire() { return wire; }

    @JsonCreator
    public static ResolutionBehavior fromWire(String wire) {
        for (ResolutionBehavior b : values()) if (b.wire.equals(wire)) return b;
        throw new IllegalArgumentException("invalid resolution.behavior: " + wire);
    }
}
