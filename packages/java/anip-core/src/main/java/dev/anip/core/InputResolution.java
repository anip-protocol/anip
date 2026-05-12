package dev.anip.core;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;

public record InputResolution(
        @JsonProperty("mode") ResolutionMode mode,
        @JsonProperty("resolver_ref") String resolverRef,
        @JsonProperty("on_missing") ResolutionBehavior onMissing,
        @JsonProperty("on_ambiguous") ResolutionBehavior onAmbiguous,
        @JsonProperty("on_unresolved") ResolutionBehavior onUnresolved
) {
    @JsonCreator
    public InputResolution {
        if (mode == null) {
            throw new IllegalArgumentException("resolution.mode is required");
        }
    }
}
