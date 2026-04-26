package dev.anip.core;

/** Audit behavior for composed capabilities. v0.23. See SPEC.md §4.6. */
public class AuditPolicy {
    private final boolean recordChildInvocations;
    private final boolean parentTaskLineage;

    public AuditPolicy(boolean recordChildInvocations, boolean parentTaskLineage) {
        this.recordChildInvocations = recordChildInvocations;
        this.parentTaskLineage = parentTaskLineage;
    }

    public boolean isRecordChildInvocations() {
        return recordChildInvocations;
    }

    public boolean isParentTaskLineage() {
        return parentTaskLineage;
    }
}
