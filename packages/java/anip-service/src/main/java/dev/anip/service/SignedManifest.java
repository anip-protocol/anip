package dev.anip.service;

/**
 * Holds the manifest as canonical JSON bytes and its detached JWS signature.
 */
public class SignedManifest {

    private final byte[] manifestJson;
    private final String signature;

    public SignedManifest(byte[] manifestJson, String signature) {
        this.manifestJson = manifestJson;
        this.signature = signature;
    }

    public byte[] getManifestJson() {
        return manifestJson;
    }

    public String getSignature() {
        return signature;
    }
}
