package dev.anip.example.flights;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.math.BigInteger;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.KeyFactory;
import java.security.Signature;
import java.security.interfaces.RSAPublicKey;
import java.security.spec.RSAPublicKeySpec;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * OIDC JWT validator for the example app.
 * <p>
 * Validates RS256 JWTs against a provider's JWKS endpoint and maps
 * OIDC claims to ANIP principal identifiers. Fully synchronous.
 * <p>
 * This is example-app code, not an SDK package. Real deployments should
 * define their own claim-to-principal mapping policy.
 */
final class OidcValidator {

    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    private final String issuerUrl;
    private final String audience;
    private volatile String jwksUrl;
    private final ConcurrentHashMap<String, RSAPublicKey> keys = new ConcurrentHashMap<>();

    OidcValidator(String issuerUrl, String audience, String jwksUrl) {
        this.issuerUrl = issuerUrl.replaceAll("/+$", "");
        this.audience = audience;
        this.jwksUrl = jwksUrl;
    }

    /**
     * Validates an OIDC bearer token and returns the mapped ANIP principal,
     * or empty if validation fails.
     */
    Optional<String> validate(String bearer) {
        try {
            // Parse JWT header and claims without verifying signature.
            String[] parts = bearer.split("\\.", 3);
            if (parts.length != 3) return Optional.empty();

            @SuppressWarnings("unchecked")
            Map<String, Object> header = MAPPER.readValue(
                    Base64.getUrlDecoder().decode(parts[0]), Map.class);
            @SuppressWarnings("unchecked")
            Map<String, Object> claims = MAPPER.readValue(
                    Base64.getUrlDecoder().decode(parts[1]), Map.class);

            String alg = (String) header.get("alg");
            if (!"RS256".equals(alg)) return Optional.empty();

            String kid = (String) header.get("kid");
            if (kid == null || kid.isEmpty()) return Optional.empty();

            // Get public key, refreshing JWKS on kid-miss.
            RSAPublicKey key = keys.get(kid);
            if (key == null) {
                refreshJwks();
                key = keys.get(kid);
            }
            if (key == null) return Optional.empty();

            // Verify RS256 signature.
            byte[] signingInput = (parts[0] + "." + parts[1]).getBytes();
            byte[] sig = Base64.getUrlDecoder().decode(parts[2]);
            Signature verifier = Signature.getInstance("SHA256withRSA");
            verifier.initVerify(key);
            verifier.update(signingInput);
            if (!verifier.verify(sig)) return Optional.empty();

            // Verify claims.
            if (!verifyClaims(claims)) return Optional.empty();

            // Map claims to principal.
            return mapClaimsToPrincipal(claims);
        } catch (Exception e) {
            return Optional.empty();
        }
    }

    private boolean verifyClaims(Map<String, Object> claims) {
        // Check issuer.
        String iss = (String) claims.get("iss");
        if (!issuerUrl.equals(iss)) return false;

        // Check audience.
        Object aud = claims.get("aud");
        if (aud instanceof String s) {
            if (!audience.equals(s)) return false;
        } else if (aud instanceof List<?> list) {
            boolean found = false;
            for (Object a : list) {
                if (audience.equals(a)) { found = true; break; }
            }
            if (!found) return false;
        } else {
            return false;
        }

        // Check expiry.
        Object expObj = claims.get("exp");
        if (expObj instanceof Number n) {
            if (Instant.now().getEpochSecond() > n.longValue()) return false;
        } else {
            return false;
        }

        return true;
    }

    private static Optional<String> mapClaimsToPrincipal(Map<String, Object> claims) {
        Object email = claims.get("email");
        if (email instanceof String s && !s.isEmpty()) {
            return Optional.of("human:" + s);
        }
        Object username = claims.get("preferred_username");
        if (username instanceof String s && !s.isEmpty()) {
            return Optional.of("human:" + s);
        }
        Object sub = claims.get("sub");
        if (sub instanceof String s && !s.isEmpty()) {
            return Optional.of("oidc:" + s);
        }
        return Optional.empty();
    }

    @SuppressWarnings("unchecked")
    private void refreshJwks() {
        try {
            String url = jwksUrl;

            // Discover JWKS URL from OIDC discovery if not explicitly set.
            if (url == null || url.isEmpty()) {
                String discoveryUrl = issuerUrl + "/.well-known/openid-configuration";
                HttpResponse<String> resp = HTTP.send(
                        HttpRequest.newBuilder(URI.create(discoveryUrl)).GET().build(),
                        HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() != 200) return;
                Map<String, Object> doc = MAPPER.readValue(resp.body(), Map.class);
                url = (String) doc.get("jwks_uri");
                if (url == null || url.isEmpty()) return;
                jwksUrl = url;
            }

            HttpResponse<String> resp = HTTP.send(
                    HttpRequest.newBuilder(URI.create(url)).GET().build(),
                    HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() != 200) return;

            Map<String, Object> jwks = MAPPER.readValue(resp.body(), Map.class);
            List<Map<String, Object>> keyList = (List<Map<String, Object>>) jwks.get("keys");
            if (keyList == null) return;

            ConcurrentHashMap<String, RSAPublicKey> newKeys = new ConcurrentHashMap<>();
            for (Map<String, Object> jwk : keyList) {
                String kty = (String) jwk.get("kty");
                String kid = (String) jwk.get("kid");
                if (!"RSA".equals(kty) || kid == null) continue;

                String n = (String) jwk.get("n");
                String e = (String) jwk.get("e");
                if (n == null || e == null) continue;

                BigInteger modulus = new BigInteger(1, Base64.getUrlDecoder().decode(n));
                BigInteger exponent = new BigInteger(1, Base64.getUrlDecoder().decode(e));
                RSAPublicKeySpec spec = new RSAPublicKeySpec(modulus, exponent);
                RSAPublicKey pubKey = (RSAPublicKey) KeyFactory.getInstance("RSA").generatePublic(spec);
                newKeys.put(kid, pubKey);
            }

            keys.clear();
            keys.putAll(newKeys);
        } catch (Exception ignored) {
            // Best effort.
        }
    }
}
