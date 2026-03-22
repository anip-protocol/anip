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
    private final int limit;

    public AuditFilters(String capability, String since, String invocationId,
                        String clientReferenceId, int limit) {
        this(capability, null, since, invocationId, clientReferenceId, limit);
    }

    public AuditFilters(String capability, String rootPrincipal, String since,
                        String invocationId, String clientReferenceId, int limit) {
        this.capability = capability;
        this.rootPrincipal = rootPrincipal;
        this.since = since;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
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

    public int getLimit() {
        return limit;
    }
}
