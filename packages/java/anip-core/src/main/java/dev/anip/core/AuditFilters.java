package dev.anip.core;

/**
 * Filters for querying audit entries.
 */
public class AuditFilters {

    private final String capability;
    private final String rootPrincipal;
    private final String since;
    private final String invocationId;
    private final String clientReferenceId;
    private final String taskId;
    private final String parentInvocationId;
    private final int limit;

    public AuditFilters(String capability, String since, String invocationId,
                        String clientReferenceId, int limit) {
        this(capability, null, since, invocationId, clientReferenceId, null, null, limit);
    }

    public AuditFilters(String capability, String rootPrincipal, String since,
                        String invocationId, String clientReferenceId, int limit) {
        this(capability, rootPrincipal, since, invocationId, clientReferenceId, null, null, limit);
    }

    public AuditFilters(String capability, String rootPrincipal, String since,
                        String invocationId, String clientReferenceId,
                        String taskId, String parentInvocationId, int limit) {
        this.capability = capability;
        this.rootPrincipal = rootPrincipal;
        this.since = since;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
        this.taskId = taskId;
        this.parentInvocationId = parentInvocationId;
        this.limit = limit;
    }

    public String getCapability() {
        return capability;
    }

    public String getRootPrincipal() {
        return rootPrincipal;
    }

    public String getSince() {
        return since;
    }

    public String getInvocationId() {
        return invocationId;
    }

    public String getClientReferenceId() {
        return clientReferenceId;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getParentInvocationId() {
        return parentInvocationId;
    }

    public int getLimit() {
        return limit;
    }
}
