package dev.anip.crypto;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class JwksTest {

    @SuppressWarnings("unchecked")
    @Test
    void jwksFormat() throws Exception {
        KeyManager km = KeyManager.create(null);

        Map<String, Object> jwks = JwksSerializer.toJwks(km);

        List<Map<String, Object>> keys = (List<Map<String, Object>>) jwks.get("keys");
        assertNotNull(keys);
        assertEquals(2, keys.size());

        // Check delegation key
        Map<String, Object> delKey = keys.get(0);
        assertEquals("EC", delKey.get("kty"));
        assertEquals("P-256", delKey.get("crv"));
        assertEquals("ES256", String.valueOf(delKey.get("alg")));
        assertEquals("sig", delKey.get("use"));
        assertEquals(km.getDelegationKid(), delKey.get("kid"));
        assertNotNull(delKey.get("x"));
        assertNotNull(delKey.get("y"));
        // Should not contain private key material
        assertNull(delKey.get("d"), "JWKS should not contain private key 'd' parameter");

        // Check audit key
        Map<String, Object> auditKey = keys.get(1);
        assertEquals("EC", auditKey.get("kty"));
        assertEquals("P-256", auditKey.get("crv"));
        assertEquals("ES256", String.valueOf(auditKey.get("alg")));
        assertEquals("audit", auditKey.get("use"));
        assertEquals(km.getAuditKid(), auditKey.get("kid"));
        assertNotNull(auditKey.get("x"));
        assertNotNull(auditKey.get("y"));
        assertNull(auditKey.get("d"), "JWKS should not contain private key 'd' parameter");
    }

    @SuppressWarnings("unchecked")
    @Test
    void jwksContainsOnlyPublicKeys() throws Exception {
        KeyManager km = KeyManager.create(null);

        Map<String, Object> jwks = JwksSerializer.toJwks(km);
        List<Map<String, Object>> keys = (List<Map<String, Object>>) jwks.get("keys");

        for (Map<String, Object> key : keys) {
            assertNull(key.get("d"), "JWKS should not expose private key parameter 'd'");
        }
    }
}
