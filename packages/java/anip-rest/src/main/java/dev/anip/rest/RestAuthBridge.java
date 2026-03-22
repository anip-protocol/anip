package dev.anip.rest;

import dev.anip.core.ANIPError;
import dev.anip.core.CapabilityDeclaration;
import dev.anip.core.DelegationToken;
import dev.anip.core.TokenRequest;
import dev.anip.core.TokenResponse;
import dev.anip.service.ANIPService;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Shared auth bridge for the REST interface.
 * JWT-first, API-key-fallback. Only catches ANIPError from JWT resolution.
 */
public class RestAuthBridge {

    private RestAuthBridge() {}

    /**
     * Resolves auth from a bearer token.
     *
     * 1. Try service.resolveBearerToken(bearer) -- JWT mode
     * 2. If ANIPError -- try service.authenticateBearer(bearer) -- API key mode
     * 3. If API key works -- issue synthetic token
     * 4. If token issuance fails -- return the real issuance error
     * 5. If neither -- re-throw original JWT error
     * 6. Only catch ANIPError from JWT, rethrow unexpected exceptions
     */
    public static DelegationToken resolveAuth(String bearer, ANIPService service,
                                               String capabilityName) throws Exception {
        // Try as JWT first.
        ANIPError jwtError;
        try {
            return service.resolveBearerToken(bearer);
        } catch (ANIPError e) {
            jwtError = e;
        }
        // Only ANIPError is caught; any other exception propagates.

        // Try as API key.
        Optional<String> principal = service.authenticateBearer(bearer);
        if (principal.isPresent() && !principal.get().isEmpty()) {
            // Issue synthetic token.
            CapabilityDeclaration capDecl = service.getCapabilityDeclaration(capabilityName);
            List<String> minScope = null;
            if (capDecl != null) {
                minScope = capDecl.getMinimumScope();
            }
            if (minScope == null || minScope.isEmpty()) {
                minScope = List.of("*");
            }

            TokenRequest req = new TokenRequest(
                    "adapter:anip-rest", minScope, capabilityName,
                    Map.of("source", "rest"), null, 0, null
            );

            TokenResponse tokenResp;
            try {
                tokenResp = service.issueToken(principal.get(), req);
            } catch (Exception issueErr) {
                // Return the real issuance error, not the stale JWT error.
                throw issueErr;
            }

            return service.resolveBearerToken(tokenResp.getToken());
        }

        // Neither JWT nor API key -- surface the original JWT error.
        throw jwtError;
    }
}
