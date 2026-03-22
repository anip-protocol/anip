package dev.anip.core;

import java.util.List;

/**
 * Wraps audit query results.
 */
public class AuditResponse {

    private final List<AuditEntry> entries;
    private final int count;
    private final String rootPrincipal;
    private final String capabilityFilter;
    private final String sinceFilter;

    public AuditResponse(List<AuditEntry> entries, int count, String rootPrincipal,
                         String capabilityFilter, String sinceFilter) {
        this.entries = entries;
        this.count = count;
        this.rootPrincipal = rootPrincipal;
        this.capabilityFilter = capabilityFilter;
        this.sinceFilter = sinceFilter;
    }

    public List<AuditEntry> getEntries() {
        return entries;
    }

    public int getCount() {
        return count;
    }

    public String getRootPrincipal() {
        return rootPrincipal;
    }

    public String getCapabilityFilter() {
        return capabilityFilter;
    }

    public String getSinceFilter() {
        return sinceFilter;
    }
}
