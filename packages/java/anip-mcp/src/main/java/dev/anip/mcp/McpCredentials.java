package dev.anip.mcp;

import java.util.List;

/**
 * Mount-time credentials for stdio MCP transport.
 * Since stdio has no per-request auth, credentials are provided once at mount time.
 */
public class McpCredentials {

    private final String apiKey;
    private final List<String> scope;
    private final String subject;

    public McpCredentials(String apiKey, List<String> scope, String subject) {
        this.apiKey = apiKey;
        this.scope = scope;
        this.subject = subject;
    }

    public String getApiKey() {
        return apiKey;
    }

    public List<String> getScope() {
        return scope;
    }

    public String getSubject() {
        return subject;
    }
}
