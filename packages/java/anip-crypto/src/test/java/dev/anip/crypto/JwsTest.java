package dev.anip.crypto;

import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.*;

class JwsTest {

    @Test
    void signAndVerify() throws Exception {
        KeyManager km = KeyManager.create(null);

        byte[] payload = "{\"protocol\":\"anip/0.13\",\"capabilities\":{}}".getBytes(StandardCharsets.UTF_8);

        String sig = JwsSigner.signDetachedJws(km, payload);
        assertNotNull(sig);

        // Should not throw
        JwsSigner.verifyDetachedJws(km, payload, sig);
    }

    @Test
    void verifyFailsWithWrongPayload() throws Exception {
        KeyManager km = KeyManager.create(null);

        byte[] payload = "{\"protocol\":\"anip/0.13\",\"capabilities\":{}}".getBytes(StandardCharsets.UTF_8);

        String sig = JwsSigner.signDetachedJws(km, payload);

        byte[] wrongPayload = "{\"protocol\":\"anip/0.12\",\"capabilities\":{}}".getBytes(StandardCharsets.UTF_8);
        assertThrows(Exception.class, () ->
                JwsSigner.verifyDetachedJws(km, wrongPayload, sig));
    }

    @Test
    void verifyFailsWithWrongKey() throws Exception {
        KeyManager km1 = KeyManager.create(null);
        KeyManager km2 = KeyManager.create(null);

        byte[] payload = "test payload".getBytes(StandardCharsets.UTF_8);

        String sig = JwsSigner.signDetachedJws(km1, payload);

        assertThrows(Exception.class, () ->
                JwsSigner.verifyDetachedJws(km2, payload, sig));
    }

    @Test
    void detachedFormat() throws Exception {
        KeyManager km = KeyManager.create(null);

        byte[] payload = "test".getBytes(StandardCharsets.UTF_8);

        String sig = JwsSigner.signDetachedJws(km, payload);

        // Detached JWS should have format: header..signature (empty middle part)
        String[] parts = sig.split("\\.", -1);
        assertEquals(3, parts.length, "expected 3 parts");
        assertTrue(parts[1].isEmpty(), "middle part should be empty for detached JWS");
        assertFalse(parts[0].isEmpty(), "header part should not be empty");
        assertFalse(parts[2].isEmpty(), "signature part should not be empty");
    }
}
