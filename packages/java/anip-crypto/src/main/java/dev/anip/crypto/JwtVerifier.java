package dev.anip.crypto;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.crypto.ECDSAVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;

import java.text.ParseException;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

/**
 * Verifies and decodes ES256 JWTs signed by the delegation key.
 */
public final class JwtVerifier {

    private JwtVerifier() {}

    /**
     * Verifies and decodes an ES256 JWT signed by the delegation key.
     * Checks signature, expiration, issuer (if provided), and audience (if provided).
     *
     * @param km       the key manager containing the delegation public key
     * @param jwtStr   the compact serialized JWT string
     * @param issuer   expected issuer (null or empty to skip check)
     * @param audience expected audience (null or empty to skip check)
     * @return the decoded claims as a map
     * @throws JOSEException   if signature verification fails
     * @throws ParseException  if the JWT cannot be parsed
     * @throws SecurityException if validation checks fail (expiry, issuer, audience)
     */
    public static Map<String, Object> verifyDelegationJwt(KeyManager km, String jwtStr,
                                                           String issuer, String audience)
            throws JOSEException, ParseException {

        SignedJWT signedJWT = SignedJWT.parse(jwtStr);

        // Verify signature
        ECDSAVerifier verifier = new ECDSAVerifier(km.getDelegationECKey().toECPublicKey());
        if (!signedJWT.verify(verifier)) {
            throw new JOSEException("Invalid signature");
        }

        JWTClaimsSet claimsSet = signedJWT.getJWTClaimsSet();

        // Check expiration
        Date expiration = claimsSet.getExpirationTime();
        if (expiration != null && new Date().after(expiration)) {
            throw new SecurityException("Token expired");
        }

        // Check issuer
        if (issuer != null && !issuer.isEmpty()) {
            String tokenIssuer = claimsSet.getIssuer();
            if (tokenIssuer != null && !tokenIssuer.equals(issuer)) {
                throw new SecurityException(
                        "Issuer mismatch: expected \"" + issuer + "\", got \"" + tokenIssuer + "\"");
            }
        }

        // Check audience
        if (audience != null && !audience.isEmpty()) {
            var audiences = claimsSet.getAudience();
            if (audiences != null && !audiences.isEmpty() && !audiences.contains(audience)) {
                throw new SecurityException(
                        "Audience \"" + audience + "\" not in token audiences " + audiences);
            }
        }

        // Convert claims to a plain map
        Map<String, Object> result = new HashMap<>(claimsSet.getClaims());

        // Convert Date values to epoch seconds for consistency with other runtimes
        if (result.containsKey("iat") && result.get("iat") instanceof Date d) {
            result.put("iat", d.getTime() / 1000L);
        }
        if (result.containsKey("exp") && result.get("exp") instanceof Date d) {
            result.put("exp", d.getTime() / 1000L);
        }

        return result;
    }
}
