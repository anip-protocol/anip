package dev.anip.core;

/**
 * Describes the side-effect characteristics of a capability.
 */
public class SideEffect {

    private final String type;
    private final String rollbackWindow;

    public SideEffect(String type, String rollbackWindow) {
        this.type = type;
        this.rollbackWindow = rollbackWindow;
    }

    /** Side-effect type: "read", "write", "irreversible", "transactional". */
    public String getType() {
        return type;
    }

    /** ISO 8601 duration, "none", or "not_applicable". */
    public String getRollbackWindow() {
        return rollbackWindow;
    }
}
