package dev.anip.crypto;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.ECDSASigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import java.util.Date;
import java.util.List;
import java.util.Map;

/**
 * Signs delegation tokens as ES256 JWTs.
 */
public final class JwtSigner {

    private JwtSigner() {}

    /**
     * Signs a delegation JWT with ES256 using the delegation key pair.
     * <p>
     * The claims map should include standard JWT claims (jti, iss, sub, aud, iat, exp)
     * plus ANIP claims (scope, root_principal, capability, parent_token_id, purpose, constraints).
     *
     * @param km     the key manager containing the delegation key pair
     * @param claims the claims to include in the JWT
     * @return the compact serialized JWT string
     */
    public static String signDelegationJwt(KeyManager km, Map<String, Object> claims) throws JOSEException {
        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.ES256)
                .keyID(km.getDelegationKid())
                .type(com.nimbusds.jose.JOSEObjectType.JWT)
                .build();

        JWTClaimsSet.Builder claimsBuilder = new JWTClaimsSet.Builder();

        for (Map.Entry<String, Object> entry : claims.entrySet()) {
            String key = entry.getKey();
            Object value = entry.getValue();

            switch (key) {
                case "jti" -> claimsBuilder.jwtID((String) value);
                case "iss" -> claimsBuilder.issuer((String) value);
                case "sub" -> claimsBuilder.subject((String) value);
                case "aud" -> {
                    if (value instanceof String s) {
                        claimsBuilder.audience(s);
                    } else if (value instanceof List<?> list) {
                        claimsBuilder.audience(list.stream().map(Object::toString).toList());
                    }
                }
                case "iat" -> {
                    if (value instanceof Number n) {
                        claimsBuilder.issueTime(new Date(n.longValue() * 1000));
                    } else if (value instanceof Date d) {
                        claimsBuilder.issueTime(d);
                    }
                }
                case "exp" -> {
                    if (value instanceof Number n) {
                        claimsBuilder.expirationTime(new Date(n.longValue() * 1000));
                    } else if (value instanceof Date d) {
                        claimsBuilder.expirationTime(d);
                    }
                }
                default -> claimsBuilder.claim(key, value);
            }
        }

        SignedJWT signedJWT = new SignedJWT(header, claimsBuilder.build());
        ECDSASigner signer = new ECDSASigner(km.getDelegationECKey());
        signedJWT.sign(signer);

        return signedJWT.serialize();
    }

    /**
     * Signs a JWT with ES256 using the audit key pair.
     * Used for signing audit entries (contains audit_hash claim).
     *
     * @param km     the key manager containing the audit key pair
     * @param claims the claims to include in the JWT
     * @return the compact serialized JWT string
     */
    public static String signAuditJwt(KeyManager km, Map<String, Object> claims) throws JOSEException {
        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.ES256)
                .keyID(km.getAuditKid())
                .type(com.nimbusds.jose.JOSEObjectType.JWT)
                .build();

        JWTClaimsSet.Builder claimsBuilder = new JWTClaimsSet.Builder();
        for (Map.Entry<String, Object> entry : claims.entrySet()) {
            claimsBuilder.claim(entry.getKey(), entry.getValue());
        }

        SignedJWT signedJWT = new SignedJWT(header, claimsBuilder.build());
        ECDSASigner signer = new ECDSASigner(km.getAuditECKey());
        signedJWT.sign(signer);

        return signedJWT.serialize();
    }

    /**
     * Creates a detached JWS signature using the audit key pair.
     * Used for signing checkpoints.
     *
     * @param km      the key manager containing the audit key pair
     * @param payload the payload bytes to sign
     * @return the detached JWS string in format "header..signature"
     */
    public static String signDetachedJwsAudit(KeyManager km, byte[] payload) throws JOSEException {
        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.ES256)
                .keyID(km.getAuditKid())
                .build();

        com.nimbusds.jose.JWSObject jwsObject =
                new com.nimbusds.jose.JWSObject(header, new com.nimbusds.jose.Payload(payload));
        ECDSASigner signer = new ECDSASigner(km.getAuditECKey());
        jwsObject.sign(signer);

        // Serialize as compact, then remove the payload part to make it detached.
        String compact = jwsObject.serialize();
        String[] parts = compact.split("\\.", 3);
        return parts[0] + ".." + parts[2];
    }
}
