package dev.anip.crypto;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.jwk.Curve;
import com.nimbusds.jose.jwk.ECKey;
import com.nimbusds.jose.jwk.gen.ECKeyGenerator;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.interfaces.ECPrivateKey;
import java.security.interfaces.ECPublicKey;
import java.text.ParseException;

/**
 * Manages two ES256 key pairs: one for delegation tokens, one for audit entries.
 * Keys can be generated in memory or persisted to/loaded from a JSON file.
 */
public class KeyManager {

    private ECKey delegationKey;
    private ECKey auditKey;

    private KeyManager() {}

    /**
     * Creates a KeyManager by loading keys from keyPath or generating new ones.
     * If keyPath is null or empty, keys are generated in memory only.
     * If keyPath is a directory, uses "anip-keys.json" inside it.
     * If keyPath is a file path, uses it directly.
     */
    public static KeyManager create(String keyPath) throws IOException, JOSEException, ParseException {
        KeyManager km = new KeyManager();

        if (keyPath != null && !keyPath.isEmpty()) {
            Path path = Path.of(keyPath);
            Path keysFile;

            if (Files.isDirectory(path)) {
                keysFile = path.resolve("anip-keys.json");
            } else if (!Files.exists(path) && !keyPath.endsWith(".json")) {
                // Looks like a directory path - create it
                Files.createDirectories(path);
                keysFile = path.resolve("anip-keys.json");
            } else {
                keysFile = path;
            }

            if (Files.exists(keysFile)) {
                km.loadFromFile(keysFile);
                return km;
            }

            // Generate and save
            km.generate();
            km.saveToFile(keysFile);
            return km;
        }

        // In-memory only
        km.generate();
        return km;
    }

    private void generate() throws JOSEException {
        delegationKey = new ECKeyGenerator(Curve.P_256)
                .keyUse(com.nimbusds.jose.jwk.KeyUse.SIGNATURE)
                .generate();
        // Set kid from thumbprint
        delegationKey = new ECKey.Builder(delegationKey)
                .keyID(computeKid(delegationKey))
                .build();

        auditKey = new ECKeyGenerator(Curve.P_256)
                .keyUse(com.nimbusds.jose.jwk.KeyUse.SIGNATURE)
                .generate();
        auditKey = new ECKey.Builder(auditKey)
                .keyID(computeKid(auditKey))
                .build();
    }

    /**
     * Computes a key ID from JWK thumbprint (RFC 7638), truncated to 16 characters.
     */
    private static String computeKid(ECKey key) throws JOSEException {
        String thumbprint = key.computeThumbprint().toString();
        if (thumbprint.length() > 16) {
            return thumbprint.substring(0, 16);
        }
        return thumbprint;
    }

    private void loadFromFile(Path path) throws IOException, ParseException, JOSEException {
        String json = Files.readString(path, StandardCharsets.UTF_8);

        // Parse the persisted format: {"delegationJwk": {...}, "delegationKid": "...", "auditJwk": {...}, "auditKid": "..."}
        // We use a simple approach: parse each JWK from the JSON
        int delStart = json.indexOf("\"delegationJwk\"");
        int auditStart = json.indexOf("\"auditJwk\"");

        if (delStart < 0 || auditStart < 0) {
            throw new ParseException("Invalid key file format", 0);
        }

        // Extract delegation JWK object
        String delJwkStr = extractJsonObject(json, delStart);
        // Extract audit JWK object
        String auditJwkStr = extractJsonObject(json, auditStart);

        // Extract KIDs
        String delKid = extractStringValue(json, "delegationKid");
        String auditKid = extractStringValue(json, "auditKid");

        delegationKey = ECKey.parse(delJwkStr);
        delegationKey = new ECKey.Builder(delegationKey).keyID(delKid).build();

        auditKey = ECKey.parse(auditJwkStr);
        auditKey = new ECKey.Builder(auditKey).keyID(auditKid).build();
    }

    private void saveToFile(Path path) throws IOException {
        // Ensure parent directory exists
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }

        String json = "{\n" +
                "  \"delegationJwk\": " + delegationKey.toJSONString() + ",\n" +
                "  \"delegationKid\": \"" + delegationKey.getKeyID() + "\",\n" +
                "  \"auditJwk\": " + auditKey.toJSONString() + ",\n" +
                "  \"auditKid\": \"" + auditKey.getKeyID() + "\"\n" +
                "}";

        Files.writeString(path, json, StandardCharsets.UTF_8);
    }

    /** Extracts a JSON object starting after the given field name. */
    private static String extractJsonObject(String json, int fieldStart) {
        int braceStart = json.indexOf('{', fieldStart);
        if (braceStart < 0) {
            throw new IllegalArgumentException("No JSON object found");
        }
        int depth = 0;
        for (int i = braceStart; i < json.length(); i++) {
            if (json.charAt(i) == '{') depth++;
            else if (json.charAt(i) == '}') {
                depth--;
                if (depth == 0) {
                    return json.substring(braceStart, i + 1);
                }
            }
        }
        throw new IllegalArgumentException("Unclosed JSON object");
    }

    /** Extracts a string value for the given field name. */
    private static String extractStringValue(String json, String field) {
        String marker = "\"" + field + "\"";
        int idx = json.indexOf(marker);
        if (idx < 0) {
            throw new IllegalArgumentException("Field not found: " + field);
        }
        int colonIdx = json.indexOf(':', idx + marker.length());
        int quoteStart = json.indexOf('"', colonIdx + 1);
        int quoteEnd = json.indexOf('"', quoteStart + 1);
        return json.substring(quoteStart + 1, quoteEnd);
    }

    // --- Accessors ---

    public ECPrivateKey getDelegationPrivateKey() throws JOSEException {
        return delegationKey.toECPrivateKey();
    }

    public ECPublicKey getDelegationPublicKey() throws JOSEException {
        return delegationKey.toECPublicKey();
    }

    public String getDelegationKid() {
        return delegationKey.getKeyID();
    }

    public ECKey getDelegationECKey() {
        return delegationKey;
    }

    public ECPrivateKey getAuditPrivateKey() throws JOSEException {
        return auditKey.toECPrivateKey();
    }

    public ECPublicKey getAuditPublicKey() throws JOSEException {
        return auditKey.toECPublicKey();
    }

    public String getAuditKid() {
        return auditKey.getKeyID();
    }

    public ECKey getAuditECKey() {
        return auditKey;
    }
}
