package dev.anip.core;

public record InputResolution(
        ResolutionMode mode,
        String resolverRef,
        ResolutionBehavior onMissing,
        ResolutionBehavior onAmbiguous,
        ResolutionBehavior onUnresolved
) {
    public InputResolution {
        if (mode == null) {
            throw new IllegalArgumentException("resolution.mode is required");
        }
    }
}
