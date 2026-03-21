package dev.anip.core;

/**
 * Filters for querying audit entries.
 */
public class AuditFilters {

    private final String capability;
    private final String since;
    private final String invocationId;
    private final String clientReferenceId;
    private final int limit;

    public AuditFilters(String capability, String since, String invocationId,
                        String clientReferenceId, int limit) {
        this.capability = capability;
        this.since = since;
        this.invocationId = invocationId;
        this.clientReferenceId = clientReferenceId;
        this.limit = limit;
    }

    public String getCapability() {
        return capability;
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
