package dev.anip.core;

/**
 * The server's response to token issuance.
 */
public class TokenResponse {

    private final boolean issued;
    private final String tokenId;
    private final String token;
    private final String expires;
    private final String taskId;

    public TokenResponse(boolean issued, String tokenId, String token, String expires) {
        this(issued, tokenId, token, expires, null);
    }

    public TokenResponse(boolean issued, String tokenId, String token, String expires, String taskId) {
        this.issued = issued;
        this.tokenId = tokenId;
        this.token = token;
        this.expires = expires;
        this.taskId = taskId;
    }

    public boolean isIssued() {
        return issued;
    }

    public String getTokenId() {
        return tokenId;
    }

    /** JWT string. */
    public String getToken() {
        return token;
    }

    public String getExpires() {
        return expires;
    }

    /** Echoed when the issued token has a resolved purpose.task_id. May be null. */
    public String getTaskId() {
        return taskId;
    }
}
