package dev.anip.crypto;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class JwtTest {

    @Test
    void signAndVerify() throws Exception {
        KeyManager km = KeyManager.create(null);

        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "token-001",
                "iss", "anip-test-service",
                "sub", "agent:demo",
                "aud", "anip-test-service",
                "iat", now,
                "exp", now + 7200,
                "scope", List.of("travel.search"),
                "root_principal", "human:test@example.com",
                "capability", "search_flights"
        );

        String token = JwtSigner.signDelegationJwt(km, claims);
        assertNotNull(token);
        assertFalse(token.isEmpty());

        Map<String, Object> decoded = JwtVerifier.verifyDelegationJwt(
                km, token, "anip-test-service", "anip-test-service");

        assertEquals("token-001", decoded.get("jti"));
        assertEquals("human:test@example.com", decoded.get("root_principal"));
        assertEquals("search_flights", decoded.get("capability"));

        // Verify scope is preserved
        @SuppressWarnings("unchecked")
        List<String> scope = (List<String>) decoded.get("scope");
        assertNotNull(scope);
        assertEquals(1, scope.size());
        assertEquals("travel.search", scope.get(0));
    }

    @Test
    void verifyFailsWithWrongKey() throws Exception {
        KeyManager km1 = KeyManager.create(null);
        KeyManager km2 = KeyManager.create(null);

        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "token-wrong",
                "iss", "service",
                "sub", "agent:test",
                "aud", "service",
                "iat", now,
                "exp", now + 3600
        );

        String token = JwtSigner.signDelegationJwt(km1, claims);

        // Verify with a different key should fail
        assertThrows(Exception.class, () ->
                JwtVerifier.verifyDelegationJwt(km2, token, "", "service"));
    }

    @Test
    void verifyFailsWhenExpired() throws Exception {
        KeyManager km = KeyManager.create(null);

        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "expired-token",
                "iss", "service",
                "sub", "agent:test",
                "aud", "service",
                "iat", now - 7200,
                "exp", now - 3600  // expired 1 hour ago
        );

        String token = JwtSigner.signDelegationJwt(km, claims);

        assertThrows(SecurityException.class, () ->
                JwtVerifier.verifyDelegationJwt(km, token, "", "service"));
    }

    @Test
    void issuerMismatchFails() throws Exception {
        KeyManager km = KeyManager.create(null);

        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "iss-test",
                "iss", "service-a",
                "sub", "agent:test",
                "aud", "service-a",
                "iat", now,
                "exp", now + 3600
        );

        String token = JwtSigner.signDelegationJwt(km, claims);

        assertThrows(SecurityException.class, () ->
                JwtVerifier.verifyDelegationJwt(km, token, "service-b", "service-a"));
    }

    @Test
    void audienceMismatchFails() throws Exception {
        KeyManager km = KeyManager.create(null);

        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "aud-test",
                "iss", "service",
                "sub", "agent:test",
                "aud", "service-a",
                "iat", now,
                "exp", now + 3600
        );

        String token = JwtSigner.signDelegationJwt(km, claims);

        assertThrows(SecurityException.class, () ->
                JwtVerifier.verifyDelegationJwt(km, token, "service", "service-b"));
    }
}
