package dev.anip.crypto;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class KeyManagerTest {

    @Test
    void keyGeneration() throws Exception {
        KeyManager km = KeyManager.create(null);

        assertNotNull(km.getDelegationPrivateKey());
        assertNotNull(km.getDelegationPublicKey());
        assertNotNull(km.getDelegationKid());
        assertFalse(km.getDelegationKid().isEmpty());

        assertNotNull(km.getAuditPrivateKey());
        assertNotNull(km.getAuditPublicKey());
        assertNotNull(km.getAuditKid());
        assertFalse(km.getAuditKid().isEmpty());

        // Delegation and audit keys should be different
        assertNotEquals(km.getDelegationKid(), km.getAuditKid());
    }

    @Test
    void keyRoundTripDirectory(@TempDir Path tempDir) throws Exception {
        Path keyDir = tempDir.resolve("test-keys");

        // Generate and save
        KeyManager km1 = KeyManager.create(keyDir.toString());

        // Load from disk
        KeyManager km2 = KeyManager.create(keyDir.toString());

        // KIDs should match
        assertEquals(km1.getDelegationKid(), km2.getDelegationKid());
        assertEquals(km1.getAuditKid(), km2.getAuditKid());

        // Sign with km1, verify with km2
        long now = Instant.now().getEpochSecond();
        Map<String, Object> claims = Map.of(
                "jti", "test-123",
                "iss", "test-service",
                "sub", "agent:test",
                "aud", "test-service",
                "iat", now,
                "exp", now + 3600
        );

        String token = JwtSigner.signDelegationJwt(km1, claims);
        Map<String, Object> decoded = JwtVerifier.verifyDelegationJwt(km2, token, "test-service", "test-service");
        assertEquals("test-123", decoded.get("jti"));
    }

    @Test
    void keyRoundTripFile(@TempDir Path tempDir) throws Exception {
        Path keyFile = tempDir.resolve("keys.json");

        // Generate and save to a specific file path
        KeyManager km1 = KeyManager.create(keyFile.toString());

        // Verify file exists
        assertTrue(Files.exists(keyFile));

        // Load from file
        KeyManager km2 = KeyManager.create(keyFile.toString());

        assertEquals(km1.getDelegationKid(), km2.getDelegationKid());
        assertEquals(km1.getAuditKid(), km2.getAuditKid());
    }

    @Test
    void kidIsDeterministic() throws Exception {
        KeyManager km = KeyManager.create(null);

        // KID should be consistent
        String kid1 = km.getDelegationKid();
        String kid2 = km.getDelegationKid();
        assertEquals(kid1, kid2);

        // KID should be 16 chars
        assertEquals(16, kid1.length());
        assertEquals(16, km.getAuditKid().length());
    }
}
