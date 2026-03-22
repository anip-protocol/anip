package dev.anip.graphql;

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
 * Per-field auth resolution for the GraphQL interface.
 * JWT-first, API-key-fallback. Subject "adapter:anip-graphql".
 * Auth errors in result body, not HTTP errors.
 */
public class GraphQLAuthBridge {

    private GraphQLAuthBridge() {}

    /**
     * Resolves auth from a bearer token for a GraphQL field.
     * Same pattern as REST auth bridge but with graphql subject and source.
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

        // Try as API key.
        Optional<String> principal = service.authenticateBearer(bearer);
        if (principal.isPresent() && !principal.get().isEmpty()) {
            CapabilityDeclaration capDecl = service.getCapabilityDeclaration(capabilityName);
            List<String> minScope = null;
            if (capDecl != null) {
                minScope = capDecl.getMinimumScope();
            }
            if (minScope == null || minScope.isEmpty()) {
                minScope = List.of("*");
            }

            TokenRequest req = new TokenRequest(
                    "adapter:anip-graphql", minScope, capabilityName,
                    Map.of("source", "graphql"), null, 0, null
            );

            TokenResponse tokenResp;
            try {
                tokenResp = service.issueToken(principal.get(), req);
            } catch (Exception issueErr) {
                throw issueErr;
            }

            return service.resolveBearerToken(tokenResp.getToken());
        }

        throw jwtError;
    }
}
