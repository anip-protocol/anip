package dev.anip.server;

import dev.anip.core.ANIPError;
import dev.anip.core.Constants;
import dev.anip.core.DelegationConstraints;
import dev.anip.core.DelegationToken;
import dev.anip.core.Purpose;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.crypto.JwtSigner;
import dev.anip.crypto.JwtVerifier;
import dev.anip.crypto.KeyManager;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Handles delegation token issuance, resolution, and scope validation.
 */
public final class DelegationEngine {

    private static final SecureRandom RANDOM = new SecureRandom();

    private DelegationEngine() {}

    /**
     * Creates a delegation token, signs it as a JWT, and stores it.
     *
     * @param km        the key manager for signing
     * @param storage   the storage backend
     * @param serviceId the service identifier (issuer and audience)
     * @param principal the authenticated principal making the request
     * @param req       the token request
     * @return the token response containing the signed JWT
     */
    public static TokenResponse issueDelegationToken(
            KeyManager km, Storage storage, String serviceId,
            String principal, TokenRequest req) throws Exception {

        String tokenId = generateTokenId();
        Instant now = Instant.now();

        int ttlHours = req.getTtlHours();
        if (ttlHours <= 0) {
            ttlHours = 2;
        }
        Instant expires = now.plusSeconds((long) ttlHours * 3600);

        // Build purpose.
        Map<String, Object> purposeParams = req.getPurposeParameters();
        if (purposeParams == null) {
            purposeParams = Map.of();
        }
        Purpose purpose = new Purpose(
                req.getCapability(),
                purposeParams,
                "task-" + tokenId
        );

        // Build constraints.
        DelegationConstraints constraints = new DelegationConstraints(3, "allowed");

        // Determine issuer and root_principal.
        String issuer = serviceId;
        String rootPrincipal = principal;
        String parent = "";

        // If there's a parent token, look it up by ID for sub-delegation.
        if (req.getParentToken() != null && !req.getParentToken().isEmpty()) {
            DelegationToken parentToken = storage.loadToken(req.getParentToken());
            if (parentToken == null) {
                throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                        "parent token not found: " + req.getParentToken());
            }

            issuer = parentToken.getSubject();
            rootPrincipal = parentToken.getRootPrincipal();
            parent = parentToken.getTokenId();
            constraints = parentToken.getConstraints();
        }

        // Default subject to the authenticated principal if not provided.
        String subject = req.getSubject();
        if (subject == null || subject.isEmpty()) {
            subject = principal;
        }

        String expiresStr = DateTimeFormatter.ISO_INSTANT.format(expires);

        // Build the token record.
        DelegationToken token = new DelegationToken(
                tokenId, issuer, subject, req.getScope(), purpose,
                parent, expiresStr, constraints, rootPrincipal, req.getCallerClass()
        );

        // Store the token.
        storage.storeToken(token);

        // Sign as JWT.
        Map<String, Object> claims = new HashMap<>();
        claims.put("jti", tokenId);
        claims.put("iss", serviceId);
        claims.put("sub", subject);
        claims.put("aud", serviceId);
        claims.put("iat", now.getEpochSecond());
        claims.put("exp", expires.getEpochSecond());
        claims.put("scope", req.getScope());
        claims.put("root_principal", rootPrincipal);
        claims.put("capability", req.getCapability());
        claims.put("purpose", JsonHelper.toMap(purpose));
        claims.put("constraints", JsonHelper.toMap(constraints));
        if (!parent.isEmpty()) {
            claims.put("parent_token_id", parent);
        }

        String jwt = JwtSigner.signDelegationJwt(km, claims);

        return new TokenResponse(true, tokenId, jwt, expiresStr);
    }

    /**
     * Verifies a JWT, loads the stored token, and compares signed claims
     * against stored state to prevent forged inline fields.
     *
     * @param km        the key manager for verification
     * @param storage   the storage backend
     * @param serviceId the service identifier (issuer and audience)
     * @param jwtStr    the compact serialized JWT string
     * @return the stored delegation token
     */
    public static DelegationToken resolveBearerToken(
            KeyManager km, Storage storage, String serviceId, String jwtStr) throws Exception {

        // 1. Verify JWT signature + expiry + issuer/audience.
        Map<String, Object> claims;
        try {
            claims = JwtVerifier.verifyDelegationJwt(km, jwtStr, serviceId, serviceId);
        } catch (SecurityException e) {
            String msg = e.getMessage();
            if (msg != null && msg.contains("expired")) {
                throw new ANIPError(Constants.FAILURE_TOKEN_EXPIRED,
                        "delegation token has expired");
            }
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "JWT verification failed: " + msg);
        } catch (Exception e) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "JWT verification failed: " + e.getMessage());
        }

        // 2. Extract jti -> token_id.
        Object jtiObj = claims.get("jti");
        String tokenId = jtiObj instanceof String s ? s : null;
        if (tokenId == null || tokenId.isEmpty()) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN, "JWT missing jti claim");
        }

        // 3. Load stored token.
        DelegationToken stored;
        try {
            stored = storage.loadToken(tokenId);
        } catch (Exception e) {
            throw new ANIPError(Constants.FAILURE_INTERNAL_ERROR,
                    "error loading token: " + e.getMessage());
        }
        if (stored == null) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN, "token not found in storage");
        }

        // 4. Compare signed claims against stored state.
        Object subObj = claims.get("sub");
        if (subObj instanceof String sub && !sub.equals(stored.getSubject())) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "subject mismatch between JWT and stored token");
        }

        Object rpObj = claims.get("root_principal");
        if (rpObj instanceof String rp && !rp.equals(stored.getRootPrincipal())) {
            throw new ANIPError(Constants.FAILURE_INVALID_TOKEN,
                    "root_principal mismatch between JWT and stored token");
        }

        // 5. Return stored token.
        return stored;
    }

    /**
     * Checks if the token's scope covers the capability's minimum_scope.
     * Throws ANIPError with scope_insufficient if insufficient.
     *
     * @param token        the delegation token to validate
     * @param minimumScope the required scope strings
     */
    public static void validateScope(DelegationToken token, List<String> minimumScope) {
        if (minimumScope == null || minimumScope.isEmpty()) {
            return;
        }

        // Extract base scopes from token (before ':' modifier).
        List<String> tokenScopeBases = token.getScope().stream()
                .map(s -> s.split(":")[0])
                .toList();

        List<String> missing = minimumScope.stream()
                .filter(required -> tokenScopeBases.stream().noneMatch(
                        base -> base.equals(required) || required.startsWith(base + ".")))
                .toList();

        if (!missing.isEmpty()) {
            throw new ANIPError(
                    Constants.FAILURE_SCOPE_INSUFFICIENT,
                    "delegation chain lacks scope(s): " + String.join(", ", missing)
            ).withResolution("request_scope_grant");
        }
    }

    /**
     * Generates a random token ID in the format "anip-{12 hex chars}".
     */
    private static String generateTokenId() {
        byte[] b = new byte[6];
        RANDOM.nextBytes(b);
        StringBuilder sb = new StringBuilder("anip-");
        for (byte v : b) {
            sb.append(String.format("%02x", v & 0xff));
        }
        return sb.toString();
    }
}
