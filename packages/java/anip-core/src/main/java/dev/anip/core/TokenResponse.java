package dev.anip.core;

/**
 * The server's response to token issuance.
 */
public class TokenResponse {

    private final boolean issued;
    private final String tokenId;
    private final String token;
    private final String expires;

    public TokenResponse(boolean issued, String tokenId, String token, String expires) {
        this.issued = issued;
        this.tokenId = tokenId;
        this.token = token;
        this.expires = expires;
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
}
