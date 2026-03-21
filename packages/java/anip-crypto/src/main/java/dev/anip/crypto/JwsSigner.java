package dev.anip.crypto;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.JWSObject;
import com.nimbusds.jose.Payload;
import com.nimbusds.jose.crypto.ECDSASigner;
import com.nimbusds.jose.crypto.ECDSAVerifier;
import com.nimbusds.jose.util.Base64URL;

import java.text.ParseException;

/**
 * Handles detached JWS signing and verification for the X-ANIP-Signature header.
 */
public final class JwsSigner {

    private JwsSigner() {}

    /**
     * Creates a detached JWS signature for the given payload.
     * The result is a compact JWS with an empty payload: "header..signature".
     * Used for the X-ANIP-Signature header on manifest responses.
     *
     * @param km      the key manager (uses delegation key)
     * @param payload the payload bytes to sign
     * @return the detached JWS string in format "header..signature"
     */
    public static String signDetachedJws(KeyManager km, byte[] payload) throws JOSEException {
        JWSHeader header = new JWSHeader.Builder(JWSAlgorithm.ES256)
                .keyID(km.getDelegationKid())
                .build();

        JWSObject jwsObject = new JWSObject(header, new Payload(payload));
        ECDSASigner signer = new ECDSASigner(km.getDelegationECKey());
        jwsObject.sign(signer);

        // Serialize as compact, then remove the payload part to make it detached
        String compact = jwsObject.serialize();
        // compact format is: header.payload.signature
        // detached format is: header..signature
        String[] parts = compact.split("\\.", 3);
        return parts[0] + ".." + parts[2];
    }

    /**
     * Verifies a detached JWS signature against the given payload.
     *
     * @param km        the key manager (uses delegation public key)
     * @param payload   the original payload bytes
     * @param signature the detached JWS string ("header..signature")
     * @throws JOSEException if verification fails
     */
    public static void verifyDetachedJws(KeyManager km, byte[] payload, String signature)
            throws JOSEException, ParseException {

        // Split the detached JWS: "header..signature"
        String[] parts = signature.split("\\.", -1);
        if (parts.length != 3) {
            throw new JOSEException("Invalid detached JWS format: expected 3 parts");
        }
        if (!parts[1].isEmpty()) {
            throw new JOSEException("Invalid detached JWS: payload part should be empty");
        }

        // Reconstruct the full JWS by inserting the payload
        Base64URL payloadB64 = Base64URL.encode(payload);
        String fullJws = parts[0] + "." + payloadB64 + "." + parts[2];

        JWSObject jwsObject = JWSObject.parse(fullJws);
        ECDSAVerifier verifier = new ECDSAVerifier(km.getDelegationECKey().toECPublicKey());

        if (!jwsObject.verify(verifier)) {
            throw new JOSEException("Invalid signature");
        }
    }
}
