package dev.anip.crypto;

import com.nimbusds.jose.jwk.ECKey;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.KeyUse;

import java.util.List;
import java.util.Map;

/**
 * Serializes public keys as a JWKS (JSON Web Key Set).
 */
public final class JwksSerializer {

    private JwksSerializer() {}

    /**
     * Returns the JWKS representation of both public keys.
     * The delegation key has use="sig" and the audit key has use="audit".
     *
     * @param km the key manager
     * @return a Map with the standard JWKS format {"keys": [...]}
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Object> toJwks(KeyManager km) {
        ECKey delegationPublic = new ECKey.Builder(km.getDelegationECKey().toPublicJWK())
                .keyID(km.getDelegationKid())
                .keyUse(KeyUse.SIGNATURE)
                .algorithm(com.nimbusds.jose.JWSAlgorithm.ES256)
                .build();

        // For audit key, we need to set a custom "use" value
        ECKey auditPublic = new ECKey.Builder(km.getAuditECKey().toPublicJWK())
                .keyID(km.getAuditKid())
                .algorithm(com.nimbusds.jose.JWSAlgorithm.ES256)
                .build();

        // Build manually to support custom "use" value for audit key
        Map<String, Object> delMap = delegationPublic.toJSONObject();
        delMap.put("use", "sig");

        Map<String, Object> auditMap = auditPublic.toJSONObject();
        auditMap.put("use", "audit");

        return Map.of("keys", List.of(delMap, auditMap));
    }
}
